"""
Gemma3模型專用Prompt模板

針對Gemma3模型特性優化的Prompt工程，實現結構化SQL查詢生成。

Author: Leon Lu
Created: 2025-01-25
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .sql_models import SQL_RESPONSE_SCHEMA


class Gemma3PromptTemplate:
    """Gemma3專用Prompt模板生成器"""
    
    def __init__(self):
        """初始化Prompt模板"""
        self.medical_terms_mapping = {
            # 病患基本資料
            "病歷號": "kcstmr",
            "姓名": "mname", 
            "性別": "msex",
            "出生日期": "mbirthdt",
            "電話": "mtelh",
            "體重": "mweight",
            "身高": "mheight",
            
            # 就診相關
            "就診日期": "idate",
            "診斷": "labno",
            "醫師": "ipk3",
            "申報金額": "tot",
            
            # 處方相關
            "藥品代碼": "dno",
            "用藥天數": "ptday",
            "使用頻率": "pfq",
            
            # 檢驗相關
            "檢驗日期": "hdate",
            "檢驗項目": "hitem",
            "檢驗值": "hval",
            "檢驗結果": "hresult",
        }
        
        self.few_shot_examples = [
            {
                "query": "查詢病患林正日的基本資料",
                "response": {
                    "sql_query": "SELECT kcstmr, mname, msex, mbirthdt, mtelh, mweight, mheight FROM CO01M WHERE mname LIKE '%林正日%' LIMIT 10",
                    "query_type": "patient_info",
                    "confidence": "high",
                    "explanation": "查詢病患主檔(CO01M)中姓名包含'林正日'的病患基本資訊",
                    "table_mapping": {"CO01M": "病患主檔"},
                    "field_mapping": {"姓名": "mname", "性別": "msex", "出生日期": "mbirthdt"},
                    "estimated_results": 1
                }
            },
            {
                "query": "2023年8月的檢驗結果",
                "response": {
                    "sql_query": "SELECT kcstmr, hdate, hitem, hval, hresult FROM CO18H WHERE hdate >= '2023-08-01' AND hdate < '2023-09-01' ORDER BY hdate DESC LIMIT 100",
                    "query_type": "lab_result", 
                    "confidence": "high",
                    "explanation": "查詢檢驗結果檔(CO18H)中2023年8月的檢驗資料，按日期降序排列",
                    "table_mapping": {"CO18H": "檢驗結果檔"},
                    "field_mapping": {"檢驗日期": "hdate", "檢驗項目": "hitem", "檢驗值": "hval"},
                    "estimated_results": 50
                }
            },
            {
                "query": "統計男性和女性病患人數",
                "response": {
                    "sql_query": "SELECT msex, COUNT(*) as patient_count FROM CO01M GROUP BY msex LIMIT 10",
                    "query_type": "statistics",
                    "confidence": "high", 
                    "explanation": "統計病患主檔(CO01M)中男性(1)和女性(0)病患的人數分布",
                    "table_mapping": {"CO01M": "病患主檔"},
                    "field_mapping": {"性別": "msex"},
                    "estimated_results": 2
                }
            },
            {
                "query": "盧盈良的抽血報告",
                "response": {
                    "sql_query": "SELECT h.kcstmr, p.mname, h.hdate, h.hitem, h.hval, h.hresult FROM CO18H h JOIN CO01M p ON h.kcstmr = p.kcstmr WHERE p.mname LIKE '%盧盈良%' ORDER BY h.hdate DESC LIMIT 100",
                    "query_type": "lab_result",
                    "confidence": "high",
                    "explanation": "查詢盧盈良的檢驗結果，通過病患主檔(CO01M)和檢驗結果檔(CO18H)聯合查詢",
                    "table_mapping": {"CO01M": "病患主檔", "CO18H": "檢驗結果檔"},
                    "field_mapping": {"姓名": "mname", "檢驗日期": "hdate", "檢驗項目": "hitem"},
                    "estimated_results": 10
                }
            },
            {
                "query": "林心若的就診記錄",
                "response": {
                    "sql_query": "SELECT c.kcstmr, p.mname, c.idate, c.itime, c.labno, c.tot FROM CO03M c JOIN CO01M p ON c.kcstmr = p.kcstmr WHERE p.mname LIKE '%林心若%' ORDER BY c.idate DESC LIMIT 100",
                    "query_type": "visit_record",
                    "confidence": "high",
                    "explanation": "查詢林心若的就診記錄，通過病患主檔(CO01M)和就診摘要檔(CO03M)聯合查詢",
                    "table_mapping": {"CO01M": "病患主檔", "CO03M": "就診摘要檔"},
                    "field_mapping": {"姓名": "mname", "就診日期": "idate", "診斷": "labno"},
                    "estimated_results": 5
                }
            }
        ]
    
    def generate_system_prompt(self) -> str:
        """生成系統提示詞"""
        schema_str = json.dumps(SQL_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)
        
        return f"""你是台灣診所的專業AI查詢助手，專門將中文醫療查詢轉換為安全的SQL語句。

## 核心任務
將醫護人員的中文自然語言查詢轉換為標準SQL查詢，必須以JSON格式回應。

## 資料庫結構（展望診療系統）

### CO01M - 病患主檔（核心表，包含姓名資訊）
- kcstmr: 病歷號（主鍵，7位數字如'0000001'）
- mname: 病患姓名（中文，如'林正日'）**← 只有這個表有姓名！**
- msex: 性別（0=女性, 1=男性）
- mbirthdt: 出生日期（YYYY-MM-DD格式，如'1987-05-15'）
- mtelh: 行動電話
- mweight: 體重（公斤）
- mheight: 身高（公分）

### CO02M - 處方記錄檔
- kcstmr: 病歷號（外鍵，對應CO01M.kcstmr）**← 只有病歷號，沒有姓名！**
- idate: 開立日期（YYYY-MM-DD格式，如'2023-08-01'）
- itime: 開立時間（如'104125'）
- dno: 藥品代碼
- ptp: 藥品類型
- pfq: 使用頻率（如TID, BID等）
- ptday: 用藥天數

### CO03M - 就診摘要檔
- kcstmr: 病歷號（外鍵，對應CO01M.kcstmr）**← 只有病歷號，沒有姓名！**
- idate: 就診日期（YYYY-MM-DD格式，如'2023-08-01'）
- itime: 就診時間（如'103819'）
- labno: 主診斷代碼
- ipk3: 醫師代碼
- tot: 申報金額

### CO18H - 檢驗結果檔
- kcstmr: 病歷號（外鍵，對應CO01M.kcstmr）**← 只有病歷號，沒有姓名！**
- hdate: 檢驗日期（YYYY-MM-DD格式，如'2023-08-01'）
- htime: 檢驗時間
- hitem: 檢驗項目代碼
- hval: 檢驗數值
- hresult: 檢驗結果描述

## ⚠️ 重要：資料表關聯規則
1. **姓名只存在CO01M表中** - 其他表只有病歷號(kcstmr)
2. **根據姓名查詢其他資料必須JOIN CO01M** - 絕對不能在CO02M/CO03M/CO18H中直接搜索姓名
3. **標準JOIN模式**：
   ```sql
   SELECT 欄位 FROM 目標表 t JOIN CO01M p ON t.kcstmr = p.kcstmr WHERE p.mname LIKE '%姓名%'
   ```

## 醫療術語對應
{json.dumps(self.medical_terms_mapping, ensure_ascii=False, indent=2)}

## 安全規則
1. **只能生成SELECT查詢** - 嚴禁任何修改操作
2. **必須加LIMIT** - 預設LIMIT 100，最大1000
3. **姓名查詢必須JOIN** - 如果根據姓名查詢其他表資料，必須JOIN CO01M表
4. **姓名使用LIKE** - 如：p.mname LIKE '%張%'（注意表別名）
5. **日期格式統一** - YYYY-MM-DD格式，如：'2023-08-01'
6. **性別編碼** - 0=女性, 1=男性（不是M/F）
7. **避免SELECT \\*** - 明確指定需要的欄位
8. **禁止敏感欄位** - 不可查詢身分證等個資
9. **必須使用正確表名** - CO01M, CO02M, CO03M, CO18H
10. **禁止錯誤邏輯** - 絕對不能在CO02M/CO03M/CO18H的kcstmr欄位中搜索姓名

## 回應格式
必須嚴格按照以下JSON Schema格式回應：

```json
{schema_str}
```

## 重要提醒
- 回應必須是有效的JSON格式
- sql_query必須是完整可執行的SQL語句
- confidence請根據查詢複雜度評估：simple→high, moderate→medium, complex→low
- explanation用繁體中文解釋SQL的功能
- 遇到模糊查詢時，在warnings中說明"""

    def generate_user_prompt(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        生成用戶查詢提示詞
        
        Args:
            user_query: 用戶的中文查詢
            context: 可選的上下文資訊
            
        Returns:
            str: 完整的用戶提示詞
        """
        prompt_parts = [
            f"用戶查詢：{user_query}",
            "",
            "請分析上述查詢並生成對應的SQL語句，以JSON格式回應。"
        ]
        
        # 添加上下文資訊
        if context:
            if 'previous_error' in context:
                prompt_parts.extend([
                    "",
                    f"注意：上次查詢失敗，錯誤原因：{context['previous_error']}",
                    "請修正錯誤並重新生成SQL。"
                ])
            
            if 'suggested_table' in context:
                prompt_parts.extend([
                    "",
                    f"建議資料表：{context['suggested_table']}"
                ])
        
        # 添加當前日期參考
        current_date = datetime.now().strftime("%Y%m%d")
        prompt_parts.extend([
            "",
            f"參考資訊：",
            f"- 今天日期：{current_date}",
            f"- 可用資料表：CO01M, CO02M, CO03M, CO18H",
            "",
            "注意：請嚴格按照JSON格式回應，確保所有字串都用雙引號包圍，SQL語句中不要包含換行符。",
            "",
            "回應格式：JSON"
        ])
        
        return "\n".join(prompt_parts)
    
    def generate_few_shot_prompt(self, user_query: str) -> str:
        """
        生成包含範例的Few-shot Prompt
        
        Args:
            user_query: 用戶查詢
            
        Returns:
            str: Few-shot提示詞
        """
        prompt_parts = [
            "以下是一些查詢範例：",
            ""
        ]
        
        # 添加範例
        for i, example in enumerate(self.few_shot_examples, 1):
            example_json = json.dumps(example["response"], ensure_ascii=False, indent=2)
            prompt_parts.extend([
                f"範例 {i}：",
                f"查詢：{example['query']}",
                f"回應：",
                f"```json",
                example_json,
                f"```",
                ""
            ])
        
        # 添加實際查詢
        prompt_parts.extend([
            "現在請處理以下查詢：",
            f"查詢：{user_query}",
            "",
            "請以相同的JSON格式回應："
        ])
        
        return "\n".join(prompt_parts)
    
    def generate_error_recovery_prompt(self, user_query: str, error_info: Dict[str, Any]) -> str:
        """
        生成錯誤恢復提示詞
        
        Args:
            user_query: 原始查詢
            error_info: 錯誤資訊
            
        Returns:
            str: 錯誤恢復提示詞
        """
        prompt_parts = [
            f"原始查詢：{user_query}",
            "",
            f"上次嘗試失敗，錯誤資訊：",
            f"- 錯誤類型：{error_info.get('error_type', '未知')}",
            f"- 錯誤訊息：{error_info.get('error_message', '無詳細資訊')}",
        ]
        
        if 'previous_sql' in error_info:
            prompt_parts.extend([
                "",
                f"上次生成的SQL：",
                f"```sql",
                error_info['previous_sql'],
                f"```"
            ])
        
        if 'suggestions' in error_info:
            prompt_parts.extend([
                "",
                "改進建議：",
            ])
            for suggestion in error_info['suggestions']:
                prompt_parts.append(f"- {suggestion}")
        
        prompt_parts.extend([
            "",
            "請根據錯誤資訊修正並重新生成正確的SQL查詢，以JSON格式回應。",
            "特別注意：",
            "1. 檢查資料表和欄位名稱是否正確",
            "2. 確保SQL語法符合SQLite標準", 
            "3. 避免使用不支援的函數或語法",
            "4. 必須包含LIMIT子句",
            "",
            "回應格式：JSON"
        ])
        
        return "\n".join(prompt_parts)
    
    def generate_confidence_boost_prompt(self, user_query: str) -> str:
        """
        生成信心提升提示詞（用於複雜查詢）
        
        Args:
            user_query: 用戶查詢
            
        Returns:
            str: 信心提升提示詞
        """
        return f"""這是一個複雜的醫療資料查詢，請仔細分析：

查詢：{user_query}

分析步驟：
1. 識別查詢意圖（病患資料/就診記錄/處方/檢驗結果/統計分析）
2. 確定需要的資料表和欄位
3. 構建適當的WHERE條件
4. 添加必要的ORDER BY和LIMIT

特別提醒：
- 如果涉及病患姓名，使用LIKE模糊匹配
- 如果涉及日期範圍，使用YYYYMMDD格式比較
- 如果是統計查詢，考慮使用GROUP BY和聚合函數
- 如果查詢模糊，在warnings中說明可能的理解

請以JSON格式回應，confidence設為適當等級：
- high: 查詢明確，SQL正確性高
- medium: 查詢有些模糊，但可以合理推測
- low: 查詢模糊，需要更多資訊才能準確執行

回應格式：JSON"""


# 創建全局Prompt模板實例
gemma3_prompts = Gemma3PromptTemplate()