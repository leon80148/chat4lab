"""
查詢範本系統測試

測試查詢範本管理器的各種功能，包括範本載入、
參數處理、SQL生成等。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
from datetime import datetime

from src.modules.query_templates import (
    QueryTemplate,
    QueryTemplateManager
)


class TestQueryTemplate:
    """查詢範本類別測試"""
    
    def test_query_template_creation(self):
        """測試查詢範本建立"""
        template = QueryTemplate(
            id="test_template",
            name="測試範本",
            description="這是一個測試範本",
            category="測試類別",
            sql_template="SELECT * FROM CO01M WHERE mname LIKE '%{name}%'",
            parameters=[
                {"name": "name", "type": "string", "required": True, "description": "病患姓名"}
            ],
            example_values={"name": "測試"},
            tags=["測試", "病患"]
        )
        
        assert template.id == "test_template"
        assert template.name == "測試範本"
        assert template.category == "測試類別"
        assert len(template.parameters) == 1
        assert template.parameters[0]["name"] == "name"
        assert "測試" in template.tags


class TestQueryTemplateManager:
    """查詢範本管理器測試"""
    
    @pytest.fixture
    def manager(self):
        """建立範本管理器實例"""
        return QueryTemplateManager()
    
    def test_manager_initialization(self, manager):
        """測試管理器初始化"""
        assert len(manager.templates) > 0
        assert "patient_by_name" in manager.templates
        assert "visits_by_date_range" in manager.templates
        assert "prescriptions_by_drug" in manager.templates
        assert "lab_results_by_item" in manager.templates
    
    def test_get_template_success(self, manager):
        """測試成功獲取範本"""
        template = manager.get_template("patient_by_name")
        
        assert template is not None
        assert template.id == "patient_by_name"
        assert template.name == "依姓名查詢病患"
        assert template.category == "病患資料"
        assert len(template.parameters) > 0
    
    def test_get_template_not_found(self, manager):
        """測試獲取不存在的範本"""
        template = manager.get_template("nonexistent_template")
        assert template is None
    
    def test_list_templates_all(self, manager):
        """測試列出所有範本"""
        templates = manager.list_templates()
        
        assert len(templates) > 0
        assert all(isinstance(t, QueryTemplate) for t in templates)
        # 檢查是否按名稱排序
        names = [t.name for t in templates]
        assert names == sorted(names)
    
    def test_list_templates_by_category(self, manager):
        """測試按類別篩選範本"""
        patient_templates = manager.list_templates(category="病患資料")
        
        assert len(patient_templates) > 0
        assert all(t.category == "病患資料" for t in patient_templates)
    
    def test_list_templates_by_tags(self, manager):
        """測試按標籤篩選範本"""
        lab_templates = manager.list_templates(tags=["檢驗"])
        
        assert len(lab_templates) > 0
        assert all(any("檢驗" in tag for tag in t.tags) for t in lab_templates)
    
    def test_get_categories(self, manager):
        """測試獲取所有類別"""
        categories = manager.get_categories()
        
        assert len(categories) > 0
        assert "病患資料" in categories
        assert "就診記錄" in categories
        assert "處方記錄" in categories
        assert "檢驗結果" in categories
        assert "統計分析" in categories
        # 檢查是否排序
        assert categories == sorted(categories)
    
    def test_search_templates(self, manager):
        """測試搜尋範本"""
        # 按名稱搜尋
        results1 = manager.search_templates("病患")
        assert len(results1) > 0
        assert all("病患" in t.name or "病患" in t.description or "病患" in t.tags 
                  for t in results1)
        
        # 按描述搜尋
        results2 = manager.search_templates("檢驗")
        assert len(results2) > 0
        
        # 按標籤搜尋
        results3 = manager.search_templates("統計")
        assert len(results3) > 0
    
    def test_generate_sql_success(self, manager):
        """測試成功生成SQL"""
        # 測試病患姓名查詢
        sql1 = manager.generate_sql("patient_by_name", {"name": "李小明"})
        
        assert "SELECT" in sql1
        assert "CO01M" in sql1
        assert "李小明" in sql1
        assert "LIMIT" in sql1
        
        # 測試帶預設值的查詢
        sql2 = manager.generate_sql("patient_by_name", {"name": "王小華", "limit": 20})
        
        assert "王小華" in sql2
        assert "LIMIT 20" in sql2 or "20" in sql2
    
    def test_generate_sql_missing_required_param(self, manager):
        """測試缺少必要參數"""
        with pytest.raises(ValueError, match="缺少必要參數"):
            manager.generate_sql("patient_by_name", {})
    
    def test_generate_sql_template_not_found(self, manager):
        """測試範本不存在"""
        with pytest.raises(ValueError, match="範本不存在"):
            manager.generate_sql("nonexistent_template", {"param": "value"})
    
    def test_generate_sql_with_default_values(self, manager):
        """測試使用預設值生成SQL"""
        sql = manager.generate_sql("patients_by_age_range", {
            "min_age": 30,
            "max_age": 50
            # limit 使用預設值
        })
        
        assert "BETWEEN 30 AND 50" in sql
        assert "100" in sql  # 預設limit值
    
    def test_generate_sql_date_validation(self, manager):
        """測試日期參數驗證"""
        # 正確的日期格式
        sql1 = manager.generate_sql("visits_by_date_range", {
            "start_date": "20250101",
            "end_date": "20250131"
        })
        
        assert "20250101" in sql1
        assert "20250131" in sql1
        
        # 錯誤的日期格式
        with pytest.raises(ValueError, match="必須是YYYYMMDD格式"):
            manager.generate_sql("visits_by_date_range", {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31"
            })
    
    def test_generate_sql_integer_validation(self, manager):
        """測試整數參數驗證"""
        # 正確的整數
        sql1 = manager.generate_sql("patients_by_age_range", {
            "min_age": 20,
            "max_age": 60,
            "limit": 50
        })
        
        assert "20" in sql1
        assert "60" in sql1
        
        # 字串數字（應該被轉換）
        sql2 = manager.generate_sql("patients_by_age_range", {
            "min_age": "25",
            "max_age": "55"
        })
        
        assert "25" in sql2
        assert "55" in sql2
        
        # 無效的整數
        with pytest.raises(ValueError, match="必須是整數"):
            manager.generate_sql("patients_by_age_range", {
                "min_age": "abc",
                "max_age": 50
            })
    
    def test_add_custom_template(self, manager):
        """測試添加自訂範本"""
        custom_template = QueryTemplate(
            id="custom_test",
            name="自訂測試範本",
            description="這是自訂範本",
            category="自訂類別",
            sql_template="SELECT * FROM CO01M WHERE kcstmr = '{patient_id}'",
            parameters=[
                {"name": "patient_id", "type": "string", "required": True, "description": "病歷號"}
            ],
            example_values={"patient_id": "001"},
            tags=["自訂", "測試"]
        )
        
        success = manager.add_custom_template(custom_template)
        
        assert success == True
        assert "custom_test" in manager.templates
        assert manager.get_template("custom_test") == custom_template
    
    def test_remove_template(self, manager):
        """測試移除範本"""
        # 先添加一個測試範本
        test_template = QueryTemplate(
            id="temp_test",
            name="臨時測試",
            description="臨時範本",
            category="測試",
            sql_template="SELECT 1",
            parameters=[],
            example_values={},
            tags=["測試"]
        )
        
        manager.add_custom_template(test_template)
        assert "temp_test" in manager.templates
        
        # 移除範本
        success = manager.remove_template("temp_test")
        
        assert success == True
        assert "temp_test" not in manager.templates
        
        # 移除不存在的範本
        success2 = manager.remove_template("nonexistent")
        assert success2 == False
    
    def test_get_template_examples(self, manager):
        """測試獲取範本範例"""
        examples = manager.get_template_examples("patient_by_name")
        
        assert examples is not None
        assert isinstance(examples, dict)
        assert "name" in examples
        
        # 不存在的範本
        examples2 = manager.get_template_examples("nonexistent")
        assert examples2 is None
    
    def test_complex_sql_generation(self, manager):
        """測試複雜SQL生成"""
        # 測試就診記錄查詢
        sql = manager.generate_sql("visits_by_date_range", {
            "start_date": "20240101",
            "end_date": "20241231",
            "limit": 500
        })
        
        assert "SELECT" in sql
        assert "CO03M" in sql
        assert "CO01M" in sql  # 應該有JOIN
        assert "LEFT JOIN" in sql or "JOIN" in sql
        assert "20240101" in sql
        assert "20241231" in sql
        assert "500" in sql
    
    def test_statistical_template(self, manager):
        """測試統計類型範本"""
        sql = manager.generate_sql("patient_count_by_age_group", {})
        
        assert "SELECT" in sql
        assert "COUNT(*)" in sql
        assert "GROUP BY" in sql
        assert "CASE" in sql
        assert "年齡" in sql or "age" in sql
    
    def test_parameter_processing_edge_cases(self, manager):
        """測試參數處理邊界情況"""
        # 測試空字串參數
        sql1 = manager.generate_sql("patient_by_name", {"name": ""})
        assert "'%%'" in sql1
        
        # 測試特殊字元參數
        sql2 = manager.generate_sql("patient_by_name", {"name": "李'小明"})
        assert "李'小明" in sql2
    
    def test_template_categories_completeness(self, manager):
        """測試範本類別完整性"""
        expected_categories = [
            "病患資料",
            "就診記錄", 
            "處方記錄",
            "檢驗結果",
            "統計分析"
        ]
        
        actual_categories = manager.get_categories()
        
        for category in expected_categories:
            assert category in actual_categories
    
    def test_all_templates_have_examples(self, manager):
        """測試所有範本都有範例值"""
        for template_id, template in manager.templates.items():
            examples = manager.get_template_examples(template_id)
            
            # 檢查是否有範例值
            assert isinstance(examples, dict)
            
            # 檢查必要參數是否都有範例
            required_params = [p["name"] for p in template.parameters if p.get("required", False)]
            for param in required_params:
                assert param in examples or param in [p["name"] for p in template.parameters if "default" in p]