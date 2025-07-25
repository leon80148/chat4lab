"""
增強型SQL提取器

實現多層級fallback機制，從LLM回應中可靠地提取SQL查詢語句。
支援JSON格式、代碼塊、純文本等多種格式。

Author: Leon Lu  
Created: 2025-01-25
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from .sql_models import SQLExtractionResult, SQLQueryResponse

logger = logging.getLogger(__name__)


@dataclass
class ExtractionMethod:
    """提取方法定義"""
    name: str
    description: str
    confidence_weight: float
    pattern: Optional[str] = None


class EnhancedSQLExtractor:
    """增強型SQL提取器"""
    
    def __init__(self):
        """初始化提取器"""
        self.extraction_methods = [
            ExtractionMethod(
                name="structured_json",
                description="結構化JSON響應提取",
                confidence_weight=1.0
            ),
            ExtractionMethod(
                name="json_sql_field",
                description="JSON中sql_query欄位提取",
                confidence_weight=0.9
            ),
            ExtractionMethod(
                name="sql_code_block",
                description="```sql代碼塊提取",
                confidence_weight=0.8,
                pattern=r'```sql\s*(.*?)\s*```'
            ),
            ExtractionMethod(
                name="generic_code_block",
                description="通用```代碼塊提取",
                confidence_weight=0.7,
                pattern=r'```\s*(SELECT.*?)\s*```'
            ),
            ExtractionMethod(
                name="select_statement",
                description="SELECT語句正則提取",
                confidence_weight=0.6,
                pattern=r'\b(SELECT\s+.*?(?:LIMIT\s+\d+|;|$))'
            ),
            ExtractionMethod(
                name="multiline_select",
                description="多行SELECT語句提取",
                confidence_weight=0.5,
                pattern=r'(SELECT\s+[^"]*?(?:LIMIT\s+\d+|;|(?=\s*["}])))'
            )
        ]
        
        # SQL清理規則
        self.cleanup_patterns = [
            (r'\s*--.*?\n', '\n'),  # 移除SQL註釋
            (r'/\*.*?\*/', ''),     # 移除多行註釋
            (r'",\s*".*$', ''),     # 移除JSON片段 (以", "開始)
            (r'"\s*,\s*".*$', ''),  # 移除JSON片段的另一種形式
            (r'\s+', ' '),          # 標準化空白
            (r';\s*$', ''),         # 移除結尾分號
        ]
    
    def extract_sql(self, llm_response: str) -> SQLExtractionResult:
        """
        從LLM回應中提取SQL查詢
        
        Args:
            llm_response: LLM的原始回應
            
        Returns:
            SQLExtractionResult: 提取結果
        """
        logger.debug(f"開始SQL提取，回應長度: {len(llm_response)}")
        
        # 嘗試各種提取方法
        best_result = None
        best_confidence = 0.0
        
        for method in self.extraction_methods:
            try:
                result = self._try_extraction_method(method, llm_response)
                if result and result.confidence_score > best_confidence:
                    best_result = result
                    best_confidence = result.confidence_score
                    
                    # 如果找到高信心結果，提前返回
                    if best_confidence >= 0.9:
                        break
                        
            except Exception as e:
                logger.debug(f"提取方法 {method.name} 失敗: {e}")
                continue
        
        if not best_result:
            return SQLExtractionResult(
                success=False,
                extraction_method="none",
                confidence_score=0.0,
                raw_response=llm_response,
                error_message="無法從回應中提取任何SQL語句"
            )
        
        return best_result
    
    def _try_extraction_method(self, method: ExtractionMethod, response: str) -> Optional[SQLExtractionResult]:
        """
        嘗試特定的提取方法
        
        Args:
            method: 提取方法
            response: LLM回應
            
        Returns:
            Optional[SQLExtractionResult]: 提取結果
        """
        if method.name == "structured_json":
            return self._extract_structured_json(response, method)
        elif method.name == "json_sql_field":
            return self._extract_json_sql_field(response, method)
        elif method.pattern:
            return self._extract_with_pattern(response, method)
        else:
            return None
    
    def _extract_structured_json(self, response: str, method: ExtractionMethod) -> Optional[SQLExtractionResult]:
        """提取結構化JSON響應"""
        try:
            # 嘗試找到JSON對象
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            # 驗證是否為完整的SQLQueryResponse格式
            sql_response = SQLQueryResponse(**data)
            
            return SQLExtractionResult(
                success=True,
                sql_query=sql_response.sql_query,
                extraction_method=method.name,
                confidence_score=method.confidence_weight,
                raw_response=response
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"結構化JSON提取失敗: {e}")
            return None
    
    def _extract_json_sql_field(self, response: str, method: ExtractionMethod) -> Optional[SQLExtractionResult]:
        """從JSON中提取sql_query欄位"""
        try:
            # 尋找可能的JSON片段
            json_patterns = [
                r'\{[^{}]*"sql_query"[^{}]*\}',
                r'\{.*?"sql_query".*?\}',
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if 'sql_query' in data and data['sql_query'].strip():
                            sql = self._clean_sql(data['sql_query'])
                            if self._is_valid_sql_format(sql):
                                return SQLExtractionResult(
                                    success=True,
                                    sql_query=sql,
                                    extraction_method=method.name,
                                    confidence_score=method.confidence_weight,
                                    raw_response=response
                                )
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"JSON sql_query欄位提取失敗: {e}")
            return None
    
    def _extract_with_pattern(self, response: str, method: ExtractionMethod) -> Optional[SQLExtractionResult]:
        """使用正則表達式提取SQL"""
        try:
            matches = re.findall(method.pattern, response, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                sql = self._clean_sql(match)
                if self._is_valid_sql_format(sql):
                    # 計算信心分數
                    confidence = self._calculate_pattern_confidence(sql, method)
                    
                    return SQLExtractionResult(
                        success=True,
                        sql_query=sql,
                        extraction_method=method.name,
                        confidence_score=confidence,
                        raw_response=response
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"模式提取失敗 {method.name}: {e}")
            return None
    
    def _clean_sql(self, sql: str) -> str:
        """清理SQL語句"""
        if not sql:
            return ""
        
        # 應用清理規則
        cleaned = sql.strip()
        for pattern, replacement in self.cleanup_patterns:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # 標準化空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _is_valid_sql_format(self, sql: str) -> bool:
        """檢查SQL格式的基本有效性"""
        if not sql or len(sql) < 10:
            return False
        
        sql_upper = sql.upper().strip()
        
        # 必須以SELECT開始
        if not sql_upper.startswith('SELECT'):
            return False
        
        # 基本結構檢查
        required_keywords = ['SELECT', 'FROM']
        for keyword in required_keywords:
            if keyword not in sql_upper:
                return False
        
        # 檢查是否包含危險操作
        dangerous_operations = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for op in dangerous_operations:
            if op in sql_upper:
                return False
        
        return True
    
    def _calculate_pattern_confidence(self, sql: str, method: ExtractionMethod) -> float:
        """計算模式提取的信心分數"""
        base_confidence = method.confidence_weight
        
        # 根據SQL品質調整信心分數
        quality_factors = []
        
        # 檢查是否包含LIMIT
        if 'LIMIT' in sql.upper():
            quality_factors.append(0.1)
        
        # 檢查是否有合理的WHERE條件
        if 'WHERE' in sql.upper():
            quality_factors.append(0.1)
        
        # 檢查是否指定了具體欄位
        if not re.search(r'SELECT\s+\*', sql, re.IGNORECASE):
            quality_factors.append(0.05)
        
        # 檢查長度合理性
        if 20 <= len(sql) <= 500:
            quality_factors.append(0.05)
        
        # 計算最終信心分數
        bonus = sum(quality_factors)
        final_confidence = min(1.0, base_confidence + bonus)
        
        return final_confidence
    
    def extract_multiple_candidates(self, response: str) -> List[SQLExtractionResult]:
        """
        提取多個SQL候選項
        
        Args:
            response: LLM回應
            
        Returns:
            List[SQLExtractionResult]: 所有可能的SQL提取結果
        """
        candidates = []
        
        for method in self.extraction_methods:
            try:
                result = self._try_extraction_method(method, response)
                if result and result.success:
                    # 檢查是否已經有相同的SQL
                    is_duplicate = any(
                        candidate.sql_query.strip().upper() == result.sql_query.strip().upper()
                        for candidate in candidates
                    )
                    
                    if not is_duplicate:
                        candidates.append(result)
                        
            except Exception as e:
                logger.debug(f"提取候選項時發生錯誤 {method.name}: {e}")
                continue
        
        # 按信心分數排序
        candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return candidates
    
    def validate_extraction_result(self, result: SQLExtractionResult) -> bool:
        """
        驗證提取結果的有效性
        
        Args:
            result: 提取結果
            
        Returns:
            bool: 是否有效
        """
        if not result.success or not result.sql_query:
            return False
        
        return self._is_valid_sql_format(result.sql_query)


# 創建全局提取器實例
sql_extractor = EnhancedSQLExtractor()