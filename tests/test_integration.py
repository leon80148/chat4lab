"""
系統整合測試

測試各模組間的整合功能，確保整個系統協同工作正常。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager
from src.modules.dbf_parser import ZhanWangDBFParser
from src.modules.llm_agent import LLMQueryAgent
from src.modules.query_templates import QueryTemplateManager


class TestSystemIntegration:
    """系統整合測試類"""
    
    @pytest.fixture
    def temp_db_path(self):
        """建立臨時資料庫"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # 清理
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def integrated_system(self, temp_db_path):
        """建立完整的整合系統"""
        # 配置管理器
        config_manager = ConfigManager()
        
        # 資料庫管理器
        db_config = config_manager.get_database_config()
        db_config['path'] = temp_db_path
        db_manager = DatabaseManager(temp_db_path, db_config)
        
        # 建立資料表
        db_manager.create_tables()
        db_manager.create_indexes()
        
        # LLM代理 (使用mock)
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        # 查詢範本管理器
        template_manager = QueryTemplateManager()
        
        # DBF解析器
        dbf_parser = ZhanWangDBFParser()
        
        return {
            'config_manager': config_manager,
            'db_manager': db_manager,
            'llm_agent': llm_agent,
            'template_manager': template_manager,
            'dbf_parser': dbf_parser
        }
    
    def test_config_to_database_integration(self, integrated_system):
        """測試配置管理器與資料庫管理器整合"""
        config_manager = integrated_system['config_manager']
        db_manager = integrated_system['db_manager']
        
        # 測試配置是否正確傳遞到資料庫管理器
        db_config = config_manager.get_database_config()
        
        assert db_manager.config['journal_mode'] == db_config['performance']['journal_mode']
        assert db_manager.config['cache_size'] == db_config['performance']['cache_size']
        
        # 測試資料庫連線
        result = db_manager.execute_query("SELECT 1 as test")
        assert len(result) == 1
        assert result.iloc[0]['test'] == 1
    
    def test_dbf_to_database_integration(self, integrated_system):
        """測試DBF解析器與資料庫整合"""
        db_manager = integrated_system['db_manager']
        dbf_parser = integrated_system['dbf_parser']
        
        # 建立測試資料
        test_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002'],
            'mname': ['測試病患一', '測試病患二'],
            'msex': ['M', 'F'],
            'mbirthdt': ['19800101', '19900215'],
            'mtelh': ['0912345678', '0987654321']
        })
        
        # 測試資料匯入
        success = db_manager.import_dbf_data('CO01M', test_data)
        assert success == True
        
        # 驗證資料是否正確匯入
        result = db_manager.execute_query("SELECT * FROM CO01M")
        assert len(result) == 2
        assert result.iloc[0]['mname'] == '測試病患一'
        assert result.iloc[1]['mname'] == '測試病患二'
    
    @patch('requests.post')
    def test_llm_to_database_integration(self, mock_post, integrated_system):
        """測試LLM代理與資料庫整合"""
        db_manager = integrated_system['db_manager']
        llm_agent = integrated_system['llm_agent']
        
        # 先插入測試資料
        test_data = pd.DataFrame({
            'kcstmr': ['0000001'],
            'mname': ['李小明'],
            'msex': ['M'],
            'mbirthdt': ['19800101']
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        # 模擬LLM回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'content': '```sql\nSELECT * FROM CO01M WHERE mname LIKE \'%李%\'\n```'
            }
        }
        mock_post.return_value = mock_response
        
        # 執行查詢
        result = llm_agent.process_query("查詢病患李小明")
        
        assert result.success == True
        assert result.result_count == 1
        assert len(result.results) == 1
        assert result.results[0]['mname'] == '李小明'
    
    def test_template_to_database_integration(self, integrated_system):
        """測試查詢範本與資料庫整合"""
        db_manager = integrated_system['db_manager']
        template_manager = integrated_system['template_manager']
        
        # 先插入測試資料
        test_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002'],
            'mname': ['王小華', '李小明'],
            'msex': ['F', 'M'],
            'mbirthdt': ['19850315', '19800101']
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        # 使用範本生成SQL
        sql = template_manager.generate_sql('patient_by_name', {'name': '王'})
        
        # 執行查詢
        result = db_manager.execute_query(sql)
        
        assert len(result) == 1
        assert result.iloc[0]['mname'] == '王小華'
    
    def test_complete_workflow_integration(self, integrated_system):
        """測試完整工作流程整合"""
        db_manager = integrated_system['db_manager']
        template_manager = integrated_system['template_manager']
        
        # 1. 匯入病患資料
        co01m_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002'],
            'mname': ['張醫師病患', '李醫師病患'],
            'msex': ['M', 'F'],
            'mbirthdt': ['19700101', '19850615']
        })
        db_manager.import_dbf_data('CO01M', co01m_data)
        
        # 2. 匯入就診資料
        co03m_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002'],
            'idate': ['20250120', '20250121'],
            'itime': ['0900', '1030'],
            'labno': ['E11', 'I10'],
            'ipk3': ['DOC001', 'DOC002']
        })
        db_manager.import_dbf_data('CO03M', co03m_data)
        
        # 3. 使用範本查詢就診記錄
        sql = template_manager.generate_sql('visits_by_date_range', {
            'start_date': '20250120',
            'end_date': '20250122'
        })
        
        result = db_manager.execute_query(sql)
        
        # 驗證結果
        assert len(result) == 2
        assert result.iloc[0]['mname'] in ['張醫師病患', '李醫師病患']
        assert result.iloc[1]['mname'] in ['張醫師病患', '李醫師病患']
    
    def test_error_handling_integration(self, integrated_system):
        """測試錯誤處理整合"""
        db_manager = integrated_system['db_manager']
        template_manager = integrated_system['template_manager']
        
        # 測試無效的範本參數
        with pytest.raises(ValueError):
            template_manager.generate_sql('patient_by_name', {})  # 缺少必要參數
        
        # 測試無效的SQL查詢
        with pytest.raises(Exception):
            db_manager.execute_query("INVALID SQL QUERY")
        
        # 測試SQL注入防護
        with pytest.raises(Exception):
            db_manager.execute_query("SELECT * FROM CO01M; DROP TABLE CO01M;")
    
    def test_performance_integration(self, integrated_system):
        """測試效能整合"""
        db_manager = integrated_system['db_manager']
        
        # 建立大量測試資料
        large_data = pd.DataFrame({
            'kcstmr': [f'{i:07d}' for i in range(1000)],
            'mname': [f'病患{i}' for i in range(1000)],
            'msex': ['M' if i % 2 == 0 else 'F' for i in range(1000)],
            'mbirthdt': ['19800101'] * 1000
        })
        
        # 測試大量資料匯入
        success = db_manager.import_dbf_data('CO01M', large_data)
        assert success == True
        
        # 測試查詢效能
        import time
        start_time = time.time()
        
        result = db_manager.execute_query("SELECT COUNT(*) as total FROM CO01M")
        
        execution_time = time.time() - start_time
        
        assert len(result) == 1
        assert result.iloc[0]['total'] == 1000
        assert execution_time < 1.0  # 應該在1秒內完成
    
    def test_data_consistency_integration(self, integrated_system):
        """測試資料一致性整合"""
        db_manager = integrated_system['db_manager']
        
        # 測試外鍵約束
        co01m_data = pd.DataFrame({
            'kcstmr': ['0000001'],
            'mname': ['測試病患'],
            'msex': ['M'],
            'mbirthdt': ['19800101']
        })
        db_manager.import_dbf_data('CO01M', co01m_data)
        
        # 插入關聯資料
        co03m_data = pd.DataFrame({
            'kcstmr': ['0000001'],
            'idate': ['20250120'],
            'itime': ['0900'],
            'labno': ['E11']
        })
        db_manager.import_dbf_data('CO03M', co03m_data)
        
        # 測試JOIN查詢
        result = db_manager.execute_query("""
            SELECT p.mname, v.idate, v.labno 
            FROM CO01M p 
            JOIN CO03M v ON p.kcstmr = v.kcstmr
        """)
        
        assert len(result) == 1
        assert result.iloc[0]['mname'] == '測試病患'
        assert result.iloc[0]['labno'] == 'E11'
    
    def test_concurrent_access_integration(self, integrated_system):
        """測試並發存取整合"""
        db_manager = integrated_system['db_manager']
        
        import threading
        import time
        
        results = []
        errors = []
        
        def query_worker():
            try:
                result = db_manager.execute_query("SELECT 1 as test")
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 建立多個並發查詢
        threads = []
        for i in range(10):
            thread = threading.Thread(target=query_worker)
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 驗證結果
        assert len(errors) == 0  # 不應該有錯誤
        assert len(results) == 10  # 所有查詢都應該成功
    
    def test_memory_usage_integration(self, integrated_system):
        """測試記憶體使用整合"""
        db_manager = integrated_system['db_manager']
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 執行大量查詢
        for i in range(100):
            result = db_manager.execute_query("SELECT 1 as test")
            assert len(result) == 1
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 記憶體增長應該在合理範圍內 (< 50MB)
        assert memory_increase < 50 * 1024 * 1024


class TestConfigurationIntegration:
    """配置整合測試"""
    
    def test_environment_override_integration(self):
        """測試環境變數覆蓋整合"""
        import os
        
        # 設置測試環境變數
        os.environ['DATABASE_PATH'] = '/tmp/test.db'
        os.environ['OLLAMA_MODEL'] = 'test-model'
        
        try:
            config_manager = ConfigManager()
            
            # 驗證環境變數是否正確覆蓋
            assert config_manager.get('database.path') == '/tmp/test.db'
            assert config_manager.get('llm.model') == 'test-model'
            
        finally:
            # 清理環境變數
            del os.environ['DATABASE_PATH']
            del os.environ['OLLAMA_MODEL']
    
    def test_config_validation_integration(self):
        """測試配置驗證整合"""
        config_manager = ConfigManager()
        
        # 測試必要配置項目是否存在
        required_configs = [
            'system.name',
            'database.path',
            'llm.model',
            'security.authentication.enabled'
        ]
        
        for config_key in required_configs:
            value = config_manager.get(config_key)
            assert value is not None, f"缺少必要配置: {config_key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])