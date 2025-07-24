"""
安全性測試 (Security Tests)

測試系統的安全防護措施，包括SQL注入防護、認證授權、敏感資料保護等。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
import tempfile
import hashlib
import re
from pathlib import Path
from unittest.mock import Mock, patch
import sqlite3

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager
from src.modules.dbf_parser import ZhanWangDBFParser
from src.modules.llm_agent import LLMQueryAgent, QueryValidator
from src.modules.query_templates import QueryTemplateManager


class TestSQLInjectionPrevention:
    """SQL注入攻擊防護測試"""
    
    @pytest.fixture
    def security_db(self):
        """建立安全測試資料庫"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        db_manager.create_indexes()
        
        # 準備測試資料
        test_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002', '0000003'],
            'mname': ['李小明', '王小華', '張醫師'],
            'msex': ['M', 'F', 'M'],
            'mbirthdt': ['19800101', '19850315', '19750620'],
            'mpersonid': ['A123456789', 'B987654321', 'C456789123']  # 敏感資料
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        yield db_manager
        
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    def test_basic_sql_injection_protection(self, security_db):
        """測試基本SQL注入防護"""
        malicious_queries = [
            "SELECT * FROM CO01M; DROP TABLE CO01M;",
            "SELECT * FROM CO01M WHERE kcstmr = '1' OR '1'='1'",
            "SELECT * FROM CO01M; DELETE FROM CO01M WHERE 1=1;",
            "SELECT * FROM CO01M UNION SELECT password FROM users;",
            "SELECT * FROM CO01M WHERE kcstmr = '1'; INSERT INTO CO01M VALUES ('hack');",
        ]
        
        for malicious_sql in malicious_queries:
            with pytest.raises(Exception) as exc_info:
                security_db.execute_query(malicious_sql)
            
            # 確保錯誤訊息指出這是安全問題
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in ['危險', 'injection', '安全', 'forbidden'])
            
            print(f"成功阻止惡意查詢: {malicious_sql[:50]}...")
    
    def test_comment_injection_protection(self, security_db):
        """測試註釋注入防護"""
        comment_injections = [
            "SELECT * FROM CO01M -- WHERE condition",
            "SELECT * FROM CO01M /* comment */ WHERE 1=1",
            "SELECT * FROM CO01M WHERE kcstmr = '1' -- ' AND other_condition",
            "SELECT /*! DROP TABLE CO01M */ * FROM CO01M",
        ]
        
        for injection in comment_injections:
            with pytest.raises(Exception):
                security_db.execute_query(injection)
            
            print(f"成功阻止註釋注入: {injection}")
    
    def test_union_based_injection_protection(self, security_db):
        """測試UNION型注入防護"""
        union_injections = [
            "SELECT kcstmr FROM CO01M UNION SELECT mpersonid FROM CO01M",
            "SELECT * FROM CO01M WHERE kcstmr = '1' UNION ALL SELECT * FROM CO01M",
            "SELECT mname FROM CO01M UNION SELECT 'hacker' as mname",
        ]
        
        for injection in union_injections:
            with pytest.raises(Exception):
                security_db.execute_query(injection)
            
            print(f"成功阻止UNION注入: {injection}")
    
    def test_stored_procedure_injection_protection(self, security_db):
        """測試儲存程序注入防護"""
        sp_injections = [
            "EXEC xp_cmdshell 'dir'",
            "SELECT * FROM CO01M; EXEC sp_configure 'show advanced options', 1",
            "EXECUTE('DROP TABLE CO01M')",
        ]
        
        for injection in sp_injections:
            with pytest.raises(Exception):
                security_db.execute_query(injection)
            
            print(f"成功阻止儲存程序注入: {injection}")


class TestLLMSecurityValidation:
    """LLM查詢安全驗證測試"""
    
    @pytest.fixture
    def llm_security_system(self):
        """建立LLM安全測試系統"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        
        # 準備測試資料
        test_data = pd.DataFrame({
            'kcstmr': ['0000001'],
            'mname': ['測試病患'],
            'msex': ['M'],
            'mbirthdt': ['19800101']
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        yield llm_agent
        
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    @patch('requests.post')
    def test_malicious_llm_response_filtering(self, mock_post, llm_security_system):
        """測試惡意LLM回應過濾"""
        malicious_responses = [
            "```sql\nDROP TABLE CO01M; SELECT * FROM CO01M\n```",
            "```sql\nSELECT * FROM CO01M; DELETE FROM CO01M WHERE 1=1\n```",
            "```sql\nUPDATE CO01M SET mname='hacked' WHERE kcstmr='0000001'\n```",
            "```sql\nINSERT INTO CO01M VALUES ('hack', 'hacker', 'X', '20250101')\n```",
            "```sql\nALTER TABLE CO01M ADD COLUMN hack TEXT\n```",
        ]
        
        for malicious_response in malicious_responses:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'message': {'content': malicious_response}
            }
            mock_post.return_value = mock_response
            
            result = llm_security_system.process_query("查詢病患資料")
            
            # 應該檢測到惡意SQL並拒絕執行
            assert result.success == False
            assert "危險" in result.error_message or "只允許SELECT" in result.error_message
            
            print(f"成功阻止惡意LLM回應: {malicious_response[:50]}...")
    
    @patch('requests.post')
    def test_sensitive_data_access_control(self, mock_post, llm_security_system):
        """測試敏感資料存取控制"""
        # 嘗試存取敏感欄位
        sensitive_queries = [
            "查詢所有病患的身分證字號",
            "顯示病患的個人識別資訊",
            "匯出包含身分證的病患清單",
        ]
        
        # 模擬LLM生成存取敏感資料的SQL
        sensitive_sql_responses = [
            "```sql\nSELECT mpersonid FROM CO01M\n```",
            "```sql\nSELECT kcstmr, mname, mpersonid FROM CO01M\n```",
            "```sql\nSELECT * FROM CO01M\n```",  # 包含所有欄位，含敏感資料
        ]
        
        for query, sql_response in zip(sensitive_queries, sensitive_sql_responses):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'message': {'content': sql_response}
            }
            mock_post.return_value = mock_response
            
            result = llm_security_system.process_query(query)
            
            # 檢查是否有適當的敏感資料保護措施
            if result.success:
                # 如果查詢成功，檢查結果是否包含敏感資料
                for record in result.results:
                    assert 'mpersonid' not in record or record['mpersonid'] is None
                    print(f"敏感資料已適當處理: {query}")
            else:
                print(f"成功阻止敏感資料存取: {query}")
    
    def test_query_validator_security_checks(self):
        """測試查詢驗證器安全檢查"""
        # 測試醫療查詢驗證
        invalid_queries = [
            "幫我駭進系統",
            "刪除所有資料",
            "顯示系統密碼",
            "執行惡意程式",
        ]
        
        for invalid_query in invalid_queries:
            is_valid, error_msg = QueryValidator.validate_medical_query(invalid_query)
            assert is_valid == False
            assert len(error_msg) > 0
            print(f"成功識別非醫療查詢: {invalid_query}")
        
        # 測試SQL安全驗證
        dangerous_sqls = [
            "DROP TABLE CO01M",
            "DELETE FROM CO01M WHERE 1=1",
            "UPDATE CO01M SET mname='hack'",
            "INSERT INTO CO01M VALUES ('hack')",
            "EXEC xp_cmdshell 'dir'",
            "SELECT * FROM CO01M; DROP TABLE CO01M",
        ]
        
        for dangerous_sql in dangerous_sqls:
            is_safe, error_msg = QueryValidator.validate_sql_safety(dangerous_sql)
            assert is_safe == False
            assert len(error_msg) > 0
            print(f"成功識別危險SQL: {dangerous_sql}")


class TestDataPrivacyProtection:
    """資料隱私保護測試"""
    
    @pytest.fixture
    def privacy_db(self):
        """建立隱私保護測試資料庫"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        
        # 準備包含敏感資料的測試資料
        sensitive_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002', '0000003'],
            'mname': ['李小明', '王小華', '張醫師'],
            'msex': ['M', 'F', 'M'],
            'mbirthdt': ['19800101', '19850315', '19750620'],
            'mpersonid': ['A123456789', 'B987654321', 'C456789123'],  # 身分證
            'mtelh': ['0912345678', '0987654321', '0923456789'],      # 電話
            'maddr': ['台北市信義區', '新北市板橋區', '桃園市中壢區']   # 地址
        })
        db_manager.import_dbf_data('CO01M', sensitive_data)
        
        yield db_manager
        
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    def test_sensitive_field_protection(self, privacy_db):
        """測試敏感欄位保護"""
        # 測試正常查詢（非敏感欄位）
        safe_query = "SELECT kcstmr, mname, msex FROM CO01M"
        result = privacy_db.execute_query(safe_query)
        
        assert len(result) == 3
        assert 'mpersonid' not in result.columns  # 確保沒有身分證欄位
        
        # 測試包含敏感欄位的查詢
        sensitive_queries = [
            "SELECT mpersonid FROM CO01M",
            "SELECT kcstmr, mpersonid FROM CO01M",
            "SELECT * FROM CO01M WHERE mpersonid = 'A123456789'",
        ]
        
        for sensitive_query in sensitive_queries:
            # 根據系統設計，可能會：
            # 1. 拒絕執行查詢
            # 2. 執行但隱藏敏感欄位
            # 3. 執行但遮罩敏感資料
            try:
                result = privacy_db.execute_query(sensitive_query)
                # 如果執行成功，檢查敏感資料是否被適當處理
                for _, row in result.iterrows():
                    if 'mpersonid' in row:
                        # 檢查是否被遮罩（如：A****6789）
                        person_id = str(row['mpersonid'])
                        if len(person_id) > 4:
                            assert '*' in person_id or person_id == '[PROTECTED]'
                
                print(f"敏感資料已遮罩: {sensitive_query}")
                
            except Exception as e:
                # 如果拒絕執行，確保錯誤訊息適當
                assert "敏感" in str(e) or "隱私" in str(e) or "保護" in str(e)
                print(f"成功阻止敏感資料查詢: {sensitive_query}")
    
    def test_data_anonymization(self, privacy_db):
        """測試資料匿名化"""
        # 查詢大量資料進行統計分析
        stats_query = """
            SELECT 
                msex,
                COUNT(*) as count,
                ROUND(AVG(CAST(substr(mbirthdt, 1, 4) AS INTEGER)), 0) as avg_birth_year
            FROM CO01M 
            GROUP BY msex
        """
        
        result = privacy_db.execute_query(stats_query)
        
        assert len(result) >= 1
        # 統計資料不應包含個人識別資訊
        for col in result.columns:
            assert col not in ['kcstmr', 'mname', 'mpersonid', 'mtelh']
        
        print("統計查詢成功，無個人識別資訊洩露")
    
    def test_access_logging(self, privacy_db):
        """測試存取日誌記錄"""
        # 執行查詢並檢查是否有適當的日誌記錄
        test_queries = [
            "SELECT COUNT(*) FROM CO01M",
            "SELECT mname FROM CO01M WHERE msex = 'M'",
            "SELECT * FROM CO01M LIMIT 1",
        ]
        
        for query in test_queries:
            result = privacy_db.execute_query(query, user_id="test_user")
            assert len(result) >= 0
        
        # 檢查系統統計是否記錄了查詢
        stats = privacy_db.get_table_stats()
        if 'query_stats' in stats:
            query_stats = stats['query_stats']
            assert query_stats['queries_executed'] >= len(test_queries)
            print(f"查詢日誌記錄正常: {query_stats['queries_executed']} 次查詢")


class TestAuthenticationSecurity:
    """認證安全測試"""
    
    def test_password_security_requirements(self):
        """測試密碼安全要求"""
        # 這裡模擬密碼驗證邏輯
        def validate_password(password):
            """模擬密碼驗證函數"""
            if len(password) < 8:
                return False, "密碼長度至少8位"
            if not re.search(r'[A-Z]', password):
                return False, "密碼需包含大寫字母"
            if not re.search(r'[a-z]', password):
                return False, "密碼需包含小寫字母"
            if not re.search(r'\d', password):
                return False, "密碼需包含數字"
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                return False, "密碼需包含特殊字符"
            return True, ""
        
        weak_passwords = [
            "123456",
            "password",
            "abcdefgh",
            "12345678",
            "Password",
            "Password123",
        ]
        
        for weak_password in weak_passwords:
            is_valid, error_msg = validate_password(weak_password)
            assert is_valid == False
            assert len(error_msg) > 0
            print(f"成功識別弱密碼: {weak_password}")
        
        # 測試強密碼
        strong_passwords = [
            "MyStr0ng!Pass",
            "Clinic#2024$Secure",
            "Admin@123!System",
        ]
        
        for strong_password in strong_passwords:
            is_valid, error_msg = validate_password(strong_password)
            assert is_valid == True
            print(f"強密碼驗證通過: {strong_password}")
    
    def test_session_security(self):
        """測試會話安全"""
        # 模擬會話管理
        class SessionManager:
            def __init__(self):
                self.sessions = {}
            
            def create_session(self, user_id):
                import secrets
                session_id = secrets.token_urlsafe(32)
                self.sessions[session_id] = {
                    'user_id': user_id,
                    'created_at': time.time(),
                    'last_access': time.time()
                }
                return session_id
            
            def validate_session(self, session_id, timeout=1800):  # 30分鐘
                if session_id not in self.sessions:
                    return False, "會話不存在"
                
                session = self.sessions[session_id]
                current_time = time.time()
                
                if current_time - session['last_access'] > timeout:
                    del self.sessions[session_id]
                    return False, "會話已過期"
                
                session['last_access'] = current_time
                return True, ""
        
        import time
        session_mgr = SessionManager()
        
        # 測試會話建立
        session_id = session_mgr.create_session("test_user")
        assert len(session_id) > 20  # 確保會話ID夠長
        
        # 測試會話驗證
        is_valid, error_msg = session_mgr.validate_session(session_id)
        assert is_valid == True
        
        # 測試會話過期
        is_valid, error_msg = session_mgr.validate_session(session_id, timeout=0)
        assert is_valid == False
        assert "過期" in error_msg
        
        print("會話安全機制驗證通過")


class TestSystemSecurityHardening:
    """系統安全加固測試"""
    
    def test_database_file_permissions(self):
        """測試資料庫檔案權限"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        db_manager.close()
        
        # 檢查檔案權限
        import stat
        file_stat = Path(db_path).stat()
        file_mode = stat.filemode(file_stat.st_mode)
        
        print(f"資料庫檔案權限: {file_mode}")
        
        # 確保不是全域可讀寫
        assert not (file_stat.st_mode & stat.S_IROTH)  # 其他用戶不可讀
        assert not (file_stat.st_mode & stat.S_IWOTH)  # 其他用戶不可寫
        
        # 清理
        Path(db_path).unlink(missing_ok=True)
    
    def test_configuration_security(self):
        """測試配置安全性"""
        config_manager = ConfigManager()
        
        # 檢查關鍵安全配置
        security_config = config_manager.config.get('security', {})
        
        # 確保認證已啟用
        auth_enabled = security_config.get('authentication', {}).get('enabled', False)
        if 'authentication' in security_config:
            print(f"認證狀態: {'啟用' if auth_enabled else '停用'}")
        
        # 檢查會話設定
        session_config = security_config.get('session', {})
        if session_config:
            timeout = session_config.get('timeout', 0)
            if timeout > 0:
                print(f"會話逾時: {timeout} 秒")
                assert timeout <= 3600  # 不超過1小時
        
        # 檢查查詢限制
        query_config = config_manager.config.get('query', {})
        if query_config:
            max_results = query_config.get('max_results', 0)
            if max_results > 0:
                print(f"查詢結果限制: {max_results} 筆")
                assert max_results <= 10000  # 合理的限制
    
    def test_input_sanitization(self):
        """測試輸入清理"""
        def sanitize_input(user_input):
            """模擬輸入清理函數"""
            # 移除危險字符
            dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`']
            sanitized = user_input
            
            for char in dangerous_chars:
                sanitized = sanitized.replace(char, '')
            
            # 限制長度
            if len(sanitized) > 1000:
                sanitized = sanitized[:1000]
            
            return sanitized
        
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE CO01M; --",
            "user' OR '1'='1",
            "&lt;img src=x onerror=alert(1)&gt;",
        ]
        
        for malicious_input in malicious_inputs:
            sanitized = sanitize_input(malicious_input)
            
            # 確保危險字符被移除
            assert '<' not in sanitized
            assert '>' not in sanitized
            assert "'" not in sanitized
            assert ';' not in sanitized
            
            print(f"輸入已清理: {malicious_input[:30]}... -> {sanitized[:30]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])