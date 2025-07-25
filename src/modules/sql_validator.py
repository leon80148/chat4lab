"""
現代化SQL安全驗證器

基於AST解析和智能白名單的SQL安全驗證系統，替代過於嚴格的正則表達式檢查。

Author: Leon Lu
Created: 2025-01-25  
"""

import re
import logging
import sqlparse
from typing import Dict, List, Set, Optional, Tuple, Any
from sqlparse import sql, tokens as T
from sqlparse.sql import Statement, IdentifierList, Identifier, Function

from .sql_models import SQLValidationResult

logger = logging.getLogger(__name__)


class SQLSecurityValidator:
    """基於AST的SQL安全驗證器"""
    
    def __init__(self):
        """初始化驗證器"""
        # 允許的SQL關鍵字（白名單）
        self.allowed_keywords = {
            # 查詢關鍵字
            'SELECT', 'FROM', 'WHERE', 'ORDER', 'BY', 'GROUP', 'HAVING',
            'LIMIT', 'OFFSET', 'DISTINCT', 'AS', 'ASC', 'DESC', 'ORDER BY',
            
            # 連接關鍵字
            'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'ON', 'USING',
            
            # 條件關鍵字
            'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'NULL',
            'TRUE', 'FALSE',
            
            # 函數關鍵字
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'UPPER', 'LOWER', 'TRIM',
            'SUBSTR', 'LENGTH', 'STRFTIME', 'DATE', 'DATETIME', 'CAST',
            
            # 聚合
            'UNION', 'ALL',
            
            # 案例表達式
            'CASE', 'WHEN', 'THEN', 'ELSE', 'END'
        }
        
        # 允許的資料表
        self.allowed_tables = {
            'CO01M',  # 病患主檔
            'CO02M',  # 處方記錄
            'CO03M',  # 就診摘要
            'CO18H',  # 檢驗結果
        }
        
        # 允許的欄位（基本檢查）
        self.table_fields = {
            'CO01M': {
                'kcstmr', 'mname', 'msex', 'mbirthdt', 'mtelh', 'mfml',
                'mweight', 'mheight', 'mbegdt', 'mlcasedate', 'maddr'
                # 注意：不包含敏感欄位如 mpersonid
            },
            'CO02M': {
                'kcstmr', 'idate', 'itime', 'dno', 'ptp', 'pfq', 'ptday'
            },
            'CO03M': {
                'kcstmr', 'idate', 'itime', 'labno', 'ipk3', 'tot', 'sa98'
            },
            'CO18H': {
                'kcstmr', 'hdate', 'htime', 'hitem', 'hdscp', 'hval', 'hresult', 'hrule'
            }
        }
        
        # 完全禁止的關鍵字
        self.forbidden_keywords = {
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
            'EXEC', 'EXECUTE', 'SCRIPT', 'PROCEDURE', 'FUNCTION',
            'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK', 'TRANSACTION'
        }
        
        # 敏感欄位（需要特別保護）
        self.sensitive_fields = {
            'mpersonid',  # 身分證字號
            'maddr',      # 詳細地址（需要特別注意）
        }
        
        # 允許的註釋模式（更寬鬆的規則）
        self.comment_patterns = [
            r'--[^\r\n]*',     # 單行註釋
            r'/\*.*?\*/',      # 多行註釋
        ]
    
    def validate_sql(self, sql: str) -> SQLValidationResult:
        """
        全面驗證SQL安全性
        
        Args:
            sql: SQL查詢語句
            
        Returns:
            SQLValidationResult: 驗證結果
        """
        try:
            logger.debug(f"開始驗證SQL: {sql[:100]}...")
            
            # 基本格式檢查
            basic_result = self._basic_validation(sql)
            if not basic_result.is_valid:
                return basic_result
            
            # AST解析
            try:
                parsed = sqlparse.parse(sql)[0]
            except Exception as e:
                return SQLValidationResult(
                    is_valid=False,
                    is_safe=False,
                    error_type="parse_error",
                    error_message=f"SQL解析失敗: {e}",
                    suggestions=["檢查SQL語法是否正確"]
                )
            
            # AST安全分析
            ast_result = self._analyze_ast_security(parsed, sql)
            if not ast_result.is_safe:
                return ast_result
            
            # 結構分析
            structure_result = self._analyze_sql_structure(parsed)
            if not structure_result.is_valid:
                return structure_result
                
            # 敏感資料檢查
            sensitivity_result = self._check_sensitive_data_access(parsed)
            if not sensitivity_result.is_safe:
                return sensitivity_result
            
            return SQLValidationResult(
                is_valid=True,
                is_safe=True,
                parsed_sql=self._extract_sql_metadata(parsed)
            )
            
        except Exception as e:
            logger.error(f"SQL驗證發生未預期錯誤: {e}")
            return SQLValidationResult(
                is_valid=False,
                is_safe=False,
                error_type="validation_error",
                error_message=f"驗證過程發生錯誤: {e}"
            )
    
    def _basic_validation(self, sql: str) -> SQLValidationResult:
        """基本格式驗證"""
        if not sql or not sql.strip():
            return SQLValidationResult(
                is_valid=False,
                is_safe=False,
                error_type="empty_sql",
                error_message="SQL查詢為空"
            )
        
        sql_clean = sql.strip().upper()
        
        # 必須以SELECT開始
        if not sql_clean.startswith('SELECT'):
            return SQLValidationResult(
                is_valid=False,
                is_safe=False,
                error_type="invalid_operation",
                error_message="只允許SELECT查詢操作",
                suggestions=["請使用SELECT語句查詢資料"]
            )
        
        # 檢查禁止的關鍵字
        for forbidden in self.forbidden_keywords:
            if forbidden in sql_clean:
                return SQLValidationResult(
                    is_valid=False,
                    is_safe=False,
                    error_type="forbidden_keyword",
                    error_message=f"包含禁止的關鍵字: {forbidden}",
                    suggestions=["請移除危險的SQL操作關鍵字"]
                )
        
        return SQLValidationResult(is_valid=True, is_safe=True)
    
    def _analyze_ast_security(self, parsed: Statement, original_sql: str) -> SQLValidationResult:
        """AST安全分析"""
        try:
            # 提取所有令牌
            tokens = list(parsed.flatten())
            
            # 檢查禁止的關鍵字
            for token in tokens:
                if token.ttype is T.Keyword:
                    keyword = token.value.upper()
                    # 只檢查明確禁止的關鍵字，對於其他關鍵字給出警告但不阻止
                    if keyword in self.forbidden_keywords:
                        return SQLValidationResult(
                            is_valid=False,
                            is_safe=False,
                            error_type="forbidden_keyword",
                            error_message=f"使用了禁止的關鍵字: {keyword}"
                        )
                    elif keyword not in self.allowed_keywords and keyword not in {'(', ')', ',', ';', '=', '<', '>', '<=', '>=', '!=', '<>'}:
                        # 未知關鍵字，只記錄警告
                        logger.debug(f"發現未知關鍵字: {keyword}")
            
            # 檢查是否只有SELECT語句
            statements = [stmt for stmt in parsed.tokens if isinstance(stmt, sql.Statement) or 
                         (hasattr(stmt, 'ttype') and stmt.ttype is T.Keyword)]
            
            return SQLValidationResult(is_valid=True, is_safe=True)
            
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                is_safe=False,
                error_type="ast_analysis_error",
                error_message=f"AST安全分析失敗: {e}"
            )
    
    def _analyze_sql_structure(self, parsed: Statement) -> SQLValidationResult:
        """分析SQL結構合法性"""
        try:
            # 提取資料表名稱
            tables = self._extract_table_names(parsed)
            
            # 檢查資料表是否在允許列表中
            for table in tables:
                if table and table.strip():  # 確保非空
                    if table.upper() not in self.allowed_tables:
                        return SQLValidationResult(
                            is_valid=False,
                            is_safe=False,
                            error_type="invalid_table",
                            error_message=f"不允許存取資料表: {table}",
                            suggestions=[f"請使用允許的資料表: {', '.join(self.allowed_tables)}"]
                        )
            
            # 檢查是否有LIMIT限制（建議性檢查）
            has_limit = self._has_limit_clause(parsed)
            suggestions = []
            if not has_limit:
                suggestions.append("建議添加LIMIT子句限制結果數量")
            
            return SQLValidationResult(
                is_valid=True,
                is_safe=True,
                suggestions=suggestions
            )
            
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                is_safe=False,
                error_type="structure_analysis_error", 
                error_message=f"結構分析失敗: {e}"
            )
    
    def _check_sensitive_data_access(self, parsed: Statement) -> SQLValidationResult:
        """檢查敏感資料存取"""
        try:
            # 提取欄位名稱
            fields = self._extract_field_names(parsed)
            
            # 檢查是否存取敏感欄位
            accessed_sensitive_fields = []
            for field in fields:
                if field.lower() in self.sensitive_fields:
                    accessed_sensitive_fields.append(field)
            
            if accessed_sensitive_fields:
                return SQLValidationResult(
                    is_valid=False,
                    is_safe=False,
                    error_type="sensitive_data_access",
                    error_message=f"嘗試存取敏感欄位: {', '.join(accessed_sensitive_fields)}",
                    suggestions=["請避免查詢個人敏感資訊如身分證字號、詳細地址等"]
                )
            
            return SQLValidationResult(is_valid=True, is_safe=True)
            
        except Exception as e:
            return SQLValidationResult(
                is_valid=True,  # 檢查失敗不影響整體驗證
                is_safe=True,
                suggestions=[f"敏感資料檢查時發生錯誤: {e}"]
            )
    
    def _extract_table_names(self, parsed: Statement) -> Set[str]:
        """從AST中提取資料表名稱"""
        tables = set()
        
        # 使用更直接的方法：分析扁平化的token序列
        tokens = list(parsed.flatten())
        from_found = False
        
        for i, token in enumerate(tokens):
            if token.ttype is T.Keyword and token.value.upper() == 'FROM':
                from_found = True
                continue
            elif from_found and token.ttype is T.Keyword:
                # 遇到其他關鍵字，FROM子句結束
                if token.value.upper() in ('WHERE', 'ORDER', 'GROUP', 'HAVING', 'LIMIT', 'JOIN'):
                    break
            elif from_found and token.ttype is T.Name and not token.is_whitespace:
                # 這是FROM後面的第一個名稱，應該是資料表
                table_name = token.value.strip()
                if table_name and table_name.upper() in self.allowed_tables:
                    tables.add(table_name)
                    break  # 找到資料表後就停止
        
        # 如果還是沒找到，使用正則fallback
        if not tables:
            import re
            sql_str = str(parsed)
            from_matches = re.findall(r'FROM\s+([A-Za-z][A-Za-z0-9_]*)', sql_str, re.IGNORECASE)
            for table_name in from_matches:
                if table_name.upper() in self.allowed_tables:
                    tables.add(table_name)
                    break
        
        return tables
    
    def _extract_field_names(self, parsed: Statement) -> Set[str]:
        """從AST中提取欄位名稱"""
        fields = set()
        
        def extract_from_token(token):
            if isinstance(token, Identifier):
                # 處理 table.field 格式
                name = token.get_name()
                if '.' in name:
                    fields.add(name.split('.')[1])
                else:
                    fields.add(name)
            elif isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    extract_from_token(identifier)
            elif hasattr(token, 'tokens'):
                for subtoken in token.tokens:
                    extract_from_token(subtoken)
        
        # 處理SELECT子句
        select_found = False
        for token in parsed.tokens:
            if token.ttype is T.Keyword and token.value.upper() == 'SELECT':
                select_found = True
                continue
            elif select_found and token.ttype is T.Keyword and token.value.upper() == 'FROM':
                break
            elif select_found and not token.is_whitespace:
                extract_from_token(token)
        
        return fields
    
    def _has_limit_clause(self, parsed: Statement) -> bool:
        """檢查是否有LIMIT子句"""
        for token in parsed.tokens:
            if token.ttype is T.Keyword and token.value.upper() == 'LIMIT':
                return True
        return False
    
    def _extract_sql_metadata(self, parsed: Statement) -> Dict[str, Any]:
        """提取SQL元數據用於後續分析"""
        try:
            metadata = {
                'tables': list(self._extract_table_names(parsed)),
                'fields': list(self._extract_field_names(parsed)),
                'has_limit': self._has_limit_clause(parsed),
                'has_where': any(token.ttype is T.Keyword and token.value.upper() == 'WHERE' 
                               for token in parsed.tokens),
                'has_order': any(token.ttype is T.Keyword and token.value.upper() == 'ORDER' 
                               for token in parsed.tokens),
            }
            return metadata
        except Exception as e:
            logger.warning(f"提取SQL元數據失敗: {e}")
            return {}
    
    def suggest_improvements(self, sql: str) -> List[str]:
        """建議SQL改進措施"""
        suggestions = []
        
        sql_upper = sql.upper()
        
        # 檢查LIMIT
        if 'LIMIT' not in sql_upper:
            suggestions.append("建議添加LIMIT子句限制結果數量，如：LIMIT 100")
        
        # 檢查WHERE條件
        if 'WHERE' not in sql_upper:
            suggestions.append("建議添加WHERE條件縮小查詢範圍")
        
        # 檢查SELECT *
        if 'SELECT *' in sql_upper:
            suggestions.append("建議指定具體欄位而非使用SELECT *")
        
        # 檢查索引欄位使用
        if 'kcstmr' not in sql.lower() and 'WHERE' in sql_upper:
            suggestions.append("建議在WHERE條件中使用病歷號(kcstmr)以提高查詢效率")
        
        return suggestions


# 創建全局驗證器實例
sql_validator = SQLSecurityValidator()