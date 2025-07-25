"""
現代化LLM查詢代理 v2.0

整合結構化輸出、智能重試、AST安全驗證等現代化功能的新一代LLM Agent。

Author: Leon Lu
Created: 2025-01-25
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import requests

# 導入新的模組
from .sql_models import (
    SQLQueryResponse, SQLExtractionResult, SQLValidationResult, 
    EnhancedQueryResult, QueryRetryContext, MedicalQueryContext,
    QueryType, ConfidenceLevel
)
from .sql_extractor import sql_extractor
from .sql_validator import sql_validator
from .gemma3_prompts import gemma3_prompts
from .smart_retry import default_retry_manager, ErrorDiagnostics
from .db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class ConversationEnhancedResult:
    """對話增強查詢結果"""
    def __init__(self, base_result: EnhancedQueryResult, 
                 suggestions: List[str] = None,
                 context_used: bool = False):
        # 複製基本結果的所有屬性
        self.success = base_result.success
        self.data = base_result.data
        self.sql_query = base_result.sql_query
        self.error_message = base_result.error_message
        self.execution_time = base_result.execution_time
        self.confidence = base_result.confidence
        self.query_type = base_result.query_type
        self.explanation = base_result.explanation
        self.warnings = base_result.warnings
        self.retry_count = base_result.retry_count
        self.extraction_method = base_result.extraction_method
        self.validation_passed = base_result.validation_passed
        
        # 新增對話相關屬性
        self.suggestions = suggestions or []
        self.context_used = context_used


class ModernLLMQueryAgent:
    """現代化LLM查詢代理"""
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any]):
        """
        初始化現代化LLM查詢代理
        
        Args:
            db_manager: 資料庫管理器
            config: LLM配置
        """
        self.db_manager = db_manager
        self.config = config
        
        # LLM設定
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.model = config.get('model', 'gemma3:4b')
        self.timeout = config.get('timeout', {})
        
        # 統計資料
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_retries': 0,
            'avg_response_time': 0.0,
            'error_breakdown': {}
        }
        
        # 初始化診斷工具
        self.diagnostics = ErrorDiagnostics()
        
        logger.info(f"現代化LLM查詢代理已初始化: {self.model}")
    
    def process_query(self, user_query: str, user_id: str = "anonymous") -> EnhancedQueryResult:
        """
        處理自然語言查詢（主要入口點）
        
        Args:
            user_query: 使用者的自然語言查詢
            user_id: 使用者ID
            
        Returns:
            EnhancedQueryResult: 增強的查詢結果
        """
        start_time = time.time()
        self.stats['total_queries'] += 1
        
        # 創建重試上下文
        retry_context = default_retry_manager.create_retry_context(user_query)
        
        try:
            logger.info(f"處理查詢: {user_query}")
            
            # 使用智能重試機制
            result, final_context = default_retry_manager.execute_with_retry(
                self._execute_single_query,
                retry_context,
                user_query,
                start_time
            )
            
            # 更新統計
            self.stats['successful_queries'] += 1
            self.stats['total_retries'] += final_context.attempt_count - 1
            
            return result
            
        except Exception as e:
            # 查詢最終失敗
            self.stats['failed_queries'] += 1
            error_category = str(type(e).__name__)
            self.stats['error_breakdown'][error_category] = \
                self.stats['error_breakdown'].get(error_category, 0) + 1
            
            execution_time = time.time() - start_time
            
            logger.error(f"查詢處理失敗: {e}")
            
            return EnhancedQueryResult(
                success=False,
                sql_query="",
                error_message=str(e),
                error_type=error_category,
                execution_time=execution_time,
                retry_context=retry_context
            )
    
    def _execute_single_query(self, user_query: str, start_time: float) -> EnhancedQueryResult:
        """
        執行單次查詢（內部方法）
        
        Args:
            user_query: 用戶查詢
            start_time: 開始時間
            
        Returns:
            EnhancedQueryResult: 查詢結果
        """
        llm_start = time.time()
        
        # 1. 生成結構化提示詞
        system_prompt = gemma3_prompts.generate_system_prompt()
        user_prompt = gemma3_prompts.generate_user_prompt(user_query)
        
        # 2. 調用LLM
        llm_response = self._call_llm(system_prompt, user_prompt)
        llm_response_time = time.time() - llm_start
        
        # 3. 提取SQL
        parse_start = time.time()
        extraction_result = sql_extractor.extract_sql(llm_response)
        
        if not extraction_result.success:
            raise Exception(f"無法從LLM回應中提取有效的SQL語句: {extraction_result.error_message}")
        
        sql_query = extraction_result.sql_query
        sql_parse_time = time.time() - parse_start
        
        # 4. 安全驗證
        validation_result = sql_validator.validate_sql(sql_query)
        
        if not validation_result.is_safe:
            raise Exception(f"SQL查詢不安全: {validation_result.error_message}")
        
        # 5. 執行資料庫查詢
        db_start = time.time()
        try:
            df_result = self.db_manager.execute_query(sql_query)
            results = df_result.to_dict('records') if not df_result.empty else []
            result_count = len(results)
            
            logger.info(f"查詢成功: {result_count} 筆結果")
            
        except Exception as e:
            raise Exception(f"資料庫查詢執行失敗: {e}")
        
        db_execution_time = time.time() - db_start
        total_execution_time = time.time() - start_time
        
        # 6. 生成結果解釋
        interpretation = self._generate_interpretation(user_query, results, sql_query)
        
        # 7. 提取查詢類型和信心水準（如果LLM提供了結構化回應）
        query_type, confidence = self._extract_metadata_from_response(llm_response)
        
        return EnhancedQueryResult(
            success=True,
            sql_query=sql_query,
            results=results,
            result_count=result_count,
            execution_time=total_execution_time,
            interpretation=interpretation,
            query_type=query_type,
            confidence=confidence,
            llm_response_time=llm_response_time,
            sql_parse_time=sql_parse_time,
            db_execution_time=db_execution_time
        )
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        調用LLM生成SQL
        
        Args:
            system_prompt: 系統提示詞
            user_prompt: 用戶提示詞
            
        Returns:
            str: LLM回應
        """
        try:
            # 構建請求
            request_data = {
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "max_tokens": 2048,
                }
            }
            
            # 發送請求
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=request_data,
                timeout=self.timeout.get('inference', 30)
            )
            
            if response.status_code != 200:
                raise Exception(f"LLM API回應錯誤: {response.status_code}")
            
            result = response.json()
            llm_response = result.get('response', '').strip()
            
            if not llm_response:
                raise Exception("LLM回應為空")
            
            logger.debug(f"LLM回應長度: {len(llm_response)}")
            return llm_response
            
        except requests.RequestException as e:
            raise Exception(f"LLM連線失敗: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"LLM回應JSON解析失敗: {e}")
        except Exception as e:
            raise Exception(f"LLM調用失敗: {e}")
    
    def _generate_interpretation(self, user_query: str, results: List[Dict], sql_query: str) -> str:
        """
        生成查詢結果解釋
        
        Args:
            user_query: 原始查詢
            results: 查詢結果
            sql_query: 執行的SQL
            
        Returns:
            str: 結果解釋
        """
        result_count = len(results)
        
        if result_count == 0:
            return f"針對「{user_query}」的查詢已執行完成，但沒有找到符合條件的資料。"
        elif result_count == 1:
            return f"針對「{user_query}」的查詢已完成，找到 1 筆符合條件的資料。"
        else:
            return f"針對「{user_query}」的查詢已完成，共找到 {result_count} 筆符合條件的資料。"
    
    def _extract_metadata_from_response(self, llm_response: str) -> Tuple[Optional[QueryType], Optional[ConfidenceLevel]]:
        """
        從LLM回應中提取元數據
        
        Args:
            llm_response: LLM回應
            
        Returns:
            Tuple: (查詢類型, 信心水準)
        """
        try:
            # 嘗試解析JSON結構
            import re
            json_match = re.search(r'\\{.*\\}', llm_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                
                query_type = None
                if 'query_type' in data:
                    try:
                        query_type = QueryType(data['query_type'])
                    except ValueError:
                        pass
                
                confidence = None
                if 'confidence' in data:
                    try:
                        confidence = ConfidenceLevel(data['confidence'])
                    except ValueError:
                        pass
                
                return query_type, confidence
        
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None, None
    
    def process_query_with_context(self, user_query: str, context: MedicalQueryContext) -> EnhancedQueryResult:
        """
        帶上下文的查詢處理
        
        Args:
            user_query: 用戶查詢
            context: 醫療查詢上下文
            
        Returns:
            EnhancedQueryResult: 查詢結果
        """
        # 構建包含上下文的提示詞
        enhanced_prompt = self._build_contextual_prompt(user_query, context)
        return self.process_query(enhanced_prompt)
    
    def _build_contextual_prompt(self, user_query: str, context: MedicalQueryContext) -> str:
        """
        構建包含上下文的提示詞
        
        Args:
            user_query: 原始查詢
            context: 上下文資訊
            
        Returns:
            str: 增強的提示詞
        """
        prompt_parts = [user_query]
        
        if context.patient_name:
            prompt_parts.append(f"病患姓名：{context.patient_name}")
        
        if context.date_range:
            start_date = context.date_range.get('start', '')
            end_date = context.date_range.get('end', '')
            if start_date and end_date:
                prompt_parts.append(f"日期範圍：{start_date} 到 {end_date}")
        
        if context.medical_terms:
            prompt_parts.append(f"相關醫療術語：{', '.join(context.medical_terms)}")
        
        return "\\n".join(prompt_parts)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取代理統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        total_queries = self.stats['total_queries']
        successful_queries = self.stats['successful_queries']
        
        return {
            'total_queries': total_queries,
            'successful_queries': successful_queries,
            'failed_queries': self.stats['failed_queries'],
            'success_rate': successful_queries / total_queries if total_queries > 0 else 0.0,
            'total_retries': self.stats['total_retries'],
            'avg_response_time': self.stats['avg_response_time'],
            'error_breakdown': self.stats['error_breakdown'],
            'model': self.model
        }
    
    def get_query_suggestions(self) -> List[str]:
        """
        獲取查詢建議
        
        Returns:
            List[str]: 查詢建議列表
        """
        return [
            "查詢病患張小明的基本資料",
            "最近一週的檢驗結果",
            "統計本月就診人數",
            "查詢高血壓相關的處方記錄",
            "最近30天的抽血報告",
            "查詢特定醫師的診療記錄"
        ]
    
    def diagnose_query_issues(self, user_query: str, error_message: str) -> Dict[str, Any]:
        """
        診斷查詢問題
        
        Args:
            user_query: 用戶查詢
            error_message: 錯誤訊息
            
        Returns:
            Dict: 診斷結果
        """
        return {
            'query': user_query,
            'error': error_message,
            'suggestions': self.diagnostics.suggest_query_improvements(""),
            'model_info': {
                'model': self.model,
                'base_url': self.base_url
            }
        }
    
    def process_conversation_query(self, user_query: str, context: str = "", 
                                 user_id: str = "anonymous") -> ConversationEnhancedResult:
        """
        處理對話式查詢（包含上下文）
        
        Args:
            user_query: 使用者查詢
            context: 對話上下文
            user_id: 使用者ID
            
        Returns:
            ConversationEnhancedResult: 對話增強查詢結果
        """
        # 構建包含上下文的查詢
        enhanced_query = user_query
        context_used = False
        
        if context.strip():
            enhanced_query = f"對話上下文：\n{context}\n\n當前查詢：{user_query}"
            context_used = True
            logger.debug(f"使用對話上下文，長度: {len(context)}")
        
        # 執行基本查詢
        base_result = self.process_query(enhanced_query, user_id)
        
        # 生成智能建議
        suggestions = self._generate_conversation_suggestions(base_result, user_query)
        
        # 返回對話增強結果
        return ConversationEnhancedResult(
            base_result=base_result,
            suggestions=suggestions,
            context_used=context_used
        )
    
    def generate_follow_up_suggestions(self, result: EnhancedQueryResult, 
                                     original_query: str) -> List[str]:
        """
        生成後續建議
        
        Args:
            result: 查詢結果
            original_query: 原始查詢
            
        Returns:
            List[str]: 建議列表
        """
        return self._generate_conversation_suggestions(result, original_query)
    
    def _generate_conversation_suggestions(self, result: EnhancedQueryResult, 
                                         original_query: str) -> List[str]:
        """
        內部方法：生成對話建議
        
        Args:
            result: 查詢結果
            original_query: 原始查詢
            
        Returns:
            List[str]: 建議列表
        """
        suggestions = []
        
        try:
            if result.success and result.data:
                # 根據查詢類型和結果生成建議
                query_lower = original_query.lower()
                
                # 病患相關查詢
                if any(keyword in query_lower for keyword in ['病患', '姓名', '盧盈良', '楊淑欣']):
                    suggestions.extend([
                        "查看該病患的最近檢驗結果",
                        "分析該病患的用藥歷史",
                        "查看該病患的就診趨勢"
                    ])
                
                # 檢驗相關查詢
                elif any(keyword in query_lower for keyword in ['檢驗', '血糖', '血壓', '抽血']):
                    suggestions.extend([
                        "分析檢驗值的正常範圍",
                        "查看相關檢驗項目的趨勢",
                        "比較不同時期的檢驗結果"
                    ])
                
                # 統計相關查詢
                elif any(keyword in query_lower for keyword in ['統計', '分析', '數量', '人數']):
                    suggestions.extend([
                        "查看更詳細的統計分布",
                        "分析時間趨勢變化",
                        "比較不同期間的數據"
                    ])
                
                # 根據結果數量生成建議
                result_count = len(result.data)
                if result_count > 50:
                    suggestions.append("這個結果較多，是否需要增加篩選條件？")
                elif result_count == 0:
                    suggestions.extend([
                        "嘗試放寬查詢條件",
                        "檢查輸入的姓名或日期是否正確",
                        "查看相關的其他資料"
                    ])
                
            else:
                # 查詢失敗的建議
                suggestions.extend([
                    "嘗試用更簡單的方式描述需求",
                    "檢查輸入的條件是否正確",
                    "查看系統支援的查詢範例"
                ])
            
            # 通用建議
            if not suggestions:
                suggestions.extend([
                    "查詢其他病患的資料",
                    "分析不同時間段的統計",
                    "查看系統功能總覽"
                ])
                
        except Exception as e:
            logger.warning(f"生成建議時發生錯誤: {e}")
            suggestions = ["需要其他幫助嗎？"]
        
        # 限制建議數量並去重
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in unique_suggestions:
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:3]  # 最多返回3個建議
    
    def extract_mentioned_entities(self, text: str) -> Dict[str, List[str]]:
        """
        從文本中提取提到的實體（病患姓名、檢驗項目等）
        
        Args:
            text: 輸入文本
            
        Returns:
            Dict: 提取的實體
        """
        import re
        
        entities = {
            'patients': [],
            'lab_items': [],
            'medications': [],
            'dates': []
        }
        
        try:
            # 提取中文姓名（2-4個中文字符）
            name_pattern = r'[\u4e00-\u9fff]{2,4}(?=的|之|病患|先生|小姐|女士)'
            entities['patients'] = list(set(re.findall(name_pattern, text)))
            
            # 提取檢驗項目關鍵詞
            lab_keywords = ['血糖', '血壓', '血脂', '肝功能', '腎功能', '尿酸', '膽固醇']
            for keyword in lab_keywords:
                if keyword in text:
                    entities['lab_items'].append(keyword)
            
            # 提取日期
            date_patterns = [
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD or YYYY/MM/DD
                r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # MM-DD-YYYY or MM/DD/YYYY
                r'\d{8}',  # YYYYMMDD
                r'[今昨前]天|本週|上週|本月|上月|今年|去年'
            ]
            
            for pattern in date_patterns:
                entities['dates'].extend(re.findall(pattern, text))
                
        except Exception as e:
            logger.warning(f"實體提取失敗: {e}")
        
        return entities
    
    def format_conversation_response(self, result: ConversationEnhancedResult, 
                                   include_technical_details: bool = False) -> str:
        """
        格式化對話回應
        
        Args:
            result: 對話增強結果
            include_technical_details: 是否包含技術細節
            
        Returns:
            str: 格式化的回應
        """
        response_parts = []
        
        if result.success:
            # 成功回應
            if result.data and len(result.data) > 0:
                response_parts.append(f"✅ 查詢完成！找到 **{len(result.data)}** 筆相關記錄。")
            else:
                response_parts.append("✅ 查詢執行成功，但沒有找到符合條件的記錄。")
            
            if result.explanation:
                response_parts.append(f"\n📋 **說明：** {result.explanation}")
            
            if result.context_used:
                response_parts.append("\n🧠 *已結合對話上下文進行分析*")
            
            if include_technical_details:
                response_parts.append(f"\n⚡ 執行時間：{result.execution_time:.3f}秒")
                response_parts.append(f"🎯 信心度：{result.confidence}")
                if result.sql_query:
                    response_parts.append(f"\n🔍 SQL：`{result.sql_query[:100]}...`")
        else:
            # 失敗回應
            response_parts.append(f"❌ 查詢失敗：{result.error_message}")
            response_parts.append("\n💡 請嘗試用不同的方式描述您的需求。")
        
        if result.warnings:
            response_parts.append(f"\n⚠️ 注意：{'; '.join(result.warnings)}")
        
        return "\n".join(response_parts)


# 向後相容的別名
LLMQueryAgent = ModernLLMQueryAgent