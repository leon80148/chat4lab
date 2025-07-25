"""
智能錯誤處理和重試機制

實現指數退避重試、錯誤分類、自動修復建議等功能。

Author: Leon Lu
Created: 2025-01-25
"""

import time
import logging
import random
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from .sql_models import QueryRetryContext, EnhancedQueryResult

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """錯誤分類枚舉"""
    SQL_EXTRACTION_FAILED = "sql_extraction_failed"
    SQL_SYNTAX_ERROR = "sql_syntax_error"
    SQL_SECURITY_ERROR = "sql_security_error"
    DATABASE_ERROR = "database_error"
    LLM_CONNECTION_ERROR = "llm_connection_error"
    LLM_RESPONSE_ERROR = "llm_response_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class RetryStrategy:
    """重試策略配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_categories: List[ErrorCategory] = field(default_factory=lambda: [
        ErrorCategory.SQL_EXTRACTION_FAILED,
        ErrorCategory.LLM_CONNECTION_ERROR,
        ErrorCategory.LLM_RESPONSE_ERROR,
        ErrorCategory.TIMEOUT_ERROR
    ])


@dataclass
class ErrorInfo:
    """錯誤資訊封裝"""
    category: ErrorCategory
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    is_retryable: bool = True
    suggested_fixes: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class SmartErrorHandler:
    """智能錯誤處理器"""
    
    def __init__(self):
        """初始化錯誤處理器"""
        self.error_patterns = {
            # SQL提取錯誤
            r"無法從.*回應.*提取.*SQL": ErrorCategory.SQL_EXTRACTION_FAILED,
            r".*extract.*sql.*failed": ErrorCategory.SQL_EXTRACTION_FAILED,
            
            # SQL語法錯誤
            r".*syntax.*error": ErrorCategory.SQL_SYNTAX_ERROR,
            r".*near.*unexpected": ErrorCategory.SQL_SYNTAX_ERROR,
            r".*invalid.*syntax": ErrorCategory.SQL_SYNTAX_ERROR,
            
            # SQL安全錯誤
            r".*禁止.*關鍵字": ErrorCategory.SQL_SECURITY_ERROR,
            r".*不允許.*操作": ErrorCategory.SQL_SECURITY_ERROR,
            r".*敏感.*欄位": ErrorCategory.SQL_SECURITY_ERROR,
            
            # 資料庫錯誤
            r".*no such table": ErrorCategory.DATABASE_ERROR,
            r".*no such column": ErrorCategory.DATABASE_ERROR,
            r".*database.*lock": ErrorCategory.DATABASE_ERROR,
            
            # LLM連線錯誤
            r".*connection.*refused": ErrorCategory.LLM_CONNECTION_ERROR,
            r".*timeout.*connect": ErrorCategory.LLM_CONNECTION_ERROR,
            r".*ollama.*not.*respond": ErrorCategory.LLM_CONNECTION_ERROR,
            
            # LLM回應錯誤
            r".*json.*decode.*error": ErrorCategory.LLM_RESPONSE_ERROR,
            r".*invalid.*response.*format": ErrorCategory.LLM_RESPONSE_ERROR,
            r".*empty.*response": ErrorCategory.LLM_RESPONSE_ERROR,
        }
        
        self.fix_suggestions = {
            ErrorCategory.SQL_EXTRACTION_FAILED: [
                "檢查LLM回應格式是否正確",
                "嘗試使用更明確的Prompt指示",
                "檢查是否需要調整SQL提取模式",
                "考慮使用Few-shot範例引導"
            ],
            ErrorCategory.SQL_SYNTAX_ERROR: [
                "檢查SQL語法是否符合SQLite標準",
                "確認資料表和欄位名稱正確",
                "檢查括號、引號是否配對",
                "簡化SQL查詢結構"
            ],
            ErrorCategory.SQL_SECURITY_ERROR: [
                "移除危險的SQL關鍵字",
                "使用允許的查詢操作",
                "避免存取敏感欄位",
                "添加適當的安全限制"
            ],
            ErrorCategory.DATABASE_ERROR: [
                "檢查資料表名稱是否正確",
                "確認欄位名稱拼寫無誤",
                "檢查資料庫連線狀態",
                "驗證資料庫權限設定"
            ],
            ErrorCategory.LLM_CONNECTION_ERROR: [
                "檢查Ollama服務是否正常運行",
                "確認網路連線正常",
                "檢查模型是否已載入",
                "嘗試重新啟動LLM服務"
            ],
            ErrorCategory.LLM_RESPONSE_ERROR: [
                "檢查LLM回應格式",
                "調整Prompt以獲得更好的結構化輸出",
                "增加回應驗證邏輯",
                "考慮使用不同的提取策略"
            ]
        }
    
    def categorize_error(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ErrorInfo:
        """
        錯誤分類和分析
        
        Args:
            error_message: 錯誤訊息
            context: 錯誤上下文
            
        Returns:
            ErrorInfo: 錯誤資訊
        """
        import re
        
        # 錯誤分類
        category = ErrorCategory.UNKNOWN_ERROR
        for pattern, error_cat in self.error_patterns.items():
            if re.search(pattern, error_message, re.IGNORECASE):
                category = error_cat
                break
        
        # 判斷是否可重試
        is_retryable = category in [
            ErrorCategory.SQL_EXTRACTION_FAILED,
            ErrorCategory.LLM_CONNECTION_ERROR,
            ErrorCategory.LLM_RESPONSE_ERROR,
            ErrorCategory.TIMEOUT_ERROR
        ]
        
        # 獲取修復建議
        suggested_fixes = self.fix_suggestions.get(category, ["檢查錯誤詳情並手動修復"])
        
        return ErrorInfo(
            category=category,
            message=error_message,
            details=context or {},
            is_retryable=is_retryable,
            suggested_fixes=suggested_fixes,
            context=context or {}
        )
    
    def generate_recovery_context(self, error_info: ErrorInfo, previous_attempts: List[str]) -> Dict[str, Any]:
        """
        生成錯誤恢復上下文
        
        Args:
            error_info: 錯誤資訊
            previous_attempts: 之前的嘗試記錄
            
        Returns:
            Dict: 恢復上下文
        """
        recovery_context = {
            "error_type": error_info.category.value,
            "error_message": error_info.message,
            "suggestions": error_info.suggested_fixes,
            "attempt_count": len(previous_attempts)
        }
        
        # 針對特定錯誤類型的特殊處理
        if error_info.category == ErrorCategory.SQL_EXTRACTION_FAILED:
            recovery_context.update({
                "instruction": "請確保回應格式為有效的JSON，包含sql_query欄位",
                "format_hint": "使用 ```json 代碼塊包裹JSON回應"
            })
        
        elif error_info.category == ErrorCategory.SQL_SYNTAX_ERROR:
            recovery_context.update({
                "instruction": "請檢查SQL語法，確保符合SQLite標準",
                "syntax_hints": [
                    "使用正確的資料表名稱：CO01M, CO02M, CO03M, CO18H",
                    "日期格式使用YYYYMMDD",
                    "字串比較使用LIKE '%pattern%'"
                ]
            })
        
        elif error_info.category == ErrorCategory.SQL_SECURITY_ERROR:
            recovery_context.update({
                "instruction": "請遵守安全規則，只使用允許的SQL操作",
                "security_reminders": [
                    "只能使用SELECT查詢",
                    "避免存取敏感欄位如身分證",
                    "必須添加LIMIT限制"
                ]
            })
        
        # 添加之前嘗試的SQL（如果有）
        if previous_attempts:
            recovery_context["previous_sql"] = previous_attempts[-1]
        
        return recovery_context


class SmartRetryManager:
    """智能重試管理器"""
    
    def __init__(self, strategy: Optional[RetryStrategy] = None):
        """
        初始化重試管理器
        
        Args:
            strategy: 重試策略配置
        """
        self.strategy = strategy or RetryStrategy()
        self.error_handler = SmartErrorHandler()
    
    def execute_with_retry(self, 
                          operation: Callable,
                          context: QueryRetryContext,
                          *args, **kwargs) -> Tuple[Any, QueryRetryContext]:
        """
        帶重試的操作執行
        
        Args:
            operation: 要執行的操作函數
            context: 重試上下文
            *args, **kwargs: 操作參數
            
        Returns:
            Tuple[Any, QueryRetryContext]: (操作結果, 更新後的上下文)
        """
        last_error = None
        
        for attempt in range(self.strategy.max_attempts):
            try:
                # 更新嘗試次數
                context.attempt_count = attempt + 1
                
                # 如果不是第一次嘗試，計算延遲時間
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"重試第 {attempt + 1} 次，延遲 {delay:.2f} 秒")
                    time.sleep(delay)
                
                # 執行操作
                result = operation(*args, **kwargs)
                
                # 成功執行，返回結果
                if attempt > 0:
                    logger.info(f"重試成功，總嘗試次數: {attempt + 1}")
                
                return result, context
                
            except Exception as e:
                last_error = e
                error_info = self.error_handler.categorize_error(str(e))
                
                # 記錄錯誤
                context.previous_errors.append(str(e))
                logger.warning(f"第 {attempt + 1} 次嘗試失敗: {e}")
                
                # 檢查是否應該重試
                if not error_info.is_retryable or error_info.category not in self.strategy.retry_on_categories:
                    logger.error(f"錯誤不可重試或不在重試類別中: {error_info.category}")
                    break
                
                # 如果是最後一次嘗試，不再重試
                if attempt == self.strategy.max_attempts - 1:
                    logger.error(f"已達到最大重試次數 {self.strategy.max_attempts}")
                    break
                
                # 生成改進措施
                improvements = error_info.suggested_fixes
                context.improvements.extend(improvements)
        
        # 所有重試都失敗，拋出最後一個錯誤
        raise last_error
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        計算重試延遲時間
        
        Args:
            attempt: 當前嘗試次數（從0開始）
            
        Returns:
            float: 延遲時間（秒）
        """
        # 指數退避計算
        delay = self.strategy.base_delay * (self.strategy.exponential_base ** attempt)
        
        # 限制最大延遲
        delay = min(delay, self.strategy.max_delay)
        
        # 添加隨機抖動避免雷群效應
        if self.strategy.jitter:
            jitter = random.uniform(0.0, 0.1 * delay)
            delay += jitter
        
        return delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        判斷是否應該重試
        
        Args:
            error: 錯誤對象
            attempt: 當前嘗試次數
            
        Returns:
            bool: 是否應該重試
        """
        if attempt >= self.strategy.max_attempts:
            return False
        
        error_info = self.error_handler.categorize_error(str(error))
        
        return (error_info.is_retryable and 
                error_info.category in self.strategy.retry_on_categories)
    
    def create_retry_context(self, original_query: str) -> QueryRetryContext:
        """
        創建重試上下文
        
        Args:
            original_query: 原始查詢
            
        Returns:
            QueryRetryContext: 重試上下文
        """
        return QueryRetryContext(
            attempt_count=0,
            previous_errors=[],
            retry_strategy=self.strategy.__class__.__name__,
            last_sql=None,
            improvements=[]
        )


class ErrorDiagnostics:
    """錯誤診斷工具"""
    
    @staticmethod
    def diagnose_sql_error(sql: str, error_message: str) -> Dict[str, Any]:
        """
        診斷SQL錯誤
        
        Args:
            sql: SQL語句
            error_message: 錯誤訊息
            
        Returns:
            Dict: 診斷結果
        """
        diagnosis = {
            "sql": sql,
            "error": error_message,
            "issues": [],
            "recommendations": []
        }
        
        # 基本語法檢查
        if not sql.strip().upper().startswith('SELECT'):
            diagnosis["issues"].append("SQL必須以SELECT開始")
            diagnosis["recommendations"].append("修改為SELECT查詢")
        
        # 檢查資料表名稱
        import re
        table_pattern = r'FROM\s+(\w+)'
        tables = re.findall(table_pattern, sql, re.IGNORECASE)
        valid_tables = {'CO01M', 'CO02M', 'CO03M', 'CO18H'}
        
        for table in tables:
            if table.upper() not in valid_tables:
                diagnosis["issues"].append(f"無效的資料表名稱: {table}")
                diagnosis["recommendations"].append(f"使用有效的資料表: {', '.join(valid_tables)}")
        
        # 檢查LIMIT子句
        if 'LIMIT' not in sql.upper():
            diagnosis["issues"].append("缺少LIMIT子句")
            diagnosis["recommendations"].append("添加LIMIT子句以限制結果數量")
        
        return diagnosis
    
    @staticmethod
    def suggest_query_improvements(sql: str) -> List[str]:
        """
        建議查詢改進
        
        Args:
            sql: SQL語句
            
        Returns:
            List[str]: 改進建議
        """
        suggestions = []
        sql_upper = sql.upper()
        
        # 性能建議
        if 'SELECT *' in sql_upper:
            suggestions.append("建議指定具體欄位而非使用SELECT *")
        
        if 'WHERE' not in sql_upper:
            suggestions.append("建議添加WHERE條件縮小查詢範圍")
        
        if 'ORDER BY' not in sql_upper and 'LIMIT' in sql_upper:
            suggestions.append("使用LIMIT時建議添加ORDER BY確保結果一致性")
        
        # 安全建議
        if 'LIKE' in sql_upper and "'%" not in sql and '"%' not in sql:
            suggestions.append("LIKE查詢建議使用萬用字元%提高匹配靈活性")
        
        return suggestions


# 創建全局實例
default_retry_manager = SmartRetryManager()
error_diagnostics = ErrorDiagnostics()