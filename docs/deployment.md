# 診所AI查詢系統部署指南

本文件詳細說明診所AI查詢系統的部署流程，包括不同環境的部署選項、配置說明和故障排除。

## 📋 部署前準備

### 系統需求

#### 硬體需求
- **CPU**: Intel i5第8代以上或同等級AMD處理器 (4核心以上)
- **記憶體**: 16GB RAM (推薦20GB以上，LLM模型需要約5-8GB)
- **儲存空間**: 
  - 系統檔案: 2GB
  - LLM模型: 5GB (Llama3:8b)
  - 資料庫空間: 根據資料量而定 (建議預留10GB以上)
  - 日誌和備份: 2GB
- **網路**: 穩定的網際網路連線 (首次部署需要下載模型)

#### 軟體需求
- **作業系統**: 
  - Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+)
  - macOS 10.15+
  - Windows 10/11 (透過WSL2)
- **Python**: 3.9+ (3.10推薦)
- **Docker**: 20.10+ (可選，推薦用於生產環境)
- **Docker Compose**: 2.0+ (如使用Docker部署)

### 網路需求
- **對外連線**: 需要存取 Ollama 模型倉庫 (huggingface.co)
- **內部連線**: 
  - Streamlit Web界面: 8501端口
  - Ollama LLM服務: 11434端口
- **防火牆設定**: 確保相關端口可被內網存取

## 🚀 部署方式

### 方式一：Docker Compose 部署 (推薦)

這是最簡單且最穩定的部署方式，適合生產環境使用。

#### 1. 準備部署檔案

```bash
# 克隆專案
git clone https://github.com/leon80148/chat4lab.git
cd chat4lab

# 複製環境配置檔案
cp .env.example .env
```

#### 2. 配置環境變數

編輯 `.env` 檔案：

```bash
# LLM設定
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b-instruct

# 資料庫設定
DATABASE_PATH=./data/anchia_lab.db
DBF_DATA_PATH=./data/dbf_files/

# 應用設定
STREAMLIT_PORT=8501
LOG_LEVEL=INFO

# 安全設定
SESSION_TIMEOUT=1800
MAX_QUERY_RESULTS=1000
AUTH_ENABLED=true

# 資料庫效能設定
DB_CACHE_SIZE=-64000
DB_JOURNAL_MODE=WAL
DB_SYNCHRONOUS=NORMAL
```

#### 3. 建立資料目錄

```bash
# 建立必要的目錄結構
mkdir -p data/dbf_files
mkdir -p data/logs
mkdir -p data/backups

# 設定適當的權限
chmod 755 data/
chmod 755 data/dbf_files/
chmod 755 data/logs/
chmod 755 data/backups/
```

#### 4. 啟動服務

```bash
# 啟動所有服務
docker-compose up -d

# 查看服務狀態
docker-compose ps

# 查看日誌
docker-compose logs -f
```

#### 5. 初始化LLM模型

```bash
# 下載並初始化Llama3模型 (首次執行需要約10-15分鐘)
docker-compose --profile setup up model-loader

# 驗證模型是否正確載入
docker-compose exec ollama ollama list
```

#### 6. 驗證部署

```bash
# 檢查Web界面是否可存取
curl http://localhost:8501

# 檢查Ollama服務是否正常
curl http://localhost:11434/api/tags

# 執行系統健康檢查
docker-compose exec app python scripts/health_check.py
```

### 方式二：手動安裝部署

適合開發環境或需要自訂安裝的情況。

#### 1. 安裝系統依賴

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip curl
```

**CentOS/RHEL:**
```bash
sudo yum update
sudo yum install -y python39 python39-pip curl
```

#### 2. 安裝Ollama

```bash
# 下載並安裝Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 啟動Ollama服務
sudo systemctl start ollama
sudo systemctl enable ollama

# 下載Llama3模型
ollama pull llama3:8b-instruct
```

#### 3. 準備Python環境

```bash
# 克隆專案
git clone https://github.com/leon80148/chat4lab.git
cd chat4lab

# 建立虛擬環境
python3.10 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. 配置系統

```bash
# 複製配置檔案
cp .env.example .env
cp config/settings.yaml.example config/settings.yaml

# 編輯配置檔案 (使用您偏好的編輯器)
nano .env
nano config/settings.yaml
```

#### 5. 初始化資料庫

```bash
# 建立資料目錄
mkdir -p data/dbf_files data/logs data/backups

# 初始化資料庫
python scripts/setup_db.py

# 驗證資料庫設置
python scripts/verify_setup.py
```

#### 6. 啟動應用

```bash
# 啟動Streamlit應用
streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0
```

### 方式三：自動安裝腳本

提供一鍵安裝選項，適合快速測試和開發。

```bash
# 下載並執行安裝腳本
git clone https://github.com/leon80148/chat4lab.git
cd chat4lab
chmod +x scripts/install.sh
./scripts/install.sh

# 啟動服務
source venv/bin/activate
streamlit run src/app.py
```

## ⚙️ 進階配置

### 生產環境優化

#### 1. 反向代理設定 (Nginx)

建立 `/etc/nginx/sites-available/chat4lab`：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 重導向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL設定
    ssl_certificate /path/to/your/certificate.pem;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    # 代理設定
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支援
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
    
    # 靜態檔案快取
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

啟用配置：
```bash
sudo ln -s /etc/nginx/sites-available/chat4lab /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 2. 系統服務設定 (systemd)

建立 `/etc/systemd/system/chat4lab.service`：

```ini
[Unit]
Description=Chat4Lab AI Query System
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=exec
User=chat4lab
Group=chat4lab
WorkingDirectory=/opt/chat4lab
Environment=PATH=/opt/chat4lab/venv/bin
ExecStart=/opt/chat4lab/venv/bin/streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

# 安全設定
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/chat4lab/data

[Install]
WantedBy=multi-user.target
```

啟用服務：
```bash
sudo systemctl daemon-reload
sudo systemctl enable chat4lab.service
sudo systemctl start chat4lab.service
sudo systemctl status chat4lab.service
```

#### 3. 日誌輪轉設定

建立 `/etc/logrotate.d/chat4lab`：

```
/opt/chat4lab/data/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 chat4lab chat4lab
    postrotate
        systemctl reload chat4lab.service
    endscript
}
```

### 效能調優

#### 1. 資料庫優化

在 `config/settings.yaml` 中調整資料庫設定：

```yaml
database:
  performance:
    cache_size: -128000  # 128MB快取
    journal_mode: "WAL"
    synchronous: "NORMAL"
    temp_store: "MEMORY"
    mmap_size: 268435456  # 256MB memory map
    page_size: 4096
  
  connection_pool:
    max_connections: 20
    timeout: 30
    
  backup:
    enabled: true
    interval: 3600  # 每小時備份
    retention_days: 30
```

#### 2. LLM模型優化

```yaml
llm:
  model: "llama3:8b-instruct"
  parameters:
    temperature: 0.2
    max_tokens: 2048
    context_length: 4096
    
  optimization:
    batch_processing: true
    cache_responses: true
    cache_size: 1000
    
  resource_limits:
    max_concurrent_requests: 3
    request_timeout: 30
    memory_limit: "8GB"
```

### 監控和日誌

#### 1. 系統監控

安裝監控組件：

```bash
# 安裝Prometheus和Grafana (Docker)
docker-compose -f docker-compose.monitoring.yml up -d

# 或使用現有監控系統的配置
```

在 `config/settings.yaml` 中啟用監控：

```yaml
monitoring:
  enabled: true
  metrics:
    endpoint: "/metrics"
    port: 9090
    
  health_check:
    endpoint: "/health"
    interval: 30
    
  alerts:
    enabled: true
    webhook_url: "https://your-alert-system.com/webhook"
```

#### 2. 日誌配置

```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  handlers:
    file:
      enabled: true
      path: "./data/logs/chat4lab.log"
      max_size: "10MB"
      backup_count: 5
      
    syslog:
      enabled: false
      address: "localhost:514"
      
  loggers:
    "src.modules.llm_agent":
      level: "DEBUG"
    "src.modules.db_manager":
      level: "INFO"
```

## 🔒 安全配置

### 1. 認證和授權

```yaml
security:
  authentication:
    enabled: true
    method: "local"  # local, ldap, oauth
    
  session:
    timeout: 1800  # 30分鐘
    secure_cookie: true
    same_site: "Strict"
    
  access_control:
    max_query_results: 1000
    rate_limiting:
      enabled: true
      requests_per_minute: 60
```

### 2. 資料保護

```yaml
data_protection:
  encryption:
    enabled: true
    algorithm: "AES-256-GCM"
    
  sensitive_fields:
    mask_enabled: true
    fields: ["mpersonid", "mtelh", "maddr"]
    
  audit_log:
    enabled: true
    log_queries: true
    log_results: false
    retention_days: 90
```

### 3. 網路安全

```bash
# 防火牆設定 (ufw)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow from 192.168.1.0/24 to any port 8501  # 限制內網存取
```

## 🗂️ 資料管理

### DBF檔案匯入

#### 1. 準備DBF檔案

```bash
# 建立DBF檔案目錄結構
mkdir -p data/dbf_files/{CO01M,CO02M,CO03M,CO18H}

# 複製展望系統的DBF檔案到對應目錄
# 確保檔案編碼為Big5
```

#### 2. 批次匯入

```bash
# 使用匯入腳本
python scripts/import_dbf.py --data-dir ./data/dbf_files --batch-size 1000

# 驗證匯入結果
python scripts/verify_data.py
```

#### 3. 資料備份

```bash
# 建立自動備份腳本
cat > scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/chat4lab/data/backups"
DB_PATH="/opt/chat4lab/data/anchia_lab.db"
DATE=$(date +%Y%m%d_%H%M%S)

# 建立資料庫備份
sqlite3 $DB_PATH ".backup $BACKUP_DIR/anchia_lab_$DATE.db"

# 壓縮備份檔案
gzip "$BACKUP_DIR/anchia_lab_$DATE.db"

# 清理超過30天的備份
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "備份完成: anchia_lab_$DATE.db.gz"
EOF

chmod +x scripts/backup.sh

# 設定定時備份 (crontab)
echo "0 2 * * * /opt/chat4lab/scripts/backup.sh" | sudo crontab -
```

## 🔧 故障排除

### 常見問題

#### 1. LLM模型無法載入

**問題**: Ollama無法載入Llama3模型

**解決方案**:
```bash
# 檢查Ollama服務狀態
sudo systemctl status ollama

# 檢查可用模型
ollama list

# 重新下載模型
ollama pull llama3:8b-instruct

# 檢查系統記憶體
free -h

# 檢查磁碟空間
df -h
```

#### 2. 資料庫連線問題

**問題**: 無法連接到SQLite資料庫

**解決方案**:
```bash
# 檢查資料庫檔案權限
ls -la data/anchia_lab.db

# 檢查資料庫完整性
sqlite3 data/anchia_lab.db "PRAGMA integrity_check;"

# 重建資料庫索引
sqlite3 data/anchia_lab.db "REINDEX;"

# 檢查磁碟空間
df -h data/
```

#### 3. Web界面無法存取

**問題**: Streamlit界面無法載入

**解決方案**:
```bash
# 檢查Streamlit程序
ps aux | grep streamlit

# 檢查端口使用情況
netstat -tlnp | grep 8501

# 檢查防火牆設定
sudo ufw status

# 檢查應用日誌
tail -f data/logs/chat4lab.log
```

#### 4. 效能問題

**問題**: 查詢回應緩慢

**解決方案**:
```bash
# 檢查系統資源使用
top
htop
iotop

# 檢查資料庫查詢效能
sqlite3 data/anchia_lab.db "EXPLAIN QUERY PLAN SELECT * FROM CO01M WHERE mname LIKE '%test%';"

# 重建資料庫統計
sqlite3 data/anchia_lab.db "ANALYZE;"

# 檢查LLM回應時間
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "llama3:8b-instruct",
  "prompt": "Test prompt",
  "stream": false
}'
```

### 日誌分析

#### 1. 應用日誌

```bash
# 查看最新日誌
tail -f data/logs/chat4lab.log

# 搜尋錯誤
grep "ERROR" data/logs/chat4lab.log

# 分析查詢效能
grep "execution_time" data/logs/chat4lab.log | awk '{print $NF}' | sort -n
```

#### 2. 系統日誌

```bash
# 查看系統服務日誌
sudo journalctl -u chat4lab.service -f

# 查看Ollama日誌
sudo journalctl -u ollama.service -f

# 查看Nginx日誌 (如有使用)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 📊 效能基準

### 預期效能指標

| 指標 | 目標值 | 備註 |
|------|--------|------|
| 系統啟動時間 | < 30秒 | 包含模型載入 |
| 簡單查詢回應 | < 3秒 | 單表查詢 |
| 複雜查詢回應 | < 8秒 | 多表JOIN查詢 |
| LLM生成時間 | < 10秒 | 自然語言轉SQL |
| 並發查詢支援 | 10+ | 同時線上用戶 |
| 資料匯入速度 | 1000筆/秒 | DBF資料匯入 |
| 記憶體使用 | < 12GB | 穩定運行狀態 |
| CPU使用率 | < 70% | 高負載情況 |

### 效能測試

```bash
# 執行內建效能測試
python -m pytest tests/test_performance.py -v

# 資料庫效能測試
python scripts/performance_test.py --database

# LLM效能測試
python scripts/performance_test.py --llm

# 完整系統壓力測試
python scripts/stress_test.py --users 20 --duration 300
```

## 🔄 更新和維護

### 系統更新

```bash
# 停止服務
sudo systemctl stop chat4lab

# 備份當前版本
cp -r /opt/chat4lab /opt/chat4lab.backup.$(date +%Y%m%d)

# 拉取最新代碼
cd /opt/chat4lab
git pull origin main

# 更新依賴
source venv/bin/activate
pip install --upgrade -r requirements.txt

# 執行資料庫遷移 (如有需要)
python scripts/migrate_db.py

# 重啟服務
sudo systemctl start chat4lab
sudo systemctl status chat4lab
```

### 定期維護

建立定期維護腳本 `scripts/maintenance.sh`：

```bash
#!/bin/bash
echo "開始定期維護 - $(date)"

# 清理日誌
find /opt/chat4lab/data/logs -name "*.log.*" -mtime +7 -delete

# 資料庫維護
sqlite3 /opt/chat4lab/data/anchia_lab.db "VACUUM;"
sqlite3 /opt/chat4lab/data/anchia_lab.db "ANALYZE;"

# 檢查磁碟空間
df -h /opt/chat4lab/data

# 檢查系統狀態
systemctl status chat4lab.service

echo "定期維護完成 - $(date)"
```

設定週期執行：
```bash
# 每週日凌晨3點執行維護
echo "0 3 * * 0 /opt/chat4lab/scripts/maintenance.sh >> /var/log/chat4lab-maintenance.log 2>&1" | sudo crontab -
```

---

## 📞 技術支援

如果在部署過程中遇到問題，請參考：

- **GitHub Issues**: https://github.com/leon80148/chat4lab/issues
- **技術文檔**: https://github.com/leon80148/chat4lab/docs
- **聯絡作者**: leon80148@gmail.com

部署成功後，請訪問 `http://your-server:8501` 開始使用診所AI查詢系統！