# 診所AI查詢系統 - CLAUDE.md

## 專案概述
基於本地LLM的診所資料庫智能查詢系統，專門處理展望診療系統的DBF格式資料，提供自然語言查詢功能。

## 系統架構
```
展望DBF檔案 → DBF解析器(Big5) → SQLite本地庫 → Gemma-3n模型 → Streamlit介面
```

## 核心規格

### 資料規模
- **病患數量**: 約5萬人
- **看診記錄**: 15年 × 300天 × 100人次 ≈ 45萬筆
- **總資料量**: 約600MB
- **日均查詢**: 預估50-100次

### 技術棧
- **LLM模型**: Gemma-3n-9B (首選)
- **資料庫**: SQLite + 性能優化
- **DBF解析**: simpledbf + Big5編碼處理
- **介面**: Streamlit + 認證模組
- **部署**: 本地化部署 (符合醫療法規)

### 硬體需求
- **CPU**: Intel i5第8代以上
- **RAM**: 16GB (建議20GB)
- **儲存**: 20GB可用空間
- **作業系統**: Windows 10/11

## 展望系統資料庫結構

### 主要檔案結構
```python
ANCHIA_LAB_SCHEMA = {
    'CO01M.dbf': {    # 病患主資料表
        'description': '病患核心靜態資料，個人基本資訊、聯絡方式及重要醫療註記',
        'primary_key': 'kcstmr',
        'encoding': 'big5',
        'key_fields': {
            'kcstmr': '病歷號 (七位數字，主鍵)',
            'mname': '病患姓名',
            'msex': '性別',
            'mbirthdt': '出生年月日',
            'mtelh': '電話/行動電話',
            'mweight': '體重',
            'mheight': '身高',
            'maddr': '地址',
            'mpersonid': '身分證字號',
            'mlcasedate': '最後就診日期',
            'mlcasedise': '最後就診主診斷'
        }
    },
    'CO02M.dbf': {    # 處方記錄檔
        'description': '病患用藥處方或治療項目記錄',
        'primary_key': ['kcstmr', 'idate', 'itime', 'dno'],
        'encoding': 'big5',
        'key_fields': {
            'kcstmr': '病歷號',
            'idate': '開立日期',
            'itime': '開立時間',
            'dno': '藥品代碼/醫令代碼',
            'ptp': '藥品類型',
            'pfq': '使用頻率 (如：TID)',
            'ptday': '總天數'
        }
    },
    'CO03M.dbf': {    # 就診摘要檔
        'description': '就診申請單摘要資訊，包含診斷與帳務資料',
        'primary_key': ['kcstmr', 'idate', 'itime'],
        'encoding': 'big5',
        'key_fields': {
            'kcstmr': '病歷號',
            'idate': '就醫日期',
            'itime': '就醫時間',
            'labno': '主診斷',
            'lacd01': '次診斷01',
            'lacd02': '次診斷02',
            'lacd03': '次診斷03',
            'tot': '申報金額',
            'sa98': '部分負擔',
            'ipk3': '醫師'
        }
    },
    'CO18H.dbf': {    # 檢驗結果歷史檔
        'description': '檢驗數據與生理數據記錄，如檢驗值、身高體重等',
        'primary_key': ['kcstmr', 'hdate', 'htime', 'hitem'],
        'encoding': 'big5',
        'key_fields': {
            'kcstmr': '病歷號',
            'hdate': '記錄日期',
            'htime': '記錄時間',
            'hitem': '檢驗項目代碼',
            'hdscp': '項目描述',
            'hval': '檢驗數值',
            'hresult': '檢驗結果(文字)',
            'hrule': '參考值範圍'
        }
    }
}
```

## 功能需求

### 核心查詢類型
1. **病患查詢**: "王小明最近6個月的看診記錄和檢驗結果"
2. **處方分析**: "糖尿病患者最近一年的用藥統計分析"
3. **檢驗追蹤**: "血糖值超標患者的HbA1c變化趨勢"
4. **診斷統計**: "去年各月份主要診斷分布情況"
5. **收費分析**: "月收入與就診人次關聯分析"

### 典型SQL查詢範例
```sql
-- 病患基本資料查詢
SELECT m.mname, m.msex, m.mbirthdt, m.mlcasedate 
FROM CO01M m 
WHERE m.mname LIKE '%王小明%';

-- 用藥頻率統計
SELECT c2.dno, c2.pfq, COUNT(*) as frequency
FROM CO02M c2 
JOIN CO03M c3 ON c2.kcstmr = c3.kcstmr AND c2.idate = c3.idate
WHERE c3.labno LIKE '%糖尿病%'
GROUP BY c2.dno, c2.pfq;

-- 檢驗值趨勢分析
SELECT c18.hdate, c18.hval, c18.hrule
FROM CO18H c18
JOIN CO01M c1 ON c18.kcstmr = c1.kcstmr
WHERE c18.hdscp LIKE '%血糖%' 
AND c1.mname = '王小明'
ORDER BY c18.hdate DESC;
```

### 必要功能清單
- [ ] 展望DBF檔案解析 (Big5編碼)
- [ ] 四表關聯查詢優化
- [ ] SQLite資料庫建置與索引
- [ ] Gemma-3n本地部署
- [ ] 自然語言→SQL轉換
- [ ] 檢驗值範圍判斷邏輯
- [ ] 診斷代碼對應功能
- [ ] 統計視覺化圖表
- [ ] 使用者認證與權限控制
- [ ] 查詢日誌與審計追蹤

## 安全與合規

### 醫療法規要求
- **個資法遵循**: 所有資料本地處理，不上傳雲端
- **醫療法第67條**: 病歷保密，存取記錄完整
- **權限分級**: 不同醫師存取不同範圍資料
- **資料脫敏**: 顯示時部分敏感資訊遮蔽

### 技術安全措施
```python
SECURITY_CONFIG = {
    'database_encryption': True,
    'access_logging': True,
    'session_timeout': 1800,  # 30分鐘
    'max_query_results': 1000,
    'sensitive_fields_mask': ['mpersonid', 'mtelh', 'mfml']
}
```

## 開發階段

### 第一階段 (1週): 資料探索
- [ ] 分析四個DBF檔案結構與關聯性
- [ ] 測試Big5編碼解析
- [ ] 建立SQLite轉換與索引策略

### 第二階段 (2週): MVP開發
- [ ] 完成四表DBF→SQLite轉換器
- [ ] 部署Gemma-3n模型
- [ ] 實作跨表關聯查詢邏輯
- [ ] 建立Streamlit介面原型

### 第三階段 (1週): 醫療專業化
- [ ] 診斷代碼解析與對應
- [ ] 檢驗值正常範圍判斷
- [ ] 常用醫療查詢模板
- [ ] 統計報表功能

### 第四階段 (1週): 測試與優化
- [ ] 真實資料全量測試
- [ ] 跨表查詢性能優化
- [ ] 安全性檢查與認證
- [ ] 使用者介面優化

## 性能優化

### SQLite設定
```python
SQLITE_CONFIG = {
    'journal_mode': 'WAL',
    'synchronous': 'NORMAL',
    'cache_size': 10000,     # 40MB快取
    'temp_store': 'MEMORY',
    'mmap_size': 268435456   # 256MB記憶體映射
}
```

### 關鍵索引策略
```sql
-- CO01M 病患主檔索引
CREATE INDEX idx_co01m_kcstmr ON CO01M(kcstmr);
CREATE INDEX idx_co01m_name ON CO01M(mname);
CREATE INDEX idx_co01m_lastcase ON CO01M(mlcasedate);

-- CO02M 處方檔索引
CREATE INDEX idx_co02m_patient_date ON CO02M(kcstmr, idate);
CREATE INDEX idx_co02m_drug ON CO02M(dno);
CREATE INDEX idx_co02m_composite ON CO02M(kcstmr, idate, itime);

-- CO03M 就診摘要索引
CREATE INDEX idx_co03m_patient_date ON CO03M(kcstmr, idate);
CREATE INDEX idx_co03m_diagnosis ON CO03M(labno);
CREATE INDEX idx_co03m_doctor ON CO03M(ipk3);

-- CO18H 檢驗結果索引
CREATE INDEX idx_co18h_patient_date ON CO18H(kcstmr, hdate);
CREATE INDEX idx_co18h_item ON CO18H(hitem);
CREATE INDEX idx_co18h_desc ON CO18H(hdscp);
```

## 開源部署方案

### 項目結構
```
clinic-ai-query/
├── README.md
├── LICENSE (MIT)
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── setup.py
├── src/
│   ├── __init__.py
│   ├── app.py              # Streamlit主程式
│   ├── config.py           # 配置管理
│   ├── auth.py            # 認證模組
│   └── modules/
│       ├── __init__.py
│       ├── dbf_parser.py   # DBF解析器
│       ├── db_manager.py   # 資料庫管理
│       ├── llm_agent.py    # LLM查詢代理
│       └── visualizer.py   # 視覺化模組
├── data/
│   ├── .gitkeep
│   └── sample/            # 範例DBF檔案 (脫敏)
├── config/
│   ├── settings.yaml
│   └── prompts/
│       ├── system_prompt.txt
│       └── sql_examples.txt
├── scripts/
│   ├── install.sh         # 一鍵安裝腳本
│   ├── setup_db.py        # 資料庫初始化
│   └── health_check.py    # 系統健康檢查
├── tests/
│   ├── __init__.py
│   ├── test_dbf_parser.py
│   ├── test_db_manager.py
│   └── test_llm_agent.py
└── docs/
    ├── installation.md
    ├── configuration.md
    ├── api_reference.md
    └── deployment.md
```

### 一鍵部署方案

#### 方案一：Docker部署 (推薦)
```bash
# 1. 克隆項目
git clone https://github.com/[username]/clinic-ai-query.git
cd clinic-ai-query

# 2. 配置環境變數
cp .env.example .env
# 編輯 .env 檔案設定參數

# 3. 一鍵啟動
docker-compose up -d

# 4. 檢查狀態
docker-compose ps
```

#### Docker Compose 配置
```yaml
# docker-compose.yml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
      - ./models:/models
    environment:
      - OLLAMA_HOST=0.0.0.0
    command: serve
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  clinic-ai:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DATABASE_PATH=/app/data/anchia_lab.db
      - LOG_LEVEL=INFO
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  model-loader:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ollama_data:/root/.ollama
    command: >
      bash -c "
        ollama pull llama3:8b-instruct &&
        echo 'Model loaded successfully'
      "
    profiles:
      - setup

volumes:
  ollama_data:
```

#### 方案二：自動化安裝腳本
```bash
#!/bin/bash
# scripts/install.sh

set -e

echo "🏥 診所AI查詢系統 - 自動安裝"
echo "================================"

# 檢查作業系統
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
else
    echo "❌ 不支援的作業系統: $OSTYPE"
    exit 1
fi

echo "📋 檢測到作業系統: $OS"

# 檢查Python版本
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安裝，請先安裝 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "🐍 Python 版本: $PYTHON_VERSION"

# 安裝Ollama
echo "🤖 安裝 Ollama..."
if [[ "$OS" == "linux" || "$OS" == "macos" ]]; then
    curl -fsSL https://ollama.ai/install.sh | sh
elif [[ "$OS" == "windows" ]]; then
    echo "請手動下載並安裝 Ollama: https://ollama.ai/download/windows"
    read -p "安裝完成後按 Enter 繼續..."
fi

# 創建虛擬環境
echo "📦 創建虛擬環境..."
python3 -m venv venv

# 啟動虛擬環境
if [[ "$OS" == "windows" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# 安裝依賴
echo "📚 安裝 Python 依賴..."
pip install --upgrade pip
pip install -r requirements.txt

# 創建必要目錄
echo "📁 創建目錄結構..."
mkdir -p data logs config/prompts

# 複製配置檔案
echo "⚙️ 設定配置檔案..."
cp .env.example .env
cp config/settings.yaml.example config/settings.yaml

# 啟動Ollama服務
echo "🚀 啟動 Ollama 服務..."
if [[ "$OS" == "macos" || "$OS" == "linux" ]]; then
    ollama serve &
    sleep 5
fi

# 下載模型
echo "📥 下載 Gemma-3n 模型 (約5.4GB)..."
ollama pull llama3:8b-instruct

# 初始化資料庫
echo "🗄️ 初始化資料庫..."
python scripts/setup_db.py

# 健康檢查
echo "🔍 執行健康檢查..."
python scripts/health_check.py

echo ""
echo "✅ 安裝完成！"
echo ""
echo "🎯 啟動指令:"
echo "   source venv/bin/activate  # 啟動虛擬環境"
echo "   streamlit run src/app.py  # 啟動應用程式"
echo ""
echo "🌐 訪問網址: http://localhost:8501"
echo ""
echo "📖 更多說明請參考: docs/installation.md"
```

### 配置管理

#### 環境變數配置 (.env)
```bash
# .env.example
# 基本設定
APP_NAME=診所AI查詢系統
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=your-secret-key-here

# LLM設定
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b-instruct
OLLAMA_TIMEOUT=30

# 資料庫設定  
DATABASE_PATH=./data/anchia_lab.db
DBF_DATA_PATH=./data/dbf_files/
BACKUP_PATH=./data/backups/

# 安全設定
SESSION_TIMEOUT=1800
MAX_QUERY_RESULTS=1000
ENABLE_AUDIT_LOG=true

# 日誌設定
LOG_LEVEL=INFO
LOG_FILE=./logs/clinic_ai.log
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5

# Streamlit設定
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

#### 系統配置 (config/settings.yaml)
```yaml
# settings.yaml
system:
  name: "診所AI查詢系統"
  version: "1.0.0"
  author: "開源社群"
  license: "MIT"

database:
  type: "sqlite"
  encoding: "big5"
  tables:
    - "CO01M"  # 病患主檔
    - "CO02M"  # 處方檔  
    - "CO03M"  # 就診摘要
    - "CO18H"  # 檢驗結果

llm:
  provider: "ollama"
  model: "llama3:8b-instruct"
  temperature: 0.1
  max_tokens: 2048
  system_prompt_file: "config/prompts/system_prompt.txt"

security:
  enable_auth: true
  session_timeout: 1800
  max_login_attempts: 3
  sensitive_fields:
    - "mpersonid"
    - "mtelh" 
    - "mfml"

ui:
  theme: "light"
  language: "zh-TW"
  page_title: "診所AI查詢系統"
  sidebar_title: "功能選單"
```

### 完整安裝文檔

#### requirements.txt
```txt
streamlit>=1.28.0
pandas>=2.0.0  
sqlite3
simpledbf>=0.2.6
ollama>=0.1.7
langchain>=0.1.0
plotly>=5.15.0
pyyaml>=6.0
python-dotenv>=1.0.0
bcrypt>=4.0.0
loguru>=0.7.0
pytest>=7.0.0
pytest-cov>=4.0.0
black>=23.0.0
flake8>=6.0.0
pre-commit>=3.0.0
```

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴檔案
COPY requirements.txt .

# 安裝Python依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY . .

# 創建必要目錄
RUN mkdir -p data logs config

# 設定權限
RUN chmod +x scripts/*.py

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/healthz || exit 1

# 暴露端口
EXPOSE 8501

# 啟動命令
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 開發工具配置

#### GitHub Actions CI/CD
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.9
      uses: actions/setup-python@v3
      with:
        python-version: 3.9
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        
    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml
        
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  docker:
    needs: test
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t clinic-ai-query:latest .
        
    - name: Test Docker image
      run: |
        docker run --rm -d -p 8501:8501 clinic-ai-query:latest
        sleep 30
        curl -f http://localhost:8501/healthz
```

### 常用指令

#### 開發環境
```bash
# 克隆項目
git clone https://github.com/[username]/clinic-ai-query.git
cd clinic-ai-query

# 自動安裝 (推薦)
chmod +x scripts/install.sh
./scripts/install.sh

# 手動安裝
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 啟動開發服務器
streamlit run src/app.py

# 執行測試
pytest tests/ -v

# 程式碼格式化
black src/ tests/
flake8 src/ tests/
```

#### 生產部署
```bash
# Docker 部署
docker-compose up -d

# 檢查服務狀態
docker-compose ps
docker-compose logs clinic-ai

# 停止服務
docker-compose down

# 備份資料
docker-compose exec clinic-ai python scripts/backup.py

# 更新系統
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

## 資料關聯邏輯

### 主要關聯關係
```python
TABLE_RELATIONSHIPS = {
    'patient_prescriptions': {
        'tables': ['CO01M', 'CO02M'],
        'join_key': 'kcstmr',
        'description': '病患與處方記錄關聯'
    },
    'visit_diagnosis': {
        'tables': ['CO01M', 'CO03M'], 
        'join_key': 'kcstmr',
        'description': '病患與就診診斷關聯'
    },
    'lab_results': {
        'tables': ['CO01M', 'CO18H'],
        'join_key': 'kcstmr', 
        'description': '病患與檢驗結果關聯'
    },
    'prescription_visit': {
        'tables': ['CO02M', 'CO03M'],
        'join_key': ['kcstmr', 'idate', 'itime'],
        'description': '處方與就診記錄關聯'
    }
}
```

### 複雜查詢範例
```sql
-- 完整病患就診歷程
SELECT 
    c1.mname as 病患姓名,
    c3.idate as 就診日期,
    c3.labno as 主診斷,
    GROUP_CONCAT(c2.dno) as 處方藥品,
    GROUP_CONCAT(c18.hdscp || ':' || c18.hval) as 檢驗結果
FROM CO01M c1
LEFT JOIN CO03M c3 ON c1.kcstmr = c3.kcstmr
LEFT JOIN CO02M c2 ON c3.kcstmr = c2.kcstmr AND c3.idate = c2.idate
LEFT JOIN CO18H c18 ON c1.kcstmr = c18.kcstmr AND c3.idate = c18.hdate
WHERE c1.mname = '王小明'
GROUP BY c1.kcstmr, c3.idate, c3.labno
ORDER BY c3.idate DESC;
```

## 預期成果

### 查詢效能目標
- **單表查詢**: <100ms
- **雙表關聯**: <500ms
- **四表複雜查詢**: 1-3秒
- **LLM推論時間**: 2-3秒
- **總回應時間**: <5秒

### 準確率目標
- **SQL生成正確率**: >90%
- **中文醫療詞彙理解**: >85%
- **跨表關聯查詢**: >95%
- **檢驗值判讀準確性**: >90%

## 維護注意事項

### 定期任務
- [ ] 每月備份SQLite資料庫
- [ ] 每季檢查索引效能
- [ ] 每年更新診斷代碼對應表
- [ ] 定期清理查詢日誌 (保留6個月)

### 故障排除
- **記憶體不足**: 檢查Gemma-3n模型載入狀態
- **DBF解析錯誤**: 確認Big5編碼與檔案完整性  
- **跨表查詢緩慢**: 檢查關聯索引完整性
- **檢驗值解析錯誤**: 確認hval欄位數值格式

## 未來擴展

### 短期規劃 (6個月內)
- [ ] 支援更多檢驗項目自動判讀
- [ ] 增加時間序列分析圖表
- [ ] 優化複雜統計查詢效能

### 長期規劃 (1年內)
- [ ] 整合其他診所系統格式
- [ ] 開發檢驗值預警系統
- [ ] 加入AI輔助診斷建議

---

**重要提醒**:
1. 所有病患資料嚴禁上傳雲端
2. 系統上線前必須通過資安檢查  
3. 定期備份四個核心DBF檔案
4. 遵循醫療法規，維護病患隱私
5. 注意Big5編碼轉換的資料完整性

**聯絡資訊**:
- 開發者: [診所醫師]
- 技術支援: Claude AI Assistant  
- 更新日期: 2025-01-24