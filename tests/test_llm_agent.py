"""
LLM查詢代理測試

測試LLM查詢代理的各種功能，包括自然語言處理、
SQL生成、安全性驗證等。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.modules.llm_agent import (
    LLMQueryAgent, 
    MedicalTermsMapper,
    QueryResult,
    QueryValidator
)
from src.modules.db_manager import DatabaseManager


class TestMedicalTermsMapper:
    """醫療術語對應器測試"""
    
    @pytest.fixture
    def mapper(self):
        """建立術語對應器實例"""
        return MedicalTermsMapper()
    
    def test_medical_terms_mapping(self, mapper):
        """測試醫療術語對應"""
        assert mapper.medical_terms["病歷號"] == "kcstmr"
        assert mapper.medical_terms["姓名"] == "mname"
        assert mapper.medical_terms["性別"] == "msex"
        assert mapper.medical_terms["出生日期"] == "mbirthdt"
    
    def test_common_queries_templates(self, mapper):
        """測試常用查詢範本"""
        assert "病患基本資料" in mapper.common_queries
        assert "就診記錄" in mapper.common_queries
        assert "處方記錄" in mapper.common_queries
        assert "檢驗結果" in mapper.common_queries
    
    def test_condition_patterns(self, mapper):
        """測試條件模式"""
        assert r"(\d+)歲以上" in mapper.condition_patterns
        assert r"最近(\d+)天" in mapper.condition_patterns
        assert r"(\d{4})年" in mapper.condition_patterns


class TestLLMQueryAgent:
    """LLM查詢代理測試"""
    
    @pytest.fixture
    def mock_db_manager(self):
        """模擬資料庫管理器"""
        mock_db = Mock(spec=DatabaseManager)
        return mock_db
    
    @pytest.fixture
    def config(self):
        """LLM配置"""
        return {
            'base_url': 'http://localhost:11434',
            'model': 'gemma2:9b-instruct-q4_0',
            'parameters': {
                'temperature': 0.1,
                'max_tokens': 2048
            }
        }
    
    @pytest.fixture
    def agent(self, mock_db_manager, config):
        """建立LLM查詢代理實例"""
        return LLMQueryAgent(mock_db_manager, config)
    
    def test_agent_initialization(self, agent, config):
        """測試代理初始化"""
        assert agent.model == config['model']
        assert agent.base_url == config['base_url']
        assert agent.temperature == config['parameters']['temperature']
        assert isinstance(agent.terms_mapper, MedicalTermsMapper)
        assert agent.stats['total_queries'] == 0
    
    def test_system_prompt_generation(self, agent):
        """測試系統提示詞生成"""
        prompt = agent._get_system_prompt()
        
        assert "診所AI查詢助手" in prompt
        assert "CO01M" in prompt
        assert "CO02M" in prompt
        assert "CO03M" in prompt
        assert "CO18H" in prompt
        assert "只能生成SELECT查詢" in prompt
    
    @patch('requests.post')
    def test_call_llm_success(self, mock_post, agent):
        """測試成功呼叫LLM"""
        # 設置模擬回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'content': 'SELECT * FROM CO01M WHERE mname LIKE \'%測試%\''
            }
        }
        mock_post.return_value = mock_response
        
        # 執行測試
        result = agent._call_llm("系統提示", "查詢測試病患")
        
        # 驗證結果
        assert "SELECT * FROM CO01M" in result
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_call_llm_connection_error(self, mock_post, agent):
        """測試LLM連線錯誤"""
        mock_post.side_effect = Exception("Connection error")
        
        with pytest.raises(Exception, match="無法連接到LLM服務"):
            agent._call_llm("系統提示", "查詢測試")
    
    def test_extract_sql_from_response_success(self, agent):
        """測試成功提取SQL語句"""
        responses = [
            "```sql\nSELECT * FROM CO01M WHERE mname LIKE '%測試%'\n```",
            "```\nSELECT * FROM CO01M WHERE mname LIKE '%測試%'\n```",
            "這是查詢:\nSELECT * FROM CO01M WHERE mname LIKE '%測試%'",
        ]
        
        for response in responses:
            sql = agent._extract_sql_from_response(response)
            assert sql.startswith("SELECT")
            assert "CO01M" in sql
    
    def test_extract_sql_from_response_failure(self, agent):
        """測試提取SQL語句失敗"""
        invalid_responses = [
            "沒有SQL語句的回應",
            "```python\nprint('hello')\n```",
            "DELETE FROM CO01M",
        ]
        
        for response in invalid_responses:
            with pytest.raises(Exception, match="無法從LLM回應中提取有效的SQL語句"):
                agent._extract_sql_from_response(response)
    
    def test_preprocess_query(self, agent):
        """測試查詢預處理"""
        original_query = "查詢   病患   李小明的基本資料"
        processed = agent._preprocess_query(original_query)
        
        assert "查詢 病患" in processed
        assert "姓名(mname)" in processed
    
    def test_validate_and_enhance_sql_success(self, agent):
        """測試SQL驗證和增強成功"""
        sql = "SELECT * FROM CO01M WHERE mname LIKE '%測試%'"
        enhanced_sql = agent._validate_and_enhance_sql(sql)
        
        assert enhanced_sql.startswith("SELECT")
        assert "LIMIT" in enhanced_sql
    
    def test_validate_and_enhance_sql_failure(self, agent):
        """測試SQL驗證失敗"""
        invalid_sqls = [
            "DELETE FROM CO01M",
            "UPDATE CO01M SET mname = '測試'",
            "DROP TABLE CO01M",
        ]
        
        for sql in invalid_sqls:
            with pytest.raises(Exception, match="只允許SELECT查詢"):
                agent._validate_and_enhance_sql(sql)
    
    def test_validate_and_enhance_sql_limit_control(self, agent):
        """測試SQL LIMIT控制"""
        # 沒有LIMIT的查詢
        sql1 = "SELECT * FROM CO01M"
        enhanced1 = agent._validate_and_enhance_sql(sql1)
        assert "LIMIT 1000" in enhanced1
        
        # 超過限制的查詢
        sql2 = "SELECT * FROM CO01M LIMIT 2000"
        enhanced2 = agent._validate_and_enhance_sql(sql2)
        assert "LIMIT 1000" in enhanced2
        assert "LIMIT 2000" not in enhanced2
    
    def test_interpret_results(self, agent):
        """測試結果解釋"""
        test_cases = [
            ("查詢病患資料", [{"kcstmr": "001"}], "找到 1 位病患的資料"),
            ("查看就診記錄", [{"idate": "20250124"}] * 3, "找到 3 次就診記錄"),
            ("查詢處方記錄", [{"dno": "DRUG001"}] * 2, "找到 2 筆處方記錄"),
            ("檢驗結果查詢", [{"hitem": "GLU"}] * 5, "找到 5 項檢驗結果"),
            ("其他查詢", [{"data": "test"}], "查詢完成，共找到 1 筆資料"),
        ]
        
        for query, results, expected in test_cases:
            interpretation = agent._interpret_results(query, results)
            assert expected in interpretation
    
    def test_interpret_results_empty(self, agent):
        """測試空結果解釋"""
        interpretation = agent._interpret_results("任何查詢", [])
        assert "未找到符合條件的資料" in interpretation
    
    @patch.object(LLMQueryAgent, '_call_llm')
    @patch.object(LLMQueryAgent, '_extract_sql_from_response')
    @patch.object(LLMQueryAgent, '_validate_and_enhance_sql')
    def test_process_query_success(self, mock_validate, mock_extract, mock_call_llm, agent, mock_db_manager):
        """測試成功處理查詢"""
        # 設置模擬
        mock_call_llm.return_value = "```sql\nSELECT * FROM CO01M\n```"
        mock_extract.return_value = "SELECT * FROM CO01M"
        mock_validate.return_value = "SELECT * FROM CO01M LIMIT 1000"
        
        # 模擬資料庫結果
        mock_df = pd.DataFrame([
            {"kcstmr": "001", "mname": "測試病患"},
            {"kcstmr": "002", "mname": "測試病患二"}
        ])
        mock_db_manager.execute_query.return_value = mock_df
        
        # 執行測試
        result = agent.process_query("查詢病患資料")
        
        # 驗證結果
        assert result.success == True
        assert result.result_count == 2
        assert len(result.results) == 2
        assert "SELECT * FROM CO01M" in result.sql_query
        assert agent.stats['successful_queries'] == 1
    
    @patch.object(LLMQueryAgent, '_call_llm')
    def test_process_query_llm_failure(self, mock_call_llm, agent):
        """測試LLM失敗處理"""
        mock_call_llm.side_effect = Exception("LLM服務不可用")
        
        result = agent.process_query("查詢病患資料")
        
        assert result.success == False
        assert "LLM服務不可用" in result.error_message
        assert agent.stats['failed_queries'] == 1
    
    def test_get_query_suggestions(self, agent):
        """測試查詢建議"""
        suggestions = agent.get_query_suggestions()
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert any("病患" in s for s in suggestions)
        assert any("就診" in s for s in suggestions)
        assert any("處方" in s for s in suggestions)
        assert any("檢驗" in s for s in suggestions)
    
    def test_get_statistics(self, agent):
        """測試統計資訊獲取"""
        # 設置一些統計資料
        agent.stats['total_queries'] = 10
        agent.stats['successful_queries'] = 8
        agent.stats['failed_queries'] = 2
        agent.stats['avg_response_time'] = 1.5
        
        stats = agent.get_statistics()
        
        assert stats['total_queries'] == 10
        assert stats['successful_queries'] == 8
        assert stats['failed_queries'] == 2
        assert stats['success_rate'] == 0.8
        assert 'model_info' in stats
        assert stats['model_info']['model'] == agent.model
    
    def test_clear_statistics(self, agent):
        """測試清除統計資訊"""
        # 設置統計資料
        agent.stats['total_queries'] = 5
        agent.stats['successful_queries'] = 3
        
        # 清除統計
        agent.clear_statistics()
        
        assert agent.stats['total_queries'] == 0
        assert agent.stats['successful_queries'] == 0
        assert agent.stats['failed_queries'] == 0


class TestQueryValidator:
    """查詢驗證器測試"""
    
    def test_validate_medical_query_success(self):
        """測試醫療查詢驗證成功"""
        valid_queries = [
            "查詢病患李小明的基本資料",
            "顯示最近一週的就診記錄",
            "找出糖尿病診斷的病患",
            "查看血糖檢驗結果",
        ]
        
        for query in valid_queries:
            is_valid, error = QueryValidator.validate_medical_query(query)
            assert is_valid == True
            assert error == ""
    
    def test_validate_medical_query_failure(self):
        """測試醫療查詢驗證失敗"""
        invalid_queries = [
            "今天天氣如何",  # 非醫療相關
            "你好",         # 太短
            "a" * 501,      # 太長
        ]
        
        for query in invalid_queries:
            is_valid, error = QueryValidator.validate_medical_query(query)
            assert is_valid == False
            assert error != ""
    
    def test_validate_sql_safety_success(self):
        """測試SQL安全性驗證成功"""
        safe_sqls = [
            "SELECT * FROM CO01M WHERE mname LIKE '%測試%'",
            "SELECT kcstmr, mname FROM CO01M ORDER BY mname",
            "SELECT COUNT(*) FROM CO03M WHERE idate >= '20250101'",
        ]
        
        for sql in safe_sqls:
            is_safe, error = QueryValidator.validate_sql_safety(sql)
            assert is_safe == True
            assert error == ""
    
    def test_validate_sql_safety_failure(self):
        """測試SQL安全性驗證失敗"""
        dangerous_sqls = [
            "DROP TABLE CO01M",
            "DELETE FROM CO01M WHERE kcstmr = '001'",
            "UPDATE CO01M SET mname = '測試'",
            "INSERT INTO CO01M VALUES ('001', '測試')",
            "SELECT * FROM CO01M; DROP TABLE CO01M;",
            "SELECT * FROM CO01M -- 註釋",
            "SELECT * FROM CO01M /* 多行註釋 */",
        ]
        
        for sql in dangerous_sqls:
            is_safe, error = QueryValidator.validate_sql_safety(sql)
            assert is_safe == False
            assert error != ""


class TestQueryResult:
    """查詢結果測試"""
    
    def test_query_result_creation(self):
        """測試查詢結果建立"""
        result = QueryResult(
            success=True,
            sql_query="SELECT * FROM CO01M",
            results=[{"kcstmr": "001", "mname": "測試"}],
            execution_time=1.5,
            result_count=1,
            interpretation="找到1位病患"
        )
        
        assert result.success == True
        assert result.sql_query == "SELECT * FROM CO01M"
        assert len(result.results) == 1
        assert result.execution_time == 1.5
        assert result.result_count == 1
        assert "找到1位病患" in result.interpretation
    
    def test_query_result_error(self):
        """測試錯誤查詢結果"""
        result = QueryResult(
            success=False,
            sql_query="",
            error_message="SQL語法錯誤"
        )
        
        assert result.success == False
        assert result.sql_query == ""
        assert result.error_message == "SQL語法錯誤"
        assert result.results is None