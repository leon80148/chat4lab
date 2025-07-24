"""
端到端測試 (E2E Tests)

模擬真實用戶場景，測試整個系統的端到端功能。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess
import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager
from src.modules.dbf_parser import ZhanWangDBFParser
from src.modules.llm_agent import LLMQueryAgent
from src.modules.query_templates import QueryTemplateManager


class TestEndToEndScenarios:
    """端到端場景測試"""
    
    @pytest.fixture
    def e2e_system(self):
        """建立端到端測試系統"""
        # 建立臨時資料庫
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # 初始化完整系統
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        db_manager.create_indexes()
        
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        template_manager = QueryTemplateManager()
        dbf_parser = ZhanWangDBFParser()
        
        # 建立測試資料
        self._setup_test_data(db_manager)
        
        yield {
            'config_manager': config_manager,
            'db_manager': db_manager,
            'llm_agent': llm_agent,
            'template_manager': template_manager,
            'dbf_parser': dbf_parser,
            'db_path': db_path
        }
        
        # 清理
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    def _setup_test_data(self, db_manager):
        """設置測試資料"""
        # 病患主資料
        co01m_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000002', '0000003', '0000004', '0000005'],
            'mname': ['李小明', '王小華', '張醫師', '陳護士', '林病患'],
            'msex': ['M', 'F', 'M', 'F', 'M'],
            'mbirthdt': ['19800101', '19850315', '19750620', '19900510', '19701025'],
            'mtelh': ['0912345678', '0987654321', '0923456789', '0934567890', '0945678901'],
            'mweight': [70.5, 55.2, 80.0, 60.5, 75.0],
            'mheight': [175, 160, 180, 165, 170]
        })
        db_manager.import_dbf_data('CO01M', co01m_data)
        
        # 就診記錄
        co03m_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000001', '0000002', '0000003', '0000004'],
            'idate': ['20250120', '20250115', '20250118', '20250119', '20250121'],
            'itime': ['0900', '1030', '1400', '0830', '1530'],
            'labno': ['E11', 'I10', 'J45', 'E11', 'M79'],
            'ipk3': ['DOC001', 'DOC001', 'DOC002', 'DOC001', 'DOC003'],
            'tot': [1200.0, 800.0, 1500.0, 1000.0, 600.0]
        })
        db_manager.import_dbf_data('CO03M', co03m_data)
        
        # 處方記錄
        co02m_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000001', '0000002', '0000003', '0000004'],
            'idate': ['20250120', '20250120', '20250118', '20250119', '20250121'],
            'itime': ['0900', '0900', '1400', '0830', '1530'],
            'dno': ['DRUG001', 'DRUG002', 'DRUG003', 'DRUG001', 'DRUG004'],
            'ptp': ['口服藥', '注射劑', '口服藥', '口服藥', '外用藥'],
            'pfq': ['TID', 'BID', 'QID', 'TID', 'BID'],
            'ptday': [7, 3, 5, 7, 14]
        })
        db_manager.import_dbf_data('CO02M', co02m_data)
        
        # 檢驗結果
        co18h_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000001', '0000002', '0000003', '0000004'],
            'hdate': ['20250120', '20250115', '20250118', '20250119', '20250121'],
            'htime': ['0930', '1100', '1430', '0900', '1600'],
            'hitem': ['GLU', 'HbA1c', 'CHOL', 'GLU', 'CRP'],
            'hdscp': ['血糖', '糖化血色素', '膽固醇', '血糖', 'C反應蛋白'],
            'hval': [150.0, 8.5, 220.0, 140.0, 5.2],
            'hresult': ['偏高', '偏高', '偏高', '正常', '正常']
        })
        db_manager.import_dbf_data('CO18H', co18h_data)
    
    def test_scenario_patient_lookup(self, e2e_system):
        """場景：醫師查詢病患基本資料"""
        template_manager = e2e_system['template_manager']
        db_manager = e2e_system['db_manager']
        
        # 步驟1：醫師想查詢李小明的基本資料
        sql = template_manager.generate_sql('patient_by_name', {'name': '李小明'})
        result = db_manager.execute_query(sql)
        
        # 驗證：應該找到李小明的資料
        assert len(result) == 1
        patient = result.iloc[0]
        assert patient['mname'] == '李小明'
        assert patient['msex'] == 'M'
        assert patient['mbirthdt'] == '19800101'
        
        # 步驟2：醫師查看更詳細資料
        detailed_sql = f"SELECT * FROM CO01M WHERE kcstmr = '{patient['kcstmr']}'"
        detailed_result = db_manager.execute_query(detailed_sql)
        
        assert len(detailed_result) == 1
        assert detailed_result.iloc[0]['mtelh'] == '0912345678'
        assert detailed_result.iloc[0]['mweight'] == 70.5
    
    def test_scenario_medical_history_review(self, e2e_system):
        """場景：醫師查看病患就診歷史"""
        template_manager = e2e_system['template_manager']
        db_manager = e2e_system['db_manager']
        
        # 步驟1：查詢李小明(0000001)的就診記錄
        sql = template_manager.generate_sql('visits_by_patient', {
            'patient_id': '0000001'
        })
        visits = db_manager.execute_query(sql)
        
        # 驗證：李小明應該有2次就診記錄
        assert len(visits) == 2
        visit_dates = visits['idate'].tolist()
        assert '20250120' in visit_dates
        assert '20250115' in visit_dates
        
        # 步驟2：查看特定日期的詳細資料
        detailed_sql = """
            SELECT v.idate, v.labno, v.ipk3, v.tot,
                   p.pfq, p.ptday, p.dno
            FROM CO03M v
            LEFT JOIN CO02M p ON v.kcstmr = p.kcstmr AND v.idate = p.idate
            WHERE v.kcstmr = '0000001' AND v.idate = '20250120'
        """
        details = db_manager.execute_query(detailed_sql)
        
        assert len(details) >= 1
        assert details.iloc[0]['labno'] == 'E11'  # 糖尿病診斷
    
    def test_scenario_lab_results_tracking(self, e2e_system):
        """場景：追蹤病患檢驗結果趨勢"""
        template_manager = e2e_system['template_manager']
        db_manager = e2e_system['db_manager']
        
        # 步驟1：查詢李小明的檢驗結果
        sql = template_manager.generate_sql('lab_results_by_patient_item', {
            'patient_id': '0000001',
            'lab_item': '血糖'
        })
        lab_results = db_manager.execute_query(sql)
        
        # 驗證：應該找到血糖檢驗記錄
        assert len(lab_results) >= 1
        
        # 步驟2：分析檢驗趨勢
        trend_sql = """
            SELECT hdate, hval, hresult
            FROM CO18H
            WHERE kcstmr = '0000001' AND hdscp LIKE '%血糖%'
            ORDER BY hdate ASC
        """
        trend = db_manager.execute_query(trend_sql)
        
        assert len(trend) >= 1
        # 驗證數值合理性
        for _, row in trend.iterrows():
            assert row['hval'] > 0
            assert row['hval'] < 500  # 合理的血糖範圍
    
    def test_scenario_prescription_management(self, e2e_system):
        """場景：處方管理和藥物查詢"""
        template_manager = e2e_system['template_manager']
        db_manager = e2e_system['db_manager']
        
        # 步驟1：查詢特定藥物的處方記錄
        sql = template_manager.generate_sql('prescriptions_by_drug', {
            'drug_code': 'DRUG001'
        })
        prescriptions = db_manager.execute_query(sql)
        
        # 驗證：DRUG001應該被開立給多位病患
        assert len(prescriptions) >= 2
        
        # 步驟2：查詢病患的完整用藥記錄
        patient_meds_sql = """
            SELECT p.idate, p.dno, p.ptp, p.pfq, p.ptday
            FROM CO02M p
            WHERE p.kcstmr = '0000001'
            ORDER BY p.idate DESC
        """
        patient_meds = db_manager.execute_query(patient_meds_sql)
        
        assert len(patient_meds) >= 2
        # 驗證藥物資訊完整性
        for _, med in patient_meds.iterrows():
            assert med['dno'] is not None
            assert med['ptday'] > 0
    
    def test_scenario_statistical_analysis(self, e2e_system):
        """場景：統計分析和報表生成"""
        db_manager = e2e_system['db_manager']
        
        # 步驟1：病患年齡分布統計
        age_stats_sql = """
            SELECT 
                CASE 
                    WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) < 30 THEN '青年'
                    WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) < 60 THEN '中年'
                    ELSE '老年'
                END as age_group,
                COUNT(*) as count
            FROM CO01M
            GROUP BY age_group
        """
        age_stats = db_manager.execute_query(age_stats_sql)
        
        assert len(age_stats) >= 1
        total_patients = age_stats['count'].sum()
        assert total_patients == 5  # 我們有5個測試病患
        
        # 步驟2：就診頻率統計
        visit_stats_sql = """
            SELECT 
                substr(idate, 1, 6) as month,
                COUNT(*) as visit_count,
                COUNT(DISTINCT kcstmr) as unique_patients
            FROM CO03M
            GROUP BY substr(idate, 1, 6)
            ORDER BY month
        """
        visit_stats = db_manager.execute_query(visit_stats_sql)
        
        assert len(visit_stats) >= 1
        for _, stat in visit_stats.iterrows():
            assert stat['visit_count'] >= stat['unique_patients']
    
    @patch('requests.post')
    def test_scenario_natural_language_query(self, mock_post, e2e_system):
        """場景：自然語言查詢完整流程"""
        llm_agent = e2e_system['llm_agent']
        
        # 模擬LLM回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'content': '''```sql
SELECT p.mname, v.idate, v.labno 
FROM CO01M p 
JOIN CO03M v ON p.kcstmr = v.kcstmr 
WHERE p.mname LIKE '%李%' 
ORDER BY v.idate DESC 
LIMIT 100
```'''
            }
        }
        mock_post.return_value = mock_response
        
        # 步驟1：用戶輸入自然語言查詢
        query = "查詢姓李的病患最近的就診記錄"
        
        # 步驟2：LLM處理並生成SQL
        result = llm_agent.process_query(query)
        
        # 驗證：查詢應該成功
        assert result.success == True
        assert result.result_count >= 1
        assert len(result.results) >= 1
        
        # 驗證結果內容
        patient_names = [r['mname'] for r in result.results]
        assert any('李' in name for name in patient_names)
        
        # 步驟3：驗證生成的SQL是安全的
        assert 'SELECT' in result.sql_query.upper()
        assert 'DROP' not in result.sql_query.upper()
        assert 'DELETE' not in result.sql_query.upper()
    
    def test_scenario_data_export_workflow(self, e2e_system):
        """場景：資料匯出工作流程"""
        db_manager = e2e_system['db_manager']
        
        # 步驟1：查詢要匯出的資料
        export_sql = """
            SELECT p.kcstmr, p.mname, p.msex, 
                   v.idate, v.labno, v.tot
            FROM CO01M p
            JOIN CO03M v ON p.kcstmr = v.kcstmr
            WHERE v.idate >= '20250118'
            ORDER BY v.idate DESC
        """
        export_data = db_manager.execute_query(export_sql)
        
        assert len(export_data) >= 1
        
        # 步驟2：驗證匯出資料的完整性
        required_columns = ['kcstmr', 'mname', 'msex', 'idate', 'labno', 'tot']
        for col in required_columns:
            assert col in export_data.columns
        
        # 步驟3：驗證敏感資料處理
        # 確認沒有包含敏感欄位如身分證字號
        assert 'mpersonid' not in export_data.columns
        
        # 步驟4：模擬CSV匯出
        csv_content = export_data.to_csv(index=False)
        assert len(csv_content) > 0
        assert 'kcstmr,mname' in csv_content
    
    def test_scenario_system_monitoring(self, e2e_system):
        """場景：系統監控和健康檢查"""
        db_manager = e2e_system['db_manager']
        
        # 步驟1：檢查資料庫狀態
        db_stats = db_manager.get_table_stats()
        
        assert 'tables' in db_stats
        assert 'CO01M' in db_stats['tables']
        assert 'CO02M' in db_stats['tables']
        assert 'CO03M' in db_stats['tables']
        assert 'CO18H' in db_stats['tables']
        
        # 驗證資料表記錄數
        assert db_stats['tables']['CO01M']['record_count'] == 5
        assert db_stats['tables']['CO03M']['record_count'] == 5
        
        # 步驟2：檢查查詢效能
        start_time = time.time()
        test_query = "SELECT COUNT(*) as total FROM CO01M"
        result = db_manager.execute_query(test_query)
        execution_time = time.time() - start_time
        
        assert execution_time < 0.1  # 應該很快完成
        assert result.iloc[0]['total'] == 5
        
        # 步驟3：檢查系統資源使用
        query_stats = db_stats['query_stats']
        assert 'queries_executed' in query_stats
        assert query_stats['queries_executed'] >= 0
    
    def test_scenario_error_recovery(self, e2e_system):
        """場景：錯誤處理和系統恢復"""
        db_manager = e2e_system['db_manager']
        template_manager = e2e_system['template_manager']
        
        # 步驟1：嘗試無效查詢
        with pytest.raises(Exception):
            db_manager.execute_query("SELECT * FROM NonExistentTable")
        
        # 步驟2：驗證系統仍然正常工作
        normal_query = "SELECT COUNT(*) as total FROM CO01M"
        result = db_manager.execute_query(normal_query)
        assert result.iloc[0]['total'] == 5
        
        # 步驟3：測試範本參數錯誤
        with pytest.raises(ValueError):
            template_manager.generate_sql('patient_by_name', {})  # 缺少必要參數
        
        # 步驟4：驗證系統狀態正常
        sql = template_manager.generate_sql('patient_by_name', {'name': '李'})
        result = db_manager.execute_query(sql)
        assert len(result) >= 1
    
    def test_scenario_concurrent_users(self, e2e_system):
        """場景：多用戶並發使用"""
        db_manager = e2e_system['db_manager']
        
        import threading
        import random
        
        results = []
        errors = []
        
        def user_query(user_id):
            try:
                # 模擬不同用戶的查詢
                queries = [
                    "SELECT COUNT(*) as total FROM CO01M",
                    "SELECT COUNT(*) as total FROM CO03M",
                    "SELECT COUNT(*) as total FROM CO02M",
                    "SELECT COUNT(*) as total FROM CO18H"
                ]
                
                query = random.choice(queries)
                result = db_manager.execute_query(query, user_id=f"user_{user_id}")
                results.append((user_id, result))
                
            except Exception as e:
                errors.append((user_id, e))
        
        # 建立10個並發用戶
        threads = []
        for i in range(10):
            thread = threading.Thread(target=user_query, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有用戶完成
        for thread in threads:
            thread.join()
        
        # 驗證結果
        assert len(errors) == 0, f"並發錯誤: {errors}"
        assert len(results) == 10
        
        # 驗證每個查詢都有正確結果
        for user_id, result in results:
            assert len(result) == 1
            assert result.iloc[0]['total'] >= 0


class TestEndToEndPerformance:
    """端到端效能測試"""
    
    @pytest.fixture
    def performance_system(self):
        """建立效能測試系統"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        db_manager.create_indexes()
        
        yield db_manager
        
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    def test_large_dataset_performance(self, performance_system):
        """測試大資料集效能"""
        db_manager = performance_system
        
        # 建立大量測試資料 (10,000筆)
        large_data = pd.DataFrame({
            'kcstmr': [f'{i:07d}' for i in range(10000)],
            'mname': [f'病患{i}' for i in range(10000)],
            'msex': ['M' if i % 2 == 0 else 'F' for i in range(10000)],
            'mbirthdt': ['19800101'] * 10000,
            'mweight': [70.0 + i % 30 for i in range(10000)],
            'mheight': [160.0 + i % 40 for i in range(10000)]
        })
        
        # 測試大量資料匯入效能
        start_time = time.time()
        success = db_manager.import_dbf_data('CO01M', large_data)
        import_time = time.time() - start_time
        
        assert success == True
        assert import_time < 10.0  # 應該在10秒內完成
        
        # 測試大量資料查詢效能
        start_time = time.time()
        result = db_manager.execute_query("SELECT COUNT(*) as total FROM CO01M")
        query_time = time.time() - start_time
        
        assert result.iloc[0]['total'] == 10000
        assert query_time < 0.5  # 計數查詢應該很快
        
        # 測試複雜查詢效能
        start_time = time.time()
        complex_result = db_manager.execute_query("""
            SELECT msex, COUNT(*) as count, AVG(mweight) as avg_weight
            FROM CO01M
            GROUP BY msex
            ORDER BY count DESC
        """)
        complex_time = time.time() - start_time
        
        assert len(complex_result) == 2  # M, F
        assert complex_time < 1.0  # 複雜查詢應該在1秒內
    
    def test_memory_efficiency(self, performance_system):
        """測試記憶體效率"""
        import psutil
        import os
        
        db_manager = performance_system
        process = psutil.Process(os.getpid())
        
        # 記錄初始記憶體使用
        initial_memory = process.memory_info().rss
        
        # 執行大量查詢操作
        for i in range(1000):
            result = db_manager.execute_query("SELECT 1 as test")
            assert len(result) == 1
        
        # 檢查記憶體使用
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 記憶體增長應該在合理範圍內 (< 100MB)
        assert memory_increase < 100 * 1024 * 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])