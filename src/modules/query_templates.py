"""
常用查詢範本系統

提供預定義的醫療查詢範本，支援參數化查詢和查詢組合，
幫助使用者快速執行常見的診所資料查詢。

Author: Leon Lu
Created: 2025-01-24
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


@dataclass
class QueryTemplate:
    """查詢範本類別"""
    id: str
    name: str
    description: str
    category: str
    sql_template: str
    parameters: List[Dict[str, Any]]
    example_values: Dict[str, Any]
    tags: List[str]


class QueryTemplateManager:
    """
    查詢範本管理器
    
    管理和提供各種預定義的醫療查詢範本，
    支援參數替換和動態查詢生成。
    """
    
    def __init__(self):
        """初始化範本管理器"""
        self.templates = {}
        self._load_default_templates()
        logger.info(f"查詢範本管理器已初始化，載入 {len(self.templates)} 個範本")
    
    def _load_default_templates(self):
        """載入預設查詢範本"""
        
        # 病患基本資料查詢範本
        patient_templates = [
            QueryTemplate(
                id="patient_by_name",
                name="依姓名查詢病患",
                description="根據病患姓名查詢基本資料",
                category="病患資料",
                sql_template="SELECT kcstmr, mname, msex, mbirthdt, mtelh, mweight, mheight FROM CO01M WHERE mname LIKE '%{name}%' ORDER BY mname LIMIT {limit}",
                parameters=[
                    {"name": "name", "type": "string", "required": True, "description": "病患姓名(支援模糊搜尋)"},
                    {"name": "limit", "type": "integer", "required": False, "default": 50, "description": "最大結果數量"}
                ],
                example_values={"name": "李小明", "limit": 10},
                tags=["病患", "姓名", "基本資料"]
            ),
            
            QueryTemplate(
                id="patient_by_id",
                name="依病歷號查詢病患", 
                description="根據病歷號查詢完整病患資料",
                category="病患資料",
                sql_template="SELECT * FROM CO01M WHERE kcstmr = '{patient_id}'",
                parameters=[
                    {"name": "patient_id", "type": "string", "required": True, "description": "病歷號"}
                ],
                example_values={"patient_id": "0000001"},
                tags=["病患", "病歷號", "詳細資料"]
            ),
            
            QueryTemplate(
                id="patients_by_age_range",
                name="依年齡範圍查詢病患",
                description="查詢指定年齡範圍的病患",
                category="病患資料", 
                sql_template="SELECT kcstmr, mname, msex, mbirthdt, (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) as age FROM CO01M WHERE (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) BETWEEN {min_age} AND {max_age} ORDER BY age LIMIT {limit}",
                parameters=[
                    {"name": "min_age", "type": "integer", "required": True, "description": "最小年齡"},
                    {"name": "max_age", "type": "integer", "required": True, "description": "最大年齡"},
                    {"name": "limit", "type": "integer", "required": False, "default": 100, "description": "最大結果數量"}
                ],
                example_values={"min_age": 40, "max_age": 65, "limit": 50},
                tags=["病患", "年齡", "統計"]
            ),
        ]
        
        # 就診記錄查詢範本
        visit_templates = [
            QueryTemplate(
                id="visits_by_date_range", 
                name="依日期範圍查詢就診記錄",
                description="查詢指定日期範圍內的就診記錄",
                category="就診記錄",
                sql_template="SELECT c.kcstmr, p.mname, c.idate, c.itime, c.labno, c.ipk3, c.tot FROM CO03M c LEFT JOIN CO01M p ON c.kcstmr = p.kcstmr WHERE c.idate BETWEEN '{start_date}' AND '{end_date}' ORDER BY c.idate DESC, c.itime DESC LIMIT {limit}",
                parameters=[
                    {"name": "start_date", "type": "date", "required": True, "description": "開始日期(YYYYMMDD)"},
                    {"name": "end_date", "type": "date", "required": True, "description": "結束日期(YYYYMMDD)"},
                    {"name": "limit", "type": "integer", "required": False, "default": 200, "description": "最大結果數量"}
                ],
                example_values={"start_date": "20250101", "end_date": "20250131", "limit": 100},
                tags=["就診", "日期", "記錄"]
            ),
            
            QueryTemplate(
                id="visits_by_patient",
                name="依病患查詢就診記錄",
                description="查詢特定病患的就診歷史",
                category="就診記錄",
                sql_template="SELECT c.idate, c.itime, c.labno, c.ipk3, c.tot, c.sa98 FROM CO03M c WHERE c.kcstmr = '{patient_id}' ORDER BY c.idate DESC, c.itime DESC LIMIT {limit}",
                parameters=[
                    {"name": "patient_id", "type": "string", "required": True, "description": "病歷號"},
                    {"name": "limit", "type": "integer", "required": False, "default": 50, "description": "最大結果數量"}
                ],
                example_values={"patient_id": "0000001", "limit": 20},
                tags=["就診", "病患", "歷史"]
            ),
            
            QueryTemplate(
                id="visits_by_diagnosis",
                name="依診斷代碼查詢就診記錄",
                description="查詢特定診斷代碼的就診記錄",
                category="就診記錄",
                sql_template="SELECT c.kcstmr, p.mname, c.idate, c.labno, c.ipk3 FROM CO03M c LEFT JOIN CO01M p ON c.kcstmr = p.kcstmr WHERE c.labno LIKE '%{diagnosis_code}%' ORDER BY c.idate DESC LIMIT {limit}",
                parameters=[
                    {"name": "diagnosis_code", "type": "string", "required": True, "description": "診斷代碼"},
                    {"name": "limit", "type": "integer", "required": False, "default": 100, "description": "最大結果數量"}
                ],
                example_values={"diagnosis_code": "E11", "limit": 50},
                tags=["就診", "診斷", "疾病"]
            ),
        ]
        
        # 處方記錄查詢範本
        prescription_templates = [
            QueryTemplate(
                id="prescriptions_by_drug",
                name="依藥品查詢處方記錄",
                description="查詢特定藥品的處方記錄",
                category="處方記錄",
                sql_template="SELECT pr.kcstmr, p.mname, pr.idate, pr.dno, pr.ptp, pr.pfq, pr.ptday FROM CO02M pr LEFT JOIN CO01M p ON pr.kcstmr = p.kcstmr WHERE pr.dno LIKE '%{drug_code}%' ORDER BY pr.idate DESC LIMIT {limit}",
                parameters=[
                    {"name": "drug_code", "type": "string", "required": True, "description": "藥品代碼或名稱"},
                    {"name": "limit", "type": "integer", "required": False, "default": 100, "description": "最大結果數量"}
                ],
                example_values={"drug_code": "DRUG001", "limit": 50},
                tags=["處方", "藥品", "用藥"]
            ),
            
            QueryTemplate(
                id="prescriptions_by_patient_date",
                name="依病患和日期查詢處方",
                description="查詢特定病患在指定日期的處方記錄",
                category="處方記錄", 
                sql_template="SELECT pr.idate, pr.itime, pr.dno, pr.ptp, pr.pfq, pr.ptday FROM CO02M pr WHERE pr.kcstmr = '{patient_id}' AND pr.idate BETWEEN '{start_date}' AND '{end_date}' ORDER BY pr.idate DESC, pr.itime DESC LIMIT {limit}",
                parameters=[
                    {"name": "patient_id", "type": "string", "required": True, "description": "病歷號"},
                    {"name": "start_date", "type": "date", "required": True, "description": "開始日期(YYYYMMDD)"},
                    {"name": "end_date", "type": "date", "required": True, "description": "結束日期(YYYYMMDD)"},
                    {"name": "limit", "type": "integer", "required": False, "default": 50, "description": "最大結果數量"}
                ],
                example_values={"patient_id": "0000001", "start_date": "20250101", "end_date": "20250131", "limit": 30},
                tags=["處方", "病患", "日期"]
            ),
        ]
        
        # 檢驗結果查詢範本  
        lab_templates = [
            QueryTemplate(
                id="lab_results_by_item",
                name="依檢驗項目查詢結果",
                description="查詢特定檢驗項目的結果",
                category="檢驗結果",
                sql_template="SELECT l.kcstmr, p.mname, l.hdate, l.hitem, l.hdscp, l.hval, l.hresult, l.hrule FROM CO18H l LEFT JOIN CO01M p ON l.kcstmr = p.kcstmr WHERE l.hitem LIKE '%{lab_item}%' OR l.hdscp LIKE '%{lab_item}%' ORDER BY l.hdate DESC LIMIT {limit}",
                parameters=[
                    {"name": "lab_item", "type": "string", "required": True, "description": "檢驗項目代碼或描述"},
                    {"name": "limit", "type": "integer", "required": False, "default": 100, "description": "最大結果數量"}
                ],
                example_values={"lab_item": "血糖", "limit": 50},
                tags=["檢驗", "項目", "結果"]
            ),
            
            QueryTemplate(
                id="lab_results_abnormal",
                name="查詢異常檢驗結果",
                description="查詢包含異常標記的檢驗結果",
                category="檢驗結果",
                sql_template="SELECT l.kcstmr, p.mname, l.hdate, l.hitem, l.hdscp, l.hval, l.hresult FROM CO18H l LEFT JOIN CO01M p ON l.kcstmr = p.kcstmr WHERE l.hresult LIKE '%異常%' OR l.hresult LIKE '%↑%' OR l.hresult LIKE '%↓%' OR l.hresult LIKE '%H%' OR l.hresult LIKE '%L%' ORDER BY l.hdate DESC LIMIT {limit}",
                parameters=[
                    {"name": "limit", "type": "integer", "required": False, "default": 100, "description": "最大結果數量"}
                ],
                example_values={"limit": 50},
                tags=["檢驗", "異常", "警示"]
            ),
            
            QueryTemplate(
                id="lab_results_by_patient_item",
                name="依病患和項目查詢檢驗趨勢",
                description="查詢特定病患某項檢驗的歷史趨勢",
                category="檢驗結果",
                sql_template="SELECT l.hdate, l.htime, l.hitem, l.hdscp, l.hval, l.hresult, l.hrule FROM CO18H l WHERE l.kcstmr = '{patient_id}' AND (l.hitem LIKE '%{lab_item}%' OR l.hdscp LIKE '%{lab_item}%') ORDER BY l.hdate DESC, l.htime DESC LIMIT {limit}",
                parameters=[
                    {"name": "patient_id", "type": "string", "required": True, "description": "病歷號"},
                    {"name": "lab_item", "type": "string", "required": True, "description": "檢驗項目代碼或描述"},
                    {"name": "limit", "type": "integer", "required": False, "default": 20, "description": "最大結果數量"}
                ],
                example_values={"patient_id": "0000001", "lab_item": "血糖", "limit": 10},
                tags=["檢驗", "病患", "趨勢"]
            ),
        ]
        
        # 統計分析查詢範本
        statistics_templates = [
            QueryTemplate(
                id="patient_count_by_age_group",
                name="依年齡組統計病患數量",
                description="統計各年齡組的病患數量分布",
                category="統計分析",
                sql_template="""
                SELECT 
                    CASE 
                        WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) < 18 THEN '未成年'
                        WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) BETWEEN 18 AND 30 THEN '18-30歲'
                        WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) BETWEEN 31 AND 50 THEN '31-50歲'
                        WHEN (strftime('%Y', 'now') - CAST(substr(mbirthdt, 1, 4) AS INTEGER)) BETWEEN 51 AND 70 THEN '51-70歲'
                        ELSE '70歲以上'
                    END as age_group,
                    COUNT(*) as patient_count
                FROM CO01M 
                WHERE mbirthdt IS NOT NULL AND mbirthdt != ''
                GROUP BY age_group 
                ORDER BY patient_count DESC
                """,
                parameters=[],
                example_values={},
                tags=["統計", "年齡", "分布"]
            ),
            
            QueryTemplate(
                id="visit_count_by_month",
                name="依月份統計就診次數",
                description="統計各月份的就診次數",
                category="統計分析",
                sql_template="SELECT substr(idate, 1, 6) as month, COUNT(*) as visit_count FROM CO03M WHERE idate >= '{start_year}0101' GROUP BY substr(idate, 1, 6) ORDER BY month DESC LIMIT 12",
                parameters=[
                    {"name": "start_year", "type": "string", "required": False, "default": "2024", "description": "統計起始年份"}
                ],
                example_values={"start_year": "2024"},
                tags=["統計", "就診", "月份"]
            ),
        ]
        
        # 將所有範本加入管理器
        all_templates = (
            patient_templates + visit_templates + 
            prescription_templates + lab_templates + 
            statistics_templates
        )
        
        for template in all_templates:
            self.templates[template.id] = template
    
    def get_template(self, template_id: str) -> Optional[QueryTemplate]:
        """
        根據ID獲取查詢範本
        
        Args:
            template_id: 範本ID
            
        Returns:
            QueryTemplate: 查詢範本，如果不存在則返回None
        """
        return self.templates.get(template_id)
    
    def list_templates(self, category: Optional[str] = None, 
                      tags: Optional[List[str]] = None) -> List[QueryTemplate]:
        """
        列出查詢範本
        
        Args:
            category: 篩選類別
            tags: 篩選標籤
            
        Returns:
            List[QueryTemplate]: 符合條件的範本列表
        """
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if tags:
            templates = [t for t in templates 
                        if any(tag in t.tags for tag in tags)]
        
        return sorted(templates, key=lambda x: x.name)
    
    def get_categories(self) -> List[str]:
        """
        獲取所有範本類別
        
        Returns:
            List[str]: 類別列表
        """
        categories = set(t.category for t in self.templates.values())
        return sorted(list(categories))
    
    def search_templates(self, keyword: str) -> List[QueryTemplate]:
        """
        搜尋查詢範本
        
        Args:
            keyword: 搜尋關鍵字
            
        Returns:
            List[QueryTemplate]: 符合關鍵字的範本列表
        """
        keyword_lower = keyword.lower()
        results = []
        
        for template in self.templates.values():
            if (keyword_lower in template.name.lower() or
                keyword_lower in template.description.lower() or
                any(keyword_lower in tag.lower() for tag in template.tags)):
                results.append(template)
        
        return sorted(results, key=lambda x: x.name)
    
    def generate_sql(self, template_id: str, 
                    parameters: Dict[str, Any]) -> str:
        """
        根據範本和參數生成SQL語句
        
        Args:
            template_id: 範本ID
            parameters: 參數字典
            
        Returns:
            str: 生成的SQL語句
            
        Raises:
            ValueError: 範本不存在或參數不符合要求
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"範本不存在: {template_id}")
        
        # 驗證必要參數
        provided_params = set(parameters.keys())
        
        for param_def in template.parameters:
            param_name = param_def["name"]
            if param_def.get("required", False) and param_name not in provided_params:
                raise ValueError(f"缺少必要參數: {param_name}")
        
        # 設置預設值
        final_params = {}
        for param_def in template.parameters:
            param_name = param_def["name"]
            if param_name in parameters:
                final_params[param_name] = parameters[param_name]
            elif "default" in param_def:
                final_params[param_name] = param_def["default"]
        
        # 參數驗證和處理
        processed_params = self._process_parameters(final_params, template.parameters)
        
        # 生成SQL
        try:
            sql = template.sql_template.format(**processed_params)
            return sql.strip()
        except KeyError as e:
            raise ValueError(f"參數替換失敗: {e}")
    
    def _process_parameters(self, parameters: Dict[str, Any], 
                          param_definitions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        處理和驗證參數
        
        Args:
            parameters: 原始參數
            param_definitions: 參數定義
            
        Returns:
            Dict[str, Any]: 處理後的參數
        """
        processed = {}
        
        for param_def in param_definitions:
            param_name = param_def["name"]
            param_type = param_def.get("type", "string")
            
            if param_name not in parameters:
                continue
            
            value = parameters[param_name]
            
            # 類型轉換和驗證
            if param_type == "integer":
                try:
                    processed[param_name] = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"參數 {param_name} 必須是整數")
            
            elif param_type == "date":
                # 驗證日期格式 YYYYMMDD
                if isinstance(value, str) and re.match(r'^\d{8}$', value):
                    processed[param_name] = value
                else:
                    raise ValueError(f"參數 {param_name} 必須是YYYYMMDD格式的日期")
            
            elif param_type == "string":
                processed[param_name] = str(value)
            
            else:
                processed[param_name] = value
        
        return processed
    
    def add_custom_template(self, template: QueryTemplate) -> bool:
        """
        添加自訂範本
        
        Args:
            template: 查詢範本
            
        Returns:
            bool: 是否成功添加
        """
        try:
            if template.id in self.templates:
                logger.warning(f"範本ID已存在，將覆蓋: {template.id}")
            
            self.templates[template.id] = template
            logger.info(f"已添加自訂範本: {template.id}")
            return True
            
        except Exception as e:
            logger.error(f"添加自訂範本失敗: {e}")
            return False
    
    def remove_template(self, template_id: str) -> bool:
        """
        移除範本
        
        Args:
            template_id: 範本ID
            
        Returns:
            bool: 是否成功移除
        """
        if template_id in self.templates:
            del self.templates[template_id]
            logger.info(f"已移除範本: {template_id}")
            return True
        
        return False
    
    def get_template_examples(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取範本的範例參數
        
        Args:
            template_id: 範本ID
            
        Returns:
            Dict[str, Any]: 範例參數
        """
        template = self.get_template(template_id)
        return template.example_values if template else None