"""
性能測試 (Performance Tests)

測試系統在各種負載條件下的性能表現，確保系統能夠滿足實際使用需求。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
import tempfile
import time
import threading
import multiprocessing
import psutil
import os
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager
from src.modules.dbf_parser import ZhanWangDBFParser
from src.modules.llm_agent import LLMQueryAgent
from src.modules.query_templates import QueryTemplateManager


class TestDatabasePerformance:
    """資料庫性能測試"""
    
    @pytest.fixture
    def performance_db(self):
        """建立性能測試資料庫"""
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
    
    def _generate_large_dataset(self, size: int) -> pd.DataFrame:
        """生成大量測試資料"""
        import random
        import string
        
        names = [f"病患{''.join(random.choices(string.ascii_letters, k=3))}{i}" for i in range(size)]
        
        return pd.DataFrame({
            'kcstmr': [f'{i:07d}' for i in range(size)],
            'mname': names,
            'msex': [random.choice(['M', 'F']) for _ in range(size)],
            'mbirthdt': [f'19{random.randint(50, 99):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}' for _ in range(size)],
            'mweight': [round(random.uniform(40, 120), 1) for _ in range(size)],
            'mheight': [random.randint(140, 200) for _ in range(size)]
        })
    
    def test_large_data_import_performance(self, performance_db):
        """測試大量資料匯入性能"""
        sizes = [1000, 5000, 10000]
        import_times = []
        
        for size in sizes:
            test_data = self._generate_large_dataset(size)
            
            start_time = time.time()
            success = performance_db.import_dbf_data('CO01M', test_data)
            import_time = time.time() - start_time
            
            assert success == True
            import_times.append(import_time)
            
            # 清理資料，為下次測試準備
            performance_db.execute_query("DELETE FROM CO01M")
            
            print(f"匯入 {size} 筆資料耗時: {import_time:.2f} 秒")
        
        # 驗證性能要求
        assert import_times[0] < 2.0  # 1000筆 < 2秒
        assert import_times[1] < 8.0  # 5000筆 < 8秒
        assert import_times[2] < 15.0 # 10000筆 < 15秒
    
    def test_query_performance_with_scale(self, performance_db):
        """測試不同資料規模下的查詢性能"""
        # 匯入測試資料
        test_data = self._generate_large_dataset(10000)
        performance_db.import_dbf_data('CO01M', test_data)
        
        queries = [
            ("簡單計數", "SELECT COUNT(*) as total FROM CO01M"),
            ("索引查詢", "SELECT * FROM CO01M WHERE kcstmr = '0001000' LIMIT 10"),
            ("範圍查詢", "SELECT * FROM CO01M WHERE mweight BETWEEN 60 AND 80 LIMIT 100"),
            ("模糊搜尋", "SELECT * FROM CO01M WHERE mname LIKE '%病患%' LIMIT 100"),
            ("聚合查詢", "SELECT msex, COUNT(*) as count, AVG(mweight) as avg_weight FROM CO01M GROUP BY msex"),
            ("排序查詢", "SELECT * FROM CO01M ORDER BY mweight DESC LIMIT 100")
        ]
        
        for query_name, sql in queries:
            times = []
            
            # 執行多次測試取平均值
            for _ in range(5):
                start_time = time.time()
                result = performance_db.execute_query(sql)
                execution_time = time.time() - start_time
                times.append(execution_time)
                
                assert len(result) >= 0  # 確保查詢成功
            
            avg_time = statistics.mean(times)
            print(f"{query_name}: 平均 {avg_time:.3f} 秒")
            
            # 性能要求
            if query_name == "簡單計數":
                assert avg_time < 0.1
            elif query_name == "索引查詢":
                assert avg_time < 0.05
            else:
                assert avg_time < 1.0
    
    def test_concurrent_query_performance(self, performance_db):
        """測試並發查詢性能"""
        # 匯入測試資料
        test_data = self._generate_large_dataset(5000)
        performance_db.import_dbf_data('CO01M', test_data)
        
        def execute_query(query_id):
            """執行單個查詢"""
            queries = [
                "SELECT COUNT(*) FROM CO01M",
                "SELECT * FROM CO01M WHERE msex = 'M' LIMIT 10",
                "SELECT * FROM CO01M WHERE mweight > 70 LIMIT 10",
                f"SELECT * FROM CO01M WHERE kcstmr = '{query_id:07d}' LIMIT 1"
            ]
            
            start_time = time.time()
            query = queries[query_id % len(queries)]
            result = performance_db.execute_query(query, user_id=f"user_{query_id}")
            execution_time = time.time() - start_time
            
            return {
                'query_id': query_id,
                'execution_time': execution_time,
                'result_count': len(result)
            }
        
        # 測試不同並發數量
        concurrent_levels = [5, 10, 20]
        
        for concurrent_count in concurrent_levels:
            start_time = time.time()
            results = []
            errors = []
            
            with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
                futures = [executor.submit(execute_query, i) for i in range(concurrent_count)]
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        errors.append(e)
            
            total_time = time.time() - start_time
            
            # 驗證結果
            assert len(errors) == 0, f"並發錯誤: {errors}"
            assert len(results) == concurrent_count
            
            avg_query_time = statistics.mean([r['execution_time'] for r in results])
            
            print(f"並發 {concurrent_count} 個查詢:")
            print(f"  總耗時: {total_time:.2f} 秒")
            print(f"  平均查詢時間: {avg_query_time:.3f} 秒")
            
            # 性能要求
            assert total_time < 5.0  # 總時間不超過5秒
            assert avg_query_time < 1.0  # 平均查詢時間不超過1秒


class TestLLMPerformance:
    """LLM性能測試"""
    
    @pytest.fixture
    def llm_performance_system(self):
        """建立LLM性能測試系統"""
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
            'mname': ['測試病患A', '測試病患B', '測試病患C'],
            'msex': ['M', 'F', 'M'],
            'mbirthdt': ['19800101', '19850315', '19750620']
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        yield llm_agent
        
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
    
    @patch('requests.post')
    def test_llm_response_time(self, mock_post, llm_performance_system):
        """測試LLM回應時間"""
        # 模擬不同複雜度的LLM回應
        responses = [
            "```sql\nSELECT * FROM CO01M WHERE mname LIKE '%測試%' LIMIT 100\n```",
            "```sql\nSELECT p.mname, v.idate FROM CO01M p JOIN CO03M v ON p.kcstmr = v.kcstmr LIMIT 100\n```",
            "```sql\nSELECT msex, COUNT(*) as count FROM CO01M GROUP BY msex LIMIT 100\n```"
        ]
        
        queries = [
            "查詢測試病患的基本資料",
            "查看病患的就診記錄",
            "統計男女病患數量"
        ]
        
        response_times = []
        
        for i, (query, response) in enumerate(zip(queries, responses)):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'message': {'content': response}
            }
            mock_post.return_value = mock_response
            
            start_time = time.time()
            result = llm_performance_system.process_query(query)
            response_time = time.time() - start_time
            
            response_times.append(response_time)
            
            assert result.success == True
            print(f"查詢 {i+1}: {response_time:.2f} 秒")
        
        avg_response_time = statistics.mean(response_times)
        print(f"平均回應時間: {avg_response_time:.2f} 秒")
        
        # 性能要求 (不包含實際LLM調用時間)
        assert avg_response_time < 5.0  # 平均5秒內完成
        assert max(response_times) < 10.0  # 最長不超過10秒
    
    @patch('requests.post')
    def test_llm_concurrent_processing(self, mock_post, llm_performance_system):
        """測試LLM並發處理能力"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {'content': "```sql\nSELECT * FROM CO01M LIMIT 10\n```"}
        }
        mock_post.return_value = mock_response
        
        def process_query(query_id):
            query = f"查詢病患資料{query_id}"
            start_time = time.time()
            result = llm_performance_system.process_query(
                query, 
                user_id=f"user_{query_id}"
            )
            execution_time = time.time() - start_time
            
            return {
                'query_id': query_id,
                'success': result.success,
                'execution_time': execution_time
            }
        
        concurrent_count = 5
        results = []
        errors = []
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            futures = [executor.submit(process_query, i) for i in range(concurrent_count)]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(e)
        
        total_time = time.time() - start_time
        
        # 驗證結果
        assert len(errors) == 0, f"並發處理錯誤: {errors}"
        assert len(results) == concurrent_count
        assert all(r['success'] for r in results)
        
        avg_time = statistics.mean([r['execution_time'] for r in results])
        
        print(f"並發處理 {concurrent_count} 個LLM查詢:")
        print(f"  總耗時: {total_time:.2f} 秒")
        print(f"  平均處理時間: {avg_time:.2f} 秒")
        
        # 性能要求
        assert total_time < 30.0  # 總時間不超過30秒
        assert avg_time < 10.0   # 平均處理時間不超過10秒


class TestSystemResourceUsage:
    """系統資源使用測試"""
    
    def test_memory_usage_under_load(self):
        """測試負載下的記憶體使用"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 建立多個資料庫連線和資料操作
        db_managers = []
        
        for i in range(5):
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            config_manager = ConfigManager()
            db_config = config_manager.get_database_config()
            db_config['path'] = db_path
            
            db_manager = DatabaseManager(db_path, db_config)
            db_manager.create_tables()
            
            # 插入測試資料
            test_data = pd.DataFrame({
                'kcstmr': [f'{j:07d}' for j in range(i*100, (i+1)*100)],
                'mname': [f'病患{j}' for j in range(i*100, (i+1)*100)],
                'msex': ['M' if j % 2 == 0 else 'F' for j in range(100)],
                'mbirthdt': ['19800101'] * 100
            })
            db_manager.import_dbf_data('CO01M', test_data)
            
            db_managers.append((db_manager, db_path))
        
        # 執行大量查詢操作
        for _ in range(100):
            for db_manager, _ in db_managers:
                result = db_manager.execute_query("SELECT COUNT(*) FROM CO01M")
                assert len(result) == 1
        
        # 檢查記憶體使用
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        print(f"記憶體增長: {memory_increase / 1024 / 1024:.2f} MB")
        
        # 清理資源
        for db_manager, db_path in db_managers:
            db_manager.close()
            Path(db_path).unlink(missing_ok=True)
        
        # 記憶體增長應該在合理範圍內 (< 200MB)
        assert memory_increase < 200 * 1024 * 1024
    
    def test_cpu_usage_efficiency(self):
        """測試CPU使用效率"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        
        # 準備大量資料
        large_data = pd.DataFrame({
            'kcstmr': [f'{i:07d}' for i in range(5000)],
            'mname': [f'病患{i}' for i in range(5000)],
            'msex': ['M' if i % 2 == 0 else 'F' for i in range(5000)],
            'mbirthdt': ['19800101'] * 5000
        })
        db_manager.import_dbf_data('CO01M', large_data)
        
        # 監控CPU使用率
        cpu_percentages = []
        
        def monitor_cpu():
            for _ in range(10):  # 監控10秒
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_percentages.append(cpu_percent)
        
        def execute_queries():
            complex_queries = [
                "SELECT msex, COUNT(*) FROM CO01M GROUP BY msex",
                "SELECT * FROM CO01M WHERE mweight > 70 ORDER BY mweight DESC LIMIT 100",
                "SELECT COUNT(DISTINCT msex) FROM CO01M",
                "SELECT * FROM CO01M WHERE mname LIKE '%病患1%' ORDER BY kcstmr LIMIT 50"
            ]
            
            for _ in range(25):  # 執行100個查詢
                for query in complex_queries:
                    result = db_manager.execute_query(query)
                    assert len(result) >= 0
        
        # 並行執行監控和查詢
        monitor_thread = threading.Thread(target=monitor_cpu)
        query_thread = threading.Thread(target=execute_queries)
        
        monitor_thread.start()
        query_thread.start()
        
        monitor_thread.join()
        query_thread.join()
        
        # 清理
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
        
        if cpu_percentages:
            avg_cpu = statistics.mean(cpu_percentages)
            max_cpu = max(cpu_percentages)
            
            print(f"平均CPU使用率: {avg_cpu:.1f}%")
            print(f"最高CPU使用率: {max_cpu:.1f}%")
            
            # CPU使用率應該在合理範圍內
            assert max_cpu < 80.0  # 最高不超過80%
            assert avg_cpu < 50.0  # 平均不超過50%


class TestPerformanceBenchmarks:
    """性能基準測試"""
    
    def test_system_startup_time(self):
        """測試系統啟動時間"""
        startup_times = []
        
        for _ in range(3):  # 測試3次取平均
            start_time = time.time()
            
            # 模擬系統啟動流程
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            config_manager = ConfigManager()
            db_config = config_manager.get_database_config()
            db_config['path'] = db_path
            
            db_manager = DatabaseManager(db_path, db_config)
            db_manager.create_tables()
            db_manager.create_indexes()
            
            template_manager = QueryTemplateManager()
            
            startup_time = time.time() - start_time
            startup_times.append(startup_time)
            
            # 清理
            db_manager.close()
            Path(db_path).unlink(missing_ok=True)
        
        avg_startup_time = statistics.mean(startup_times)
        print(f"平均系統啟動時間: {avg_startup_time:.2f} 秒")
        
        # 系統啟動應該在合理時間內完成
        assert avg_startup_time < 5.0  # 5秒內啟動完成
    
    def test_throughput_benchmark(self):
        """測試系統吞吐量基準"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        db_config['path'] = db_path
        
        db_manager = DatabaseManager(db_path, db_config)
        db_manager.create_tables()
        
        # 準備測試資料
        test_data = pd.DataFrame({
            'kcstmr': [f'{i:07d}' for i in range(1000)],
            'mname': [f'病患{i}' for i in range(1000)],
            'msex': ['M' if i % 2 == 0 else 'F' for i in range(1000)],
            'mbirthdt': ['19800101'] * 1000
        })
        db_manager.import_dbf_data('CO01M', test_data)
        
        # 測試查詢吞吐量
        queries_count = 100
        start_time = time.time()
        
        for i in range(queries_count):
            query = f"SELECT * FROM CO01M WHERE kcstmr = '{i%100:07d}' LIMIT 1"
            result = db_manager.execute_query(query)
            assert len(result) <= 1
        
        total_time = time.time() - start_time
        throughput = queries_count / total_time
        
        print(f"查詢吞吐量: {throughput:.1f} 查詢/秒")
        
        # 清理
        db_manager.close()
        Path(db_path).unlink(missing_ok=True)
        
        # 吞吐量基準
        assert throughput > 50.0  # 至少50查詢/秒
    
    def test_scalability_benchmark(self):
        """測試擴展性基準"""
        data_sizes = [100, 500, 1000, 2000]
        query_times = []
        
        for size in data_sizes:
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            config_manager = ConfigManager()
            db_config = config_manager.get_database_config()
            db_config['path'] = db_path
            
            db_manager = DatabaseManager(db_path, db_config)
            db_manager.create_tables()
            db_manager.create_indexes()
            
            # 準備不同大小的資料集
            test_data = pd.DataFrame({
                'kcstmr': [f'{i:07d}' for i in range(size)],
                'mname': [f'病患{i}' for i in range(size)],
                'msex': ['M' if i % 2 == 0 else 'F' for i in range(size)],
                'mbirthdt': ['19800101'] * size
            })
            db_manager.import_dbf_data('CO01M', test_data)
            
            # 測試查詢時間
            start_time = time.time()
            result = db_manager.execute_query("SELECT COUNT(*) FROM CO01M")
            query_time = time.time() - start_time
            
            query_times.append(query_time)
            assert result.iloc[0].iloc[0] == size
            
            # 清理
            db_manager.close()
            Path(db_path).unlink(missing_ok=True)
            
            print(f"資料量 {size}: 查詢時間 {query_time:.3f} 秒")
        
        # 檢查擴展性 - 查詢時間不應該隨資料量線性增長
        time_ratio = query_times[-1] / query_times[0]  # 最大/最小
        data_ratio = data_sizes[-1] / data_sizes[0]   # 最大/最小
        
        print(f"資料量增長 {data_ratio}x, 查詢時間增長 {time_ratio:.1f}x")
        
        # 查詢時間增長應該遠小於資料量增長（有索引優化）
        assert time_ratio < data_ratio / 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])