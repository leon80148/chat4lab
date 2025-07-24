"""
診所AI查詢系統 - LLM查詢代理

負責處理自然語言查詢，將中文查詢轉換為安全的SQL語句，
並提供醫療專業術語的智能解析。

Author: Leon Lu
Created: 2025-01-24
"""

import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass

from .db_manager import DatabaseManager, DatabaseError

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """查詢結果封裝"""
    success: bool
    sql_query: str
    results: Optional[List[Dict]] = None
    error_message: str = ""
    execution_time: float = 0.0
    result_count: int = 0
    interpretation: str = ""


class MedicalTermsMapper:
    """醫療術語對應器"""
    
    def __init__(self):
        self.medical_terms = {
            # 基本資訊
            "病歷號": "kcstmr",
            "姓名": "mname", 
            "性別": "msex",
            "出生日期": "mbirthdt",
            "電話": "mtelh",
            "住家電話": "mfml",
            "體重": "mweight",
            "身高": "mheight",
            "初診日期": "mbegdt",
            "最後就診": "mlcasedate",
            "地址": "maddr",
            "身分證": "mpersonid",
            
            # 就診相關
            "就診日期": "idate",
            "就診時間": "itime", 
            "診斷": "labno",
            "主診斷": "labno",
            "次診斷": ["lacd01", "lacd02", "lacd03", "lacd04", "lacd05"],
            "醫師": "ipk3",
            "申報金額": "tot",
            "部分負擔": "sa98",
            
            # 處方相關
            "藥品代碼": "dno",
            "藥品類型": "ptp",
            "使用頻率": "pfq",
            "天數": "ptday",
            
            # 檢驗相關
            "檢驗日期": "hdate",
            "檢驗項目": "hitem",
            "檢驗描述": "hdscp",
            "檢驗值": "hval",
            "檢驗結果": "hresult",
            "參考值": "hrule",
        }
        
        self.common_queries = {
            "病患基本資料": "SELECT * FROM CO01M WHERE {condition}",
            "就診記錄": "SELECT * FROM CO03M WHERE {condition}",
            "處方記錄": "SELECT * FROM CO02M WHERE {condition}",
            "檢驗結果": "SELECT * FROM CO18H WHERE {condition}",
        }
        
        # 常見的醫療條件模式
        self.condition_patterns = {
            r"(\d+)歲以上": "CAST(substr(mbirthdt, 1, 4) AS INTEGER) <= (strftime('%Y', 'now') - {0})",
            r"(\d+)歲以下": "CAST(substr(mbirthdt, 1, 4) AS INTEGER) >= (strftime('%Y', 'now') - {0})",
            r"最近(\d+)天": "idate >= date('now', '-{0} days')",
            r"最近(\d+)個月": "idate >= date('now', '-{0} months')",
            r"(\d{4})年": "substr(idate, 1, 4) = '{0}'",
            r"(\d{1,2})月": "substr(idate, 6, 2) = '{0:02d}'",
        }


class LLMQueryAgent:
    """
    LLM查詢代理核心類別
    
    負責接收自然語言查詢，使用LLM理解查詢意圖，
    轉換為安全的SQL語句並執行查詢。
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any]):
        """
        初始化LLM查詢代理
        
        Args:
            db_manager: 資料庫管理器
            config: LLM配置
        """
        self.db_manager = db_manager
        self.config = config
        self.terms_mapper = MedicalTermsMapper()
        
        # LLM設定
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.model = config.get('model', 'llama3:8b-instruct')
        self.temperature = config.get('parameters', {}).get('temperature', 0.2)
        self.max_tokens = config.get('parameters', {}).get('max_tokens', 2048)
        
        # 查詢統計
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'avg_response_time': 0.0
        }
        
        logger.info(f"LLM查詢代理已初始化: {self.model}")
    
    def _get_system_prompt(self) -> str:
        """獲取系統提示詞 - 針對Llama3優化"""
        return """你是一個專業的診所AI查詢助手，專門協助醫護人員查詢台灣診所的病患資料。你精通SQL語法並理解繁體中文醫療術語。

## 資料庫結構 (展望診療系統)

**CO01M - 病患主檔：**
- kcstmr: 病歷號 (主鍵)
- mname: 病患姓名 
- msex: 性別 (M/F)
- mbirthdt: 出生日期 (YYYYMMDD)
- mtelh: 行動電話
- mweight: 體重 (公斤)
- mheight: 身高 (公分)
- mpersonid: 身分證字號 (敏感資料)

**CO02M - 處方記錄：**
- kcstmr: 病歷號 (外鍵)
- idate: 開立日期 (YYYYMMDD)
- dno: 藥品代碼
- ptp: 藥品類型
- pfq: 使用頻率 (TID/BID/QID等)
- ptday: 用藥天數

**CO03M - 就診摘要：**
- kcstmr: 病歷號 (外鍵)
- idate: 就診日期 (YYYYMMDD)
- labno: 主診斷代碼
- ipk3: 醫師代碼
- tot: 申報金額

**CO18H - 檢驗結果：**
- kcstmr: 病歷號 (外鍵)
- hdate: 檢驗日期 (YYYYMMDD)
- hitem: 檢驗項目代碼
- hval: 檢驗數值
- hresult: 檢驗結果描述

## 重要安全規則
1. **絕對只能產生SELECT查詢** - 嚴禁INSERT/UPDATE/DELETE/DROP等操作
2. **使用參數化查詢** - 防止SQL注入攻擊
3. **姓名模糊搜尋** - 使用 `LIKE '%姓名%'` 語法
4. **日期格式標準** - 統一使用 YYYYMMDD 格式
5. **結果數量限制** - 必須加上 `LIMIT 1000` 避免大量資料
6. **敏感資料保護** - 避免直接查詢身分證等個資

## 查詢範例
```sql
-- 查詢病患基本資料
SELECT kcstmr, mname, msex, mbirthdt FROM CO01M WHERE mname LIKE '%李%' LIMIT 100;

-- 查詢就診記錄 
SELECT c.idate, p.mname, c.labno FROM CO03M c 
JOIN CO01M p ON c.kcstmr = p.kcstmr 
WHERE c.idate >= '20240101' LIMIT 100;
```

請根據使用者的繁體中文醫療查詢需求，產生準確、安全的SQL語句。必須用```sql開始，```結束包圍SQL語句。"""

    def _call_llm(self, prompt: str, user_query: str) -> str:
        """
        呼叫LLM服務
        
        Args:
            prompt: 系統提示詞
            user_query: 使用者查詢
            
        Returns:
            str: LLM回應
        """
        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_query}
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result.get('message', {}).get('content', '')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM服務呼叫失敗: {e}")
            raise Exception(f"無法連接到LLM服務: {e}")
        except Exception as e:
            logger.error(f"LLM處理失敗: {e}")
            raise Exception(f"LLM處理錯誤: {e}")
    
    def _extract_sql_from_response(self, response: str) -> str:
        """
        從LLM回應中提取SQL語句
        
        Args:
            response: LLM回應文字
            
        Returns:
            str: 提取的SQL語句
        """
        # 嘗試找到SQL代碼塊
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(SELECT.*?)\s*```',
            r'(SELECT\s+.*?(?:;|$))',
        ]
        
        for pattern in sql_patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                sql = matches[0].strip()
                if sql.upper().startswith('SELECT'):
                    return sql.rstrip(';')
        
        raise Exception("無法從LLM回應中提取有效的SQL語句")
    
    def _preprocess_query(self, query: str) -> str:
        """
        預處理使用者查詢
        
        Args:
            query: 原始查詢
            
        Returns:
            str: 處理後的查詢
        """
        # 移除多餘空白
        query = re.sub(r'\s+', ' ', query.strip())
        
        # 替換常見醫療術語
        for term, field in self.terms_mapper.medical_terms.items():
            if isinstance(field, str):
                query = query.replace(term, f"{term}({field})")
        
        return query
    
    def _validate_and_enhance_sql(self, sql: str) -> str:
        """
        驗證並增強SQL語句
        
        Args:
            sql: 原始SQL語句
            
        Returns:
            str: 增強後的SQL語句
        """
        sql_upper = sql.upper().strip()
        
        # 基本安全檢查
        if not sql_upper.startswith('SELECT'):
            raise Exception("只允許SELECT查詢")
        
        # 添加LIMIT限制
        if 'LIMIT' not in sql_upper:
            sql += ' LIMIT 1000'
        
        # 確保不超過最大限制
        limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > 1000:
                sql = re.sub(r'LIMIT\s+\d+', 'LIMIT 1000', sql, flags=re.IGNORECASE)
        
        return sql
    
    def _interpret_results(self, query: str, results: List[Dict]) -> str:
        """
        解釋查詢結果
        
        Args:
            query: 原始查詢
            results: 查詢結果
            
        Returns:
            str: 結果解釋
        """
        if not results:
            return "未找到符合條件的資料。"
        
        count = len(results)
        
        # 根據查詢類型提供不同的解釋
        if "病患" in query or "姓名" in query:
            return f"找到 {count} 位病患的資料。"
        elif "就診" in query or "看診" in query:
            return f"找到 {count} 次就診記錄。"
        elif "處方" in query or "藥物" in query:
            return f"找到 {count} 筆處方記錄。"
        elif "檢驗" in query or "檢查" in query:
            return f"找到 {count} 項檢驗結果。"
        else:
            return f"查詢完成，共找到 {count} 筆資料。"
    
    def process_query(self, user_query: str, user_id: str = "anonymous") -> QueryResult:
        """
        處理自然語言查詢
        
        Args:
            user_query: 使用者的自然語言查詢
            user_id: 使用者ID
            
        Returns:
            QueryResult: 查詢結果
        """
        start_time = datetime.now()
        self.stats['total_queries'] += 1
        
        try:
            logger.info(f"處理查詢: {user_query}")
            
            # 預處理查詢
            processed_query = self._preprocess_query(user_query)
            
            # 構建提示詞
            system_prompt = self._get_system_prompt()
            
            # 呼叫LLM生成SQL
            llm_response = self._call_llm(system_prompt, processed_query)
            
            # 提取SQL語句
            sql_query = self._extract_sql_from_response(llm_response)
            
            # 驗證並增強SQL
            validated_sql = self._validate_and_enhance_sql(sql_query)
            
            # 執行查詢
            df_result = self.db_manager.execute_query(validated_sql, user_id=user_id)
            results = df_result.to_dict('records')
            
            # 計算執行時間
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 生成結果解釋
            interpretation = self._interpret_results(user_query, results)
            
            # 更新統計
            self.stats['successful_queries'] += 1
            self.stats['avg_response_time'] = (
                (self.stats['avg_response_time'] * (self.stats['successful_queries'] - 1) + execution_time) 
                / self.stats['successful_queries']
            )
            
            logger.info(f"查詢成功: {len(results)} 筆結果")
            
            return QueryResult(
                success=True,
                sql_query=validated_sql,
                results=results,
                execution_time=execution_time,
                result_count=len(results),
                interpretation=interpretation
            )
            
        except Exception as e:
            self.stats['failed_queries'] += 1
            error_message = str(e)
            
            logger.error(f"查詢處理失敗: {error_message}")
            
            return QueryResult(
                success=False,
                sql_query="",
                error_message=error_message,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def get_query_suggestions(self, context: str = "") -> List[str]:
        """
        根據上下文提供查詢建議
        
        Args:
            context: 上下文資訊
            
        Returns:
            List[str]: 建議的查詢語句
        """
        suggestions = [
            "查詢病患李小明的基本資料",
            "顯示最近一週的就診記錄",
            "找出所有糖尿病患者",
            "查看王醫師今天的診療記錄",
            "顯示血糖檢驗異常的病患",
            "查詢本月開立的抗生素處方",
            "找出40歲以上的高血壓病患",
            "顯示最近的X光檢查結果"
        ]
        
        return suggestions
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取查詢統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        success_rate = 0.0
        if self.stats['total_queries'] > 0:
            success_rate = self.stats['successful_queries'] / self.stats['total_queries']
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'model_info': {
                'model': self.model,
                'base_url': self.base_url,
                'temperature': self.temperature
            }
        }
    
    def clear_statistics(self):
        """清除統計資訊"""
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'avg_response_time': 0.0
        }
        logger.info("查詢統計已清除")


class QueryValidator:
    """查詢驗證器"""
    
    @staticmethod
    def validate_medical_query(query: str) -> Tuple[bool, str]:
        """
        驗證醫療查詢的合理性
        
        Args:
            query: 查詢語句
            
        Returns:
            Tuple[bool, str]: (是否有效, 錯誤訊息)
        """
        # 檢查是否包含醫療相關關鍵字
        medical_keywords = [
            '病患', '診斷', '處方', '檢驗', '醫師', '就診', 
            '藥物', '治療', '症狀', '病歷', '檢查'
        ]
        
        if not any(keyword in query for keyword in medical_keywords):
            return False, "查詢內容似乎與醫療資料無關"
        
        # 檢查查詢長度
        if len(query.strip()) < 3:
            return False, "查詢內容太短，請提供更詳細的描述"
        
        if len(query) > 500:
            return False, "查詢內容太長，請簡化查詢條件"
        
        return True, ""
    
    @staticmethod
    def validate_sql_safety(sql: str) -> Tuple[bool, str]:
        """
        驗證SQL語句的安全性
        
        Args:
            sql: SQL語句
            
        Returns:
            Tuple[bool, str]: (是否安全, 錯誤訊息)
        """
        dangerous_patterns = [
            r'(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)',
            r'(EXEC|EXECUTE|SCRIPT)',
            r'(--|/\*|\*/)',
            r'(UNION.*SELECT)',
            r'(\bxp_|\bsp_)',
        ]
        
        sql_upper = sql.upper()
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return False, f"SQL語句包含危險操作: {pattern}"
        
        if not sql_upper.strip().startswith('SELECT'):
            return False, "只允許SELECT查詢操作"
        
        return True, ""