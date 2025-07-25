"""
SQL查詢結構化輸出模型

使用Pydantic實現強類型的SQL查詢響應格式，確保LLM輸出的一致性和可靠性。

Author: Leon Lu
Created: 2025-01-25
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
import re


class QueryType(str, Enum):
    """查詢類型枚舉"""
    PATIENT_INFO = "patient_info"
    VISIT_RECORD = "visit_record"
    PRESCRIPTION = "prescription"
    LAB_RESULT = "lab_result"
    STATISTICS = "statistics"
    GENERAL = "general"


class ConfidenceLevel(str, Enum):
    """信心水準枚舉"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SQLQueryResponse(BaseModel):
    """LLM SQL查詢響應的結構化模型"""
    
    sql_query: str = Field(
        ...,
        description="生成的SQL查詢語句",
        min_length=10,
        max_length=2000
    )
    
    query_type: QueryType = Field(
        ...,
        description="查詢類型分類"
    )
    
    confidence: ConfidenceLevel = Field(
        ...,
        description="對生成SQL的信心水準"
    )
    
    explanation: str = Field(
        ...,
        description="SQL查詢的中文解釋",
        min_length=5,
        max_length=500
    )
    
    table_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="使用的資料表映射 {table_alias: table_name}"
    )
    
    field_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="使用的欄位映射 {chinese_term: field_name}"
    )
    
    estimated_results: Optional[int] = Field(
        None,
        description="預估結果筆數",
        ge=0,
        le=10000
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="潛在的警告或注意事項"
    )
    
    @validator('sql_query')
    def validate_sql_query(cls, v):
        """驗證SQL查詢基本格式"""
        if not v.strip():
            raise ValueError("SQL查詢不能為空")
        
        # 確保以SELECT開始
        if not v.strip().upper().startswith('SELECT'):
            raise ValueError("只允許SELECT查詢")
        
        # 檢查是否包含危險關鍵字
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        v_upper = v.upper()
        for keyword in dangerous_keywords:
            if keyword in v_upper:
                raise ValueError(f"SQL包含危險關鍵字: {keyword}")
        
        return v.strip()
    
    @validator('explanation')
    def validate_explanation(cls, v):
        """驗證解釋內容"""
        if not v.strip():
            raise ValueError("解釋不能為空")
        return v.strip()


class SQLExtractionResult(BaseModel):
    """SQL提取結果模型"""
    
    success: bool = Field(..., description="是否成功提取SQL")
    sql_query: Optional[str] = Field(None, description="提取的SQL查詢")
    extraction_method: str = Field(..., description="使用的提取方法")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="提取信心分數")
    raw_response: str = Field(..., description="原始LLM回應")
    error_message: Optional[str] = Field(None, description="錯誤訊息")


class SQLValidationResult(BaseModel):
    """SQL驗證結果模型"""
    
    is_valid: bool = Field(..., description="SQL是否有效")
    is_safe: bool = Field(..., description="SQL是否安全")
    error_type: Optional[str] = Field(None, description="錯誤類型")
    error_message: Optional[str] = Field(None, description="錯誤訊息")
    suggestions: List[str] = Field(default_factory=list, description="改進建議")
    parsed_sql: Optional[Dict[str, Any]] = Field(None, description="解析後的SQL結構")


class MedicalQueryContext(BaseModel):
    """醫療查詢上下文模型"""
    
    patient_name: Optional[str] = Field(None, description="病患姓名")
    date_range: Optional[Dict[str, str]] = Field(None, description="日期範圍")
    medical_terms: List[str] = Field(default_factory=list, description="醫療術語")
    query_intent: Optional[str] = Field(None, description="查詢意圖")
    ambiguous_terms: List[str] = Field(default_factory=list, description="模糊術語")


class QueryRetryContext(BaseModel):
    """查詢重試上下文模型"""
    
    attempt_count: int = Field(0, ge=0, le=5, description="重試次數")
    previous_errors: List[str] = Field(default_factory=list, description="之前的錯誤")
    retry_strategy: str = Field("exponential_backoff", description="重試策略")
    last_sql: Optional[str] = Field(None, description="上次的SQL")
    improvements: List[str] = Field(default_factory=list, description="改進措施")


class EnhancedQueryResult(BaseModel):
    """增強的查詢結果模型"""
    
    success: bool = Field(..., description="查詢是否成功")
    sql_query: str = Field(..., description="執行的SQL查詢")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="查詢結果")
    result_count: int = Field(0, ge=0, description="結果筆數")
    execution_time: float = Field(0.0, ge=0.0, description="執行時間(秒)")
    
    # 增強欄位
    interpretation: str = Field("", description="結果解釋")
    query_type: Optional[QueryType] = Field(None, description="查詢類型")
    confidence: Optional[ConfidenceLevel] = Field(None, description="信心水準")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="額外元數據")
    
    # 錯誤處理
    error_message: Optional[str] = Field(None, description="錯誤訊息")
    error_type: Optional[str] = Field(None, description="錯誤類型")
    retry_context: Optional[QueryRetryContext] = Field(None, description="重試上下文")
    
    # 性能監控
    llm_response_time: Optional[float] = Field(None, description="LLM回應時間")
    sql_parse_time: Optional[float] = Field(None, description="SQL解析時間")
    db_execution_time: Optional[float] = Field(None, description="資料庫執行時間")


# JSON Schema 定義 - 用於LLM指導
SQL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "sql_query": {
            "type": "string",
            "description": "生成的SQL查詢語句，必須以SELECT開始",
            "minLength": 10,
            "maxLength": 2000
        },
        "query_type": {
            "type": "string",
            "enum": ["patient_info", "visit_record", "prescription", "lab_result", "statistics", "general"],
            "description": "查詢類型分類"
        },
        "confidence": {
            "type": "string", 
            "enum": ["high", "medium", "low"],
            "description": "對生成SQL的信心水準"
        },
        "explanation": {
            "type": "string",
            "description": "SQL查詢的中文解釋",
            "minLength": 5,
            "maxLength": 500
        },
        "table_mapping": {
            "type": "object",
            "description": "使用的資料表映射",
            "additionalProperties": {"type": "string"}
        },
        "field_mapping": {
            "type": "object", 
            "description": "使用的欄位映射",
            "additionalProperties": {"type": "string"}
        },
        "estimated_results": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10000,
            "description": "預估結果筆數"
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "潛在的警告或注意事項"
        }
    },
    "required": ["sql_query", "query_type", "confidence", "explanation"],
    "additionalProperties": False
}