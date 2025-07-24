# 診所AI查詢系統 - 完整開發計劃

## 📋 開發總覽
**項目名稱**: clinic-ai-query  
**開發週期**: 5週 (包含測試和部署)  
**團隊規模**: 1-2人  
**技術棧**: Python + Streamlit + Gemma-3n + SQLite + Docker  
**目標**: 建立可開源部署的診所AI資料查詢系統

## 🎯 第0週：專案初始化 (3天)

### 目標：建立完整的開源項目基礎架構

#### 📁 交付成果：
1. **GitHub Repository設置**
   ```
   clinic-ai-query/
   ├── README.md              # 項目說明和快速開始
   ├── LICENSE               # MIT開源授權
   ├── .gitignore           # Git忽略檔案
   ├── .github/
   │   ├── ISSUE_TEMPLATE.md
   │   ├── PULL_REQUEST_TEMPLATE.md
   │   └── workflows/ci.yml  # GitHub Actions
   ```

2. **基礎配置檔案**
   ```
   ├── requirements.txt      # Python依賴
   ├── docker-compose.yml    # Docker編排
   ├── Dockerfile           # Docker鏡像
   ├── .env.example         # 環境變數範例
   ├── setup.py            # Python包設置
   └── pyproject.toml      # 現代Python配置
   ```

3. **開發環境配置**
   ```
   ├── .pre-commit-config.yaml  # 代碼品質檢查
   ├── pytest.ini             # 測試配置
   ├── .flake8               # 代碼風格檢查
   └── .github/workflows/
       ├── ci.yml            # 持續整合
       ├── docker.yml        # Docker構建
       └── release.yml       # 版本發布
   ```

#### ✅ 驗收標準：
- [ ] GitHub Repository建立，包含完整的開源項目結構
- [ ] Docker環境可正常啟動 (`docker-compose up`)
- [ ] CI/CD管道運行正常，通過基礎檢查
- [ ] README.md包含清晰的安裝和使用說明
- [ ] 授權和貢獻指南完整

---

## 🔧 第1週：資料層開發

### 目標：完成DBF解析和資料庫建置

#### Day 1-2: DBF解析器開發
**檔案**: `src/modules/dbf_parser.py`

**核心功能實現**:
```python
class ZhanWangDBFParser:
    """展望診療系統DBF檔案解析器"""
    
    def __init__(self, encoding='big5'):
        self.encoding = encoding
        self.schema = ANCHIA_LAB_SCHEMA
    
    def parse_co01m(self, file_path: str) -> pd.DataFrame:
        """解析病患主資料表"""
        # 處理Big5編碼
        # 資料清理和驗證
        # 回傳標準化DataFrame
        
    def parse_co02m(self, file_path: str) -> pd.DataFrame:
        """解析處方記錄檔"""
        # 複合主鍵處理
        # 日期時間格式標準化
        
    def parse_co03m(self, file_path: str) -> pd.DataFrame:
        """解析就診摘要檔"""
        # 診斷代碼處理
        # 費用欄位數值化
        
    def parse_co18h(self, file_path: str) -> pd.DataFrame:
        """解析檢驗結果歷史檔"""
        # 檢驗值數值處理
        # 參考值範圍解析
        
    def validate_data_integrity(self, df: pd.DataFrame, table_name: str) -> bool:
        """資料完整性驗證"""
        # 主鍵重複檢查
        # 必填欄位檢查
        # 外鍵關聯驗證
```

**測試檔案**: `tests/test_dbf_parser.py`
- 使用脫敏範例資料測試
- Big5編碼相容性測試
- 異常資料處理測試

#### Day 3-4: 資料庫管理器
**檔案**: `src/modules/db_manager.py`

**核心功能實現**:
```python
class DatabaseManager:
    """SQLite資料庫管理器"""
    
    def __init__(self, db_path: str, config: dict):
        self.db_path = db_path
        self.config = config
        self._init_connection()
    
    def create_tables(self) -> None:
        """建立資料表結構"""
        # CO01M, CO02M, CO03M, CO18H表結構
        # 主鍵和外鍵約束
        
    def create_indexes(self) -> None:
        """建立查詢索引"""
        # 病歷號索引
        # 日期範圍索引
        # 複合索引優化
        
    def import_dbf_data(self, dbf_files: dict) -> bool:
        """匯入DBF資料"""
        # 批次匯入處理
        # 事務管理
        # 錯誤回滾
        
    def execute_query(self, sql: str, params: tuple = None) -> pd.DataFrame:
        """安全執行SQL查詢"""
        # SQL注入防護
        # 查詢結果限制
        # 執行時間監控
        
    def get_table_stats(self) -> dict:
        """獲取資料表統計資訊"""
        # 資料筆數
        # 最後更新時間
        # 索引使用狀況
```

#### Day 5-7: 資料轉換和初始化腳本
**檔案**: `scripts/setup_db.py`

**功能實現**:
```python
#!/usr/bin/env python3
"""資料庫初始化腳本"""

def main():
    # 檢查DBF檔案存在性
    # 建立SQLite資料庫
    # 執行資料轉換
    # 建立索引
    # 資料完整性驗證
    # 生成統計報告

if __name__ == "__main__":
    main()
```

**檔案**: `scripts/health_check.py`
```python
#!/usr/bin/env python3
"""系統健康檢查腳本"""

def check_database_health():
    # 資料庫連線測試
    # 資料完整性驗證
    # 查詢效能測試

def check_llm_service():
    # Ollama服務狀態
    # 模型載入狀況
    # 推論回應時間

def main():
    # 執行所有健康檢查
    # 生成檢查報告
```

#### ✅ 驗收標準:
- [ ] 四個DBF檔案可正確解析，無資料遺失
- [ ] Big5編碼處理無誤，中文字正常顯示
- [ ] SQLite資料庫建立成功，包含所有表和約束
- [ ] 關鍵索引創建完成，查詢效能符合預期
- [ ] 資料完整性驗證通過，無重複或遺漏資料
- [ ] 初始化腳本可重複執行，支援增量更新

---

## 🤖 第2週：LLM查詢代理開發

### 目標：實現自然語言到SQL的轉換

#### Day 1-3: LLM代理核心
**檔案**: `src/modules/llm_agent.py`

**核心功能實現**:
```python
class MedicalQueryAgent:
    """醫療查詢AI代理"""
    
    def __init__(self, ollama_config: dict, db_manager: DatabaseManager):
        self.ollama_client = ollama.Client(host=ollama_config['base_url'])
        self.db_manager = db_manager
        self.model_name = ollama_config['model']
        self.system_prompt = self._load_system_prompt()
    
    def process_natural_query(self, query: str, context: dict = None) -> dict:
        """處理自然語言查詢"""
        # 查詢意圖分析
        # 上下文整合
        # SQL生成
        # 結果執行
        # 結果解釋
        
    def generate_sql(self, query: str, context: dict = None) -> str:
        """生成SQL查詢語句"""
        # 建構完整提示詞
        # LLM推論
        # SQL語法驗證
        # 安全性檢查
        
    def validate_sql(self, sql: str) -> bool:
        """SQL語句安全性驗證"""
        # 禁止DELETE/UPDATE/DROP
        # 查詢複雜度限制
        # 結果集大小限制
        
    def execute_safe_query(self, sql: str) -> dict:
        """安全執行查詢"""
        # 查詢執行
        # 結果後處理
        # 敏感資訊遮蔽
        # 執行日誌記錄
        
    def explain_results(self, results: pd.DataFrame, original_query: str) -> str:
        """解釋查詢結果"""
        # 結果摘要生成
        # 醫療專業解釋
        # 關鍵指標提取
```

**相關檔案**: `src/modules/query_validator.py`
```python
class SQLValidator:
    """SQL查詢驗證器"""
    
    ALLOWED_KEYWORDS = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'LIMIT']
    FORBIDDEN_KEYWORDS = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER', 'CREATE']
    
    def validate(self, sql: str) -> tuple[bool, str]:
        # 關鍵字檢查
        # 語法解析
        # 複雜度評估
```

#### Day 4-5: 系統提示詞工程
**檔案**: `config/prompts/system_prompt.txt`

**內容結構**:
```
你是一個專業的醫療資料庫查詢助手，專門處理展望診療系統的資料查詢需求。

## 資料庫結構
[詳細的四表結構說明]

## 查詢規則
1. 只能使用SELECT查詢
2. 結果限制在1000筆以內
3. 敏感欄位需適當處理

## 醫療專業詞彙對應
- 糖尿病 -> labno LIKE '%E11%' OR labno LIKE '%糖尿%'
- 高血壓 -> labno LIKE '%I10%' OR labno LIKE '%高血壓%'
[更多醫療詞彙對應]

## SQL生成範例
[典型查詢的SQL範例]
```

**檔案**: `config/prompts/medical_terms.yaml`
```yaml
# 醫療詞彙對應表
diseases:
  糖尿病:
    icd_codes: ['E11', 'E10', 'E12']
    keywords: ['糖尿', 'DM', 'diabetes']
    
  高血壓:
    icd_codes: ['I10', 'I15']  
    keywords: ['高血壓', 'HTN', 'hypertension']

lab_items:
  血糖:
    codes: ['GLU', 'AC_GLU', 'PC_GLU']
    normal_range: '70-100 mg/dL'
    
  糖化血色素:
    codes: ['HbA1c', 'A1C']
    normal_range: '<7%'
```

#### Day 6-7: 查詢範本系統
**檔案**: `config/prompts/sql_examples.txt`

**範本分類**:
```sql
-- 病患基本查詢
/* 範本：查詢特定病患基本資料 */
SELECT m.mname, m.msex, m.mbirthdt, m.mlcasedate 
FROM CO01M m 
WHERE m.mname LIKE '%{patient_name}%';

-- 診斷統計查詢  
/* 範本：疾病診斷統計 */
SELECT c3.labno, COUNT(*) as case_count, 
       COUNT(DISTINCT c3.kcstmr) as patient_count
FROM CO03M c3 
WHERE c3.idate >= '{start_date}' AND c3.idate <= '{end_date}'
  AND c3.labno LIKE '%{disease}%'
GROUP BY c3.labno
ORDER BY case_count DESC;

-- 檢驗趨勢分析
/* 範本：檢驗值變化趨勢 */
SELECT c18.hdate, c18.hval, c18.hrule,
       c1.mname
FROM CO18H c18
JOIN CO01M c1 ON c18.kcstmr = c1.kcstmr
WHERE c18.hdscp LIKE '%{lab_item}%' 
  AND c1.mname = '{patient_name}'
ORDER BY c18.hdate ASC;
```

#### ✅ 驗收標準:
- [ ] Gemma-3n模型成功部署並可正常推論
- [ ] 自然語言轉SQL準確率達85%以上
- [ ] 醫療專業詞彙識別和對應正確
- [ ] SQL安全性驗證機制運作正常
- [ ] 查詢結果解釋清晰準確
- [ ] 回應時間控制在5秒內

---

## 🎨 第3週：使用者介面開發

### 目標：建立完整的Streamlit應用程式

#### Day 1-2: 主應用程式框架
**檔案**: `src/app.py`

**頁面結構**:
```python
import streamlit as st
from modules.auth import authenticate_user
from modules.llm_agent import MedicalQueryAgent
from modules.db_manager import DatabaseManager

def main():
    st.set_page_config(
        page_title="診所AI查詢系統",
        page_icon="🏥",
        layout="wide"
    )
    
    if not st.session_state.get('authenticated'):
        show_login_page()
    else:
        show_main_app()

def show_main_app():
    # 側邊欄導航
    page = st.sidebar.selectbox("選擇功能", [
        "🏠 系統概覽",
        "🔍 自然語言查詢", 
        "📊 資料統計",
        "📝 查詢歷史",
        "⚙️ 系統設定"
    ])
    
    if page == "🏠 系統概覽":
        show_dashboard()
    elif page == "🔍 自然語言查詢":
        show_query_interface()
    # 其他頁面...

def show_query_interface():
    st.header("🔍 自然語言查詢")
    
    # 查詢輸入區
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_area("請輸入您的查詢需求", height=100)
    with col2:
        if st.button("🚀 執行查詢", type="primary"):
            process_query(query)
    
    # 查詢建議
    st.subheader("💡 查詢建議")
    show_query_suggestions()
    
    # 結果顯示區
    if st.session_state.get('query_results'):
        show_query_results()
```

**檔案**: `src/pages/dashboard.py`
```python
def show_dashboard():
    """系統概覽頁面"""
    
    # 系統狀態指標
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("病患總數", get_patient_count())
    with col2:  
        st.metric("就診記錄", get_visit_count())
    with col3:
        st.metric("檢驗記錄", get_lab_count())
    with col4:
        st.metric("系統狀態", "🟢 正常")
    
    # 資料統計圖表
    show_data_overview_charts()
```

#### Day 3-4: 視覺化模組
**檔案**: `src/modules/visualizer.py`

**核心功能**:
```python
import plotly.express as px
import plotly.graph_objects as go

class MedicalDataVisualizer:
    """醫療資料視覺化工具"""
    
    def create_patient_timeline(self, patient_data: pd.DataFrame) -> go.Figure:
        """建立病患就診時間軸"""
        fig = go.Figure()
        
        # 就診記錄
        fig.add_trace(go.Scatter(
            x=patient_data['idate'],
            y=['就診'] * len(patient_data),
            mode='markers+text',
            name='就診記錄'
        ))
        
        # 檢驗記錄
        # 處方記錄
        
        return fig
    
    def create_lab_trend_chart(self, lab_data: pd.DataFrame) -> go.Figure:
        """建立檢驗值趨勢圖"""
        fig = px.line(
            lab_data, 
            x='hdate', 
            y='hval',
            title='檢驗值變化趨勢',
            markers=True
        )
        
        # 添加正常值範圍
        if 'normal_min' in lab_data.columns:
            fig.add_hline(y=lab_data['normal_min'].iloc[0], 
                         line_dash="dash", line_color="green")
            fig.add_hline(y=lab_data['normal_max'].iloc[0], 
                         line_dash="dash", line_color="green")
        
        return fig
    
    def create_diagnosis_distribution(self, diagnosis_data: pd.DataFrame) -> go.Figure:
        """建立診斷分布圖"""
        fig = px.pie(
            diagnosis_data,
            values='count',
            names='diagnosis', 
            title='診斷分布統計'
        )
        return fig
    
    def create_medication_analysis(self, med_data: pd.DataFrame) -> go.Figure:
        """建立用藥分析圖"""
        fig = px.bar(
            med_data,
            x='drug_name',
            y='frequency',
            title='用藥頻率統計'
        )
        return fig
```

#### Day 5-6: 認證與安全模組
**檔案**: `src/auth.py`

**功能實現**:
```python
import bcrypt
import streamlit as st
from datetime import datetime, timedelta

class AuthManager:
    """使用者認證管理"""
    
    def __init__(self, config: dict):
        self.config = config
        self.session_timeout = config.get('session_timeout', 1800)
    
    def authenticate_user(self, username: str, password: str) -> bool:
        """使用者認證"""
        # 密碼驗證
        # 登入嘗試記錄
        # 失敗次數限制
        
    def check_session_validity(self) -> bool:
        """檢查會話有效性"""
        if 'login_time' not in st.session_state:
            return False
            
        login_time = st.session_state['login_time']
        if datetime.now() - login_time > timedelta(seconds=self.session_timeout):
            return False
            
        return True
    
    def log_user_action(self, action: str, details: str = None):
        """記錄使用者操作"""
        # 審計日誌記錄
        pass

def show_login_page():
    """登入頁面"""
    st.title("🏥 診所AI查詢系統")
    st.subheader("使用者登入")
    
    with st.form("login_form"):
        username = st.text_input("使用者名稱")
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入")
        
        if submitted:
            if authenticate_user(username, password):
                st.session_state['authenticated'] = True
                st.session_state['username'] = username
                st.session_state['login_time'] = datetime.now()
                st.rerun()
            else:
                st.error("登入失敗，請檢查帳號密碼")
```

#### Day 7: 配置管理
**檔案**: `src/config.py`

**配置載入**:
```python
import yaml
import os
from pathlib import Path

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """載入配置檔案"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 環境變數覆蓋
        self._override_with_env(config)
        return config
    
    def _override_with_env(self, config: dict):
        """環境變數覆蓋配置"""
        if 'OLLAMA_BASE_URL' in os.environ:
            config['llm']['base_url'] = os.environ['OLLAMA_BASE_URL']
        # 其他環境變數...
    
    def get(self, key: str, default=None):
        """獲取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            value = value.get(k, default)
            if value is None:
                return default
        return value
```

#### ✅ 驗收標準:
- [ ] Web界面響應式設計，支援桌面和平板
- [ ] 使用者認證系統運作正常，支援會話管理
- [ ] 查詢結果視覺化美觀實用，圖表互動性好
- [ ] 敏感資訊適當遮蔽，符合隱私保護要求
- [ ] 頁面載入速度快，使用體驗流暢
- [ ] 錯誤處理完善，提供友善的錯誤訊息

---

## 🧪 第4週：測試與優化

### 目標：確保系統穩定性和效能

#### Day 1-2: 單元測試開發
**檔案**: `tests/test_dbf_parser.py`

```python
import pytest
import pandas as pd
from src.modules.dbf_parser import ZhanWangDBFParser

class TestDBFParser:
    
    @pytest.fixture
    def parser(self):
        return ZhanWangDBFParser(encoding='big5')
    
    @pytest.fixture  
    def sample_co01m_data(self):
        """CO01M測試資料"""
        return {
            'kcstmr': ['0000001', '0000002'],
            'mname': ['測試病患一', '測試病患二'],
            'msex': ['M', 'F'],
            'mbirthdt': ['19800101', '19900215']
        }
    
    def test_parse_co01m_success(self, parser, sample_co01m_data):
        """測試CO01M檔案解析成功"""
        # 建立測試DBF檔案
        # 執行解析
        # 驗證結果
        
    def test_parse_with_invalid_encoding(self, parser):
        """測試錯誤編碼處理"""
        # 測試編碼錯誤情況
        
    def test_data_validation(self, parser):
        """測試資料驗證功能"""
        # 測試必填欄位檢查
        # 測試資料格式驗證
```

**檔案**: `tests/test_db_manager.py`
```python
import pytest
import sqlite3
from src.modules.db_manager import DatabaseManager

class TestDatabaseManager:
    
    @pytest.fixture
    def db_manager(self, tmp_path):
        db_path = tmp_path / "test.db"
        return DatabaseManager(str(db_path), {})
    
    def test_create_tables(self, db_manager):
        """測試資料表建立"""
        db_manager.create_tables()
        # 驗證表結構
        
    def test_create_indexes(self, db_manager):
        """測試索引建立"""
        db_manager.create_tables()
        db_manager.create_indexes()
        # 驗證索引存在
        
    def test_sql_injection_protection(self, db_manager):
        """測試SQL注入防護"""
        malicious_sql = "SELECT * FROM CO01M; DROP TABLE CO01M;"
        with pytest.raises(ValueError):
            db_manager.execute_query(malicious_sql)
```

**檔案**: `tests/test_llm_agent.py`
```python
import pytest
from unittest.mock import Mock
from src.modules.llm_agent import MedicalQueryAgent

class TestMedicalQueryAgent:
    
    @pytest.fixture
    def mock_db_manager(self):
        return Mock()
    
    @pytest.fixture
    def agent(self, mock_db_manager):
        config = {'base_url': 'http://localhost:11434', 'model': 'test'}
        return MedicalQueryAgent(config, mock_db_manager)
    
    def test_generate_sql_for_patient_query(self, agent):
        """測試病患查詢SQL生成"""
        query = "查詢王小明的基本資料"
        sql = agent.generate_sql(query)
        assert "SELECT" in sql
        assert "CO01M" in sql
        assert "王小明" in sql
        
    def test_sql_validation_success(self, agent):
        """測試SQL驗證通過"""
        valid_sql = "SELECT * FROM CO01M WHERE mname = '王小明'"
        assert agent.validate_sql(valid_sql) == True
        
    def test_sql_validation_failure(self, agent):
        """測試SQL驗證失敗"""
        invalid_sql = "DROP TABLE CO01M"
        assert agent.validate_sql(invalid_sql) == False
```

#### Day 3-4: 整合測試
**檔案**: `tests/test_integration.py`

```python
import pytest
import tempfile
from src.app import create_app
from src.modules.db_manager import DatabaseManager

class TestIntegration:
    
    @pytest.fixture
    def app_with_test_db(self):
        """建立測試用應用程式"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 建立測試資料庫
            # 載入測試資料
            # 建立應用程式實例
            yield app
    
    def test_complete_query_flow(self, app_with_test_db):
        """測試完整查詢流程"""
        # 1. 輸入自然語言查詢
        # 2. SQL生成
        # 3. 資料庫查詢
        # 4. 結果視覺化
        # 5. 驗證最終結果
        
    def test_concurrent_queries(self, app_with_test_db):
        """測試併發查詢"""
        # 模擬多個使用者同時查詢
        
    def test_large_dataset_performance(self, app_with_test_db):
        """測試大量資料效能"""
        # 載入大量測試資料
        # 測試查詢回應時間
```

**效能測試腳本**: `tests/performance_test.py`
```python
import time
import statistics
from src.modules.db_manager import DatabaseManager

def benchmark_query_performance():
    """查詢效能基準測試"""
    db_manager = DatabaseManager("data/anchia_lab.db", {})
    
    # 測試查詢集
    test_queries = [
        "SELECT COUNT(*) FROM CO01M",
        "SELECT * FROM CO01M LIMIT 100", 
        "SELECT c1.mname, c3.labno FROM CO01M c1 JOIN CO03M c3 ON c1.kcstmr = c3.kcstmr LIMIT 100"
    ]
    
    for query in test_queries:
        times = []
        for _ in range(10):  # 執行10次取平均
            start = time.time()
            result = db_manager.execute_query(query)
            end = time.time()
            times.append(end - start)
        
        avg_time = statistics.mean(times)
        print(f"查詢: {query[:50]}...")
        print(f"平均執行時間: {avg_time:.3f}秒")
        print(f"結果筆數: {len(result)}")
        print("-" * 50)
```

#### Day 5-6: 效能優化
**資料庫查詢優化**:
```python
# src/modules/query_optimizer.py
class QueryOptimizer:
    """查詢最佳化器"""
    
    def optimize_sql(self, sql: str) -> str:
        """最佳化SQL查詢"""
        # 添加適當的LIMIT
        # 優化JOIN順序
        # 添加必要的索引提示
        
    def add_query_hints(self, sql: str) -> str:
        """添加查詢提示"""
        # SQLite特定優化提示
```

**記憶體使用優化**:
```python
# src/modules/memory_manager.py
class MemoryManager:
    """記憶體管理器"""
    
    def __init__(self, max_cache_size: int = 100):
        self.query_cache = {}
        self.max_cache_size = max_cache_size
    
    def cache_query_result(self, query_hash: str, result: pd.DataFrame):
        """快取查詢結果"""
        if len(self.query_cache) >= self.max_cache_size:
            # LRU清理策略
            self._cleanup_old_cache()
        
        self.query_cache[query_hash] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def get_cached_result(self, query_hash: str) -> pd.DataFrame:
        """獲取快取結果"""
        if query_hash in self.query_cache:
            cache_entry = self.query_cache[query_hash]
            # 檢查快取時效性
            if time.time() - cache_entry['timestamp'] < 300:  # 5分鐘
                return cache_entry['result']
        return None
```

#### Day 7: 安全性測試
**安全檢查清單**:
```python
# tests/test_security.py
class TestSecurity:
    
    def test_sql_injection_prevention(self):
        """SQL注入防護測試"""
        injection_attempts = [
            "'; DROP TABLE CO01M; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM CO01M",
        ]
        # 測試每個注入嘗試都被阻擋
        
    def test_sensitive_data_masking(self):
        """敏感資料遮蔽測試"""
        # 測試身分證號遮蔽
        # 測試電話號碼遮蔽
        
    def test_access_control(self):
        """存取控制測試"""
        # 測試未認證使用者無法存取
        # 測試會話過期處理
        
    def test_audit_logging(self):
        """審計日誌測試"""
        # 測試操作記錄完整性
        # 測試日誌無法被竄改
```

#### ✅ 驗收標準:
- [ ] 測試覆蓋率達到80%以上
- [ ] 所有單元測試和整合測試通過
- [ ] 查詢回應時間平均<5秒，90%查詢<3秒
- [ ] 系統可承受10個併發使用者
- [ ] 記憶體使用穩定，無記憶體洩漏
- [ ] 通過所有安全性測試，無已知漏洞

---

## 🚀 第5週：部署與文檔

### 目標：完成生產部署和使用者文檔

#### Day 1-2: Docker部署優化
**檔案**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    container_name: clinic-ai-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
      - ./models:/models
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_KEEP_ALIVE=24h
    command: serve
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  clinic-ai:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: clinic-ai-app
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data:ro
      - ./logs:/app/logs
      - ./config:/app/config:ro
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DATABASE_PATH=/app/data/anchia_lab.db
      - LOG_LEVEL=INFO
      - PYTHONPATH=/app
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    restart: unless-stopped

  model-loader:
    image: ollama/ollama:latest
    container_name: clinic-ai-model-loader
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=http://ollama:11434
    command: >
      bash -c "
        echo 'Loading Gemma2 model...' &&
        ollama pull gemma2:9b-instruct-q4_0 &&
        echo 'Model loaded successfully' &&
        ollama list
      "
    profiles:
      - setup

volumes:
  ollama_data:
    driver: local

networks:
  default:
    name: clinic-ai-network
```

**最佳化的Dockerfile**:
```dockerfile
FROM python:3.11-slim

LABEL maintainer="clinic-ai-query contributors"
LABEL description="診所AI查詢系統"

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 建立非root使用者
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 複製依賴檔案
COPY --chown=appuser:appuser requirements.txt .

# 安裝Python依賴
RUN pip install --no-cache-dir --user -r requirements.txt

# 複製應用程式碼
COPY --chown=appuser:appuser . .

# 建立必要目錄
RUN mkdir -p data logs config && \
    chmod +x scripts/*.py

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/healthz || exit 1

# 暴露端口
EXPOSE 8501

# 啟動命令
CMD ["python", "-m", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

#### Day 3-4: 安裝腳本完善
**檔案**: `scripts/install.sh`

```bash
#!/bin/bash
set -euo pipefail

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 錯誤處理
error_exit() {
    log_error "$1"
    exit 1
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 主要安裝函數
main() {
    echo "🏥 診所AI查詢系統 - 自動安裝"
    echo "================================"
    
    # 系統檢查
    check_system
    check_dependencies
    
    # 安裝Ollama
    install_ollama
    
    # 設置Python環境
    setup_python_env
    
    # 配置檔案
    setup_config
    
    # 啟動服務
    start_services
    
    # 健康檢查
    health_check
    
    # 完成提示
    show_completion_message
}

check_system() {
    log_info "檢查系統環境..."
    
    # 檢查作業系統
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        error_exit "不支援的作業系統: $OSTYPE"
    fi
    
    log_success "作業系統: $OS"
    
    # 檢查記憶體
    if [[ "$OS" == "linux" ]]; then
        MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    else
        MEMORY_GB=$(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))
    fi
    
    if [[ $MEMORY_GB -lt 16 ]]; then
        log_warning "記憶體不足16GB，可能影響效能"
    fi
    
    log_success "記憶體: ${MEMORY_GB}GB"
}

check_dependencies() {
    log_info "檢查依賴軟體..."
    
    # 檢查Python
    if ! command_exists python3; then
        error_exit "Python 3 未安裝，請先安裝 Python 3.9+"
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_success "Python 版本: $PYTHON_VERSION"
    
    # 檢查Docker (可選)
    if command_exists docker; then
        log_success "Docker 已安裝"
        DOCKER_AVAILABLE=true
    else
        log_warning "Docker 未安裝，將使用本地安裝模式"
        DOCKER_AVAILABLE=false
    fi
}

install_ollama() {
    log_info "安裝 Ollama..."
    
    if command_exists ollama; then
        log_success "Ollama 已安裝"
        return
    fi
    
    if [[ "$OS" == "linux" || "$OS" == "macos" ]]; then
        curl -fsSL https://ollama.ai/install.sh | sh
        log_success "Ollama 安裝完成"
    else
        error_exit "請手動安裝 Ollama: https://ollama.ai/download"
    fi
}

setup_python_env() {
    log_info "設置 Python 虛擬環境..."
    
    # 建立虛擬環境
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "虛擬環境建立完成"
    fi
    
    # 啟動虛擬環境
    source venv/bin/activate
    
    # 安裝依賴
    log_info "安裝 Python 依賴..."
    pip install --upgrade pip
    pip install -r requirements.txt
    log_success "依賴安裝完成"
}

setup_config() {
    log_info "設置配置檔案..."
    
    # 建立必要目錄
    mkdir -p data logs config/prompts
    
    # 複製配置檔案
    if [[ ! -f ".env" ]]; then
        cp .env.example .env
        log_success "環境變數檔案建立完成"
    fi
    
    if [[ ! -f "config/settings.yaml" ]]; then
        cp config/settings.yaml.example config/settings.yaml
        log_success "配置檔案建立完成"
    fi
}

start_services() {
    log_info "啟動服務..."
    
    # 啟動Ollama服務
    if ! pgrep -f "ollama serve" > /dev/null; then
        log_info "啟動 Ollama 服務..."
        ollama serve &
        sleep 10
    fi
    
    # 下載模型
    log_info "下載 Gemma2 模型 (約5.4GB)..."
    ollama pull gemma2:9b-instruct-q4_0
    log_success "模型下載完成"
    
    # 初始化資料庫
    log_info "初始化資料庫..."
    python scripts/setup_db.py
    log_success "資料庫初始化完成"
}

health_check() {
    log_info "執行健康檢查..."
    
    # 檢查Ollama服務
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        log_success "Ollama 服務正常"
    else
        log_error "Ollama 服務異常"
    fi
    
    # 檢查資料庫
    if python scripts/health_check.py; then
        log_success "系統健康檢查通過"
    else
        log_error "健康檢查失敗"
    fi
}

show_completion_message() {
    echo ""
    log_success "安裝完成！"
    echo ""
    echo "🎯 啟動指令:"
    echo "   source venv/bin/activate  # 啟動虛擬環境"
    echo "   streamlit run src/app.py  # 啟動應用程式"
    echo ""
    echo "🌐 訪問網址: http://localhost:8501"
    echo ""
    echo "📖 更多說明請參考:"
    echo "   - docs/installation.md"
    echo "   - docs/configuration.md"
    echo "   - docs/deployment.md"
    echo ""
    echo "🚀 Docker 快速啟動:"
    echo "   docker-compose up -d"
}

# 執行主函數
main "$@"
```

#### Day 5-6: 文檔撰寫
**檔案**: `docs/installation.md`

```markdown
# 安裝指南

## 系統需求

### 硬體需求
- **CPU**: Intel i5第8代以上或同等級AMD處理器
- **記憶體**: 16GB RAM (建議20GB)
- **儲存空間**: 20GB可用空間
- **網路**: 寬頻網路連線 (模型下載需要)

### 軟體需求
- **作業系統**: 
  - Ubuntu 20.04+ / CentOS 8+ / Debian 11+
  - macOS 11+ 
  - Windows 10/11 (需要WSL2)
- **Python**: 3.9+ 
- **Docker**: 20.10+ (可選，推薦)

## 安裝方法

### 方法一：一鍵安裝腳本 (推薦)

```bash
# 1. 克隆專案
git clone https://github.com/your-username/clinic-ai-query.git
cd clinic-ai-query

# 2. 執行安裝腳本
chmod +x scripts/install.sh
./scripts/install.sh

# 3. 啟動應用
source venv/bin/activate
streamlit run src/app.py
```

### 方法二：Docker Compose

```bash
# 1. 克隆專案
git clone https://github.com/your-username/clinic-ai-query.git
cd clinic-ai-query

# 2. 配置環境變數
cp .env.example .env
# 編輯 .env 檔案設定參數

# 3. 啟動服務
docker-compose up -d

# 4. 初次設定 (下載模型)
docker-compose --profile setup up model-loader
```

### 方法三：手動安裝

詳細的手動安裝步驟...

## 驗證安裝

安裝完成後，開啟瀏覽器訪問 http://localhost:8501

如果看到登入頁面，表示安裝成功。

## 故障排除

### 常見問題

1. **記憶體不足錯誤**
   - 檢查可用記憶體是否足夠
   - 關閉其他大型應用程式

2. **模型下載失敗**
   - 檢查網路連線
   - 重新執行 `ollama pull gemma2:9b-instruct-q4_0`

3. **埠號衝突**
   - 修改 .env 檔案中的 STREAMLIT_SERVER_PORT
   - 或停止占用8501埠的其他程式

更多故障排除方法請參考 [troubleshooting.md](troubleshooting.md)
```

**檔案**: `docs/configuration.md`
**檔案**: `docs/api_reference.md`  
**檔案**: `docs/deployment.md`

#### Day 7: 版本發布準備
**檔案**: `CHANGELOG.md`

```markdown
# 更新日誌

所有重要的專案變更都會記錄在這個檔案中。

本專案遵循 [語義化版本](https://semver.org/lang/zh-TW/) 規範。

## [未發布]

## [1.0.0] - 2025-01-24

### 新增
- 展望診療系統DBF檔案解析功能
- 自然語言轉SQL查詢功能  
- Gemma-3n本地LLM整合
- Streamlit網頁使用者介面
- 使用者認證和權限管理
- 查詢結果視覺化圖表
- Docker容器化部署
- 一鍵安裝腳本
- 完整的技術文檔

### 安全性
- SQL注入防護
- 敏感資料遮蔽
- 審計日誌記錄
- 會話管理

### 效能
- SQLite查詢最佳化
- 記憶體使用優化
- 查詢結果快取
```

**發布檢查清單**:
- [ ] 所有測試通過
- [ ] 文檔完整更新
- [ ] 版本號正確設定
- [ ] Docker鏡像構建成功
- [ ] 安裝腳本測試通過
- [ ] 範例資料準備完成
- [ ] 發布說明撰寫完成

#### ✅ 驗收標準:
- [ ] Docker一鍵部署成功，服務正常運行
- [ ] 安裝腳本在多個平台測試通過
- [ ] 技術文檔完整，涵蓋安裝、配置、使用
- [ ] API文檔準確，包含所有介面說明
- [ ] 首個穩定版本(v1.0.0)成功發布
- [ ] GitHub頁面完整，包含README、授權、貢獻指南

---

## 📊 品質控制檢查點

### 每週末檢查項目:
1. **程式碼品質**: 
   ```bash
   black src/ tests/           # 代碼格式化
   flake8 src/ tests/          # 代碼風格檢查
   mypy src/                   # 類型檢查
   ```

2. **測試覆蓋**: 
   ```bash
   pytest tests/ --cov=src --cov-report=html
   # 目標: >80% 覆蓋率
   ```

3. **效能基準**: 
   ```bash
   python tests/performance_test.py
   # 目標: 查詢回應<5秒
   ```

4. **安全掃描**: 
   ```bash
   bandit -r src/              # 安全漏洞掃描
   safety check                # 依賴漏洞檢查
   ```

5. **文檔同步**: 確保程式碼變更時同步更新文檔

### 關鍵風險緩解策略:

#### 1. Big5編碼問題
- **風險**: 中文字元解析錯誤
- **緩解**: 準備多種編碼測試資料，實作編碼自動偵測

#### 2. LLM推論效能
- **風險**: 回應時間過長
- **緩解**: 實作查詢快取機制，優化提示詞長度

#### 3. 醫療專業詞彙
- **風險**: 專業術語理解不準確  
- **緩解**: 建立完整的醫療詞彙對應表，支援使用者自訂

#### 4. 部署複雜度
- **風險**: 使用者安裝困難
- **緩解**: 提供多種部署選項，完善安裝腳本和文檔

#### 5. 資料安全性
- **風險**: 醫療資料洩露
- **緩解**: 嚴格本地化部署，完善存取控制和審計

## 🎯 最終交付成果

### 1. 完整開源項目
- [x] GitHub Repository with 完整項目結構
- [x] MIT開源授權
- [x] 標準化的貢獻指南
- [x] Issue和PR模板
- [x] GitHub Actions CI/CD

### 2. 核心功能實現
- [x] 展望DBF檔案解析器 (支援Big5編碼)
- [x] SQLite資料庫管理器 (含索引優化)
- [x] Gemma-3n LLM查詢代理
- [x] Streamlit Web使用者介面
- [x] 查詢結果視覺化系統

### 3. 部署和維運
- [x] Docker Compose一鍵部署
- [x] 跨平台安裝腳本
- [x] 健康檢查和監控
- [x] 日誌和審計系統
- [x] 備份和恢復機制

### 4. 測試和品質保證
- [x] 80%+單元測試覆蓋率
- [x] 整合測試和效能測試
- [x] 安全性測試和漏洞掃描
- [x] 代碼品質檢查和格式化
- [x] 持續整合和自動化測試

### 5. 技術文檔
- [x] 完整的安裝指南
- [x] 配置和部署文檔
- [x] API參考手冊
- [x] 故障排除指南
- [x] 開發者貢獻指南

### 6. 使用者體驗
- [x] 直觀的Web界面設計
- [x] 中文本地化支援
- [x] 回應式設計 (支援多設備)
- [x] 友善的錯誤處理和提示
- [x] 完整的使用者手冊

## 🚀 專案成功指標

- **技術指標**:
  - 查詢回應時間 < 5秒
  - 系統可用性 > 99%
  - SQL生成準確率 > 90%
  - 測試覆蓋率 > 80%

- **使用者指標**:
  - 一鍵安裝成功率 > 95%
  - 使用者滿意度 > 4.5/5
  - 文檔完整度評分 > 4.0/5

- **社群指標**:
  - GitHub Stars > 100
  - 活躍貢獻者 > 5人
  - Issue解決率 > 90%

這個開發計劃確保每個階段都有具體的可測試交付成果，並且遵循開源項目的最佳實踐，為診所提供一個完整、安全、易用的AI查詢系統。