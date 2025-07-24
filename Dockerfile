FROM python:3.11-slim

LABEL maintainer="Leon Lu <leon80148@gmail.com>"
LABEL description="診所AI查詢系統 - Clinic AI Query System"
LABEL version="1.0.0"
LABEL repository="https://github.com/leon80148/chat4lab"

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 建立非root使用者 (安全最佳實踐)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 切換至非root使用者
USER appuser

# 設置Python路徑
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 複製依賴檔案
COPY --chown=appuser:appuser requirements.txt .

# 安裝Python依賴
RUN pip install --no-cache-dir --user -r requirements.txt

# 將使用者的pip bin目錄加入PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# 複製應用程式碼
COPY --chown=appuser:appuser . .

# 建立必要目錄並設置權限
RUN mkdir -p data logs config && \
    chmod +x scripts/*.py || true

# 健康檢查端點
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/healthz || exit 1

# 暴露Streamlit預設端口
EXPOSE 8501

# 啟動命令
CMD ["python", "-m", "streamlit", "run", "src/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.runOnSave=false"]