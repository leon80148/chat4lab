#!/bin/bash
set -euo pipefail

# 診所AI查詢系統 - 一鍵安裝腳本
# Author: Leon Lu
# Repository: https://github.com/leon80148/chat4lab

# ===================
# 顏色定義
# ===================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# ===================
# 日誌函數
# ===================
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

log_step() {
    echo -e "${PURPLE}🔄 $1${NC}"
}

# ===================
# 錯誤處理
# ===================
error_exit() {
    log_error "$1"
    exit 1
}

cleanup_on_exit() {
    if [[ $? -ne 0 ]]; then
        log_error "安裝過程中發生錯誤，正在清理..."
        # 清理臨時檔案
        rm -rf temp_* 2>/dev/null || true
    fi
}

trap cleanup_on_exit EXIT

# ===================
# 工具函數
# ===================
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

get_os() {
    case "$OSTYPE" in
        linux-gnu*) echo "linux" ;;
        darwin*) echo "macos" ;;
        msys*|cygwin*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

get_memory_gb() {
    local os=$(get_os)
    if [[ "$os" == "linux" ]]; then
        free -g | awk '/^Mem:/{print $2}'
    elif [[ "$os" == "macos" ]]; then
        echo $(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))
    else
        echo "unknown"
    fi
}

# ===================
# 系統檢查函數
# ===================
check_system() {
    log_step "檢查系統環境..."
    
    local os=$(get_os)
    log_info "作業系統: $os"
    
    if [[ "$os" == "unknown" ]]; then
        error_exit "不支援的作業系統: $OSTYPE"
    fi
    
    # 檢查記憶體
    local memory_gb=$(get_memory_gb)
    if [[ "$memory_gb" != "unknown" ]]; then
        log_info "記憶體: ${memory_gb}GB"
        if [[ $memory_gb -lt 16 ]]; then
            log_warning "記憶體不足16GB，LLM運行可能較慢"
        fi
    fi
    
    log_success "系統檢查完成"
}

check_dependencies() {
    log_step "檢查依賴軟體..."
    
    # 檢查Python
    if ! command_exists python3; then
        error_exit "Python 3 未安裝，請先安裝 Python 3.9+"
    fi
    
    local python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Python 版本: $python_version"
    
    # 檢查Python版本
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"; then
        log_success "Python版本符合要求"
    else
        error_exit "Python版本過低，需要3.9以上版本"
    fi
    
    # 檢查pip
    if ! command_exists pip3; then
        log_warning "pip3 未安裝，嘗試安裝..."
        python3 -m ensurepip --upgrade || error_exit "pip3 安裝失敗"
    fi
    
    # 檢查Git
    if ! command_exists git; then
        error_exit "Git 未安裝，請先安裝 Git"
    fi
    
    # 檢查curl
    if ! command_exists curl; then
        error_exit "curl 未安裝，請先安裝 curl"
    fi
    
    # 檢查Docker (可選)
    if command_exists docker; then
        log_success "Docker 已安裝"
        export DOCKER_AVAILABLE=true
    else
        log_warning "Docker 未安裝，將使用本地安裝模式"
        export DOCKER_AVAILABLE=false
    fi
    
    log_success "依賴檢查完成"
}

# ===================
# 安裝函數
# ===================
install_ollama() {
    log_step "安裝 Ollama..."
    
    if command_exists ollama; then
        log_info "Ollama 已安裝，檢查版本..."
        ollama --version
        return
    fi
    
    local os=$(get_os)
    if [[ "$os" == "linux" || "$os" == "macos" ]]; then
        log_info "下載並安裝 Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
        log_success "Ollama 安裝完成"
    else
        log_warning "Windows 系統需要手動安裝 Ollama"
        echo "請訪問: https://ollama.ai/download/windows"
        read -p "安裝完成後按 Enter 繼續..."
        
        if ! command_exists ollama; then
            error_exit "Ollama 未正確安裝"
        fi
    fi
}

setup_python_env() {
    log_step "設置 Python 虛擬環境..."
    
    # 建立虛擬環境
    if [[ ! -d "venv" ]]; then
        log_info "建立虛擬環境..."
        python3 -m venv venv
        log_success "虛擬環境建立完成"
    else
        log_info "虛擬環境已存在"
    fi
    
    # 啟動虛擬環境
    log_info "啟動虛擬環境..."
    source venv/bin/activate
    
    # 升級pip
    log_info "升級 pip..."
    pip install --upgrade pip
    
    # 安裝依賴
    log_info "安裝 Python 依賴套件..."
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "依賴安裝完成"
    else
        error_exit "requirements.txt 檔案不存在"
    fi
}

setup_directories() {
    log_step "建立目錄結構..."
    
    # 建立必要目錄
    mkdir -p data/{dbf_files,backups,sample} logs config/prompts
    
    # 設置權限
    chmod 755 data logs config
    chmod 644 data/.gitkeep logs/.gitkeep 2>/dev/null || true
    
    log_success "目錄結構建立完成"
}

setup_config() {
    log_step "設置配置檔案..."
    
    # 複製環境變數範例
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "環境變數檔案建立完成"
        else
            log_warning ".env.example 檔案不存在"
        fi
    else
        log_info ".env 檔案已存在"
    fi
    
    # 複製系統設定範例
    if [[ ! -f "config/settings.yaml" ]]; then
        if [[ -f "config/settings.yaml.example" ]]; then
            cp config/settings.yaml.example config/settings.yaml
            log_success "系統設定檔案建立完成"
        else
            log_warning "config/settings.yaml.example 檔案不存在"
        fi
    else
        log_info "config/settings.yaml 檔案已存在"
    fi
}

start_ollama_service() {
    log_step "啟動 Ollama 服務..."
    
    # 檢查服務是否已在運行
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        log_info "Ollama 服務已在運行"
        return
    fi
    
    # 啟動服務
    log_info "啟動 Ollama 背景服務..."
    nohup ollama serve > logs/ollama.log 2>&1 &
    
    # 等待服務啟動
    local timeout=30
    local count=0
    while [[ $count -lt $timeout ]]; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            log_success "Ollama 服務啟動成功"
            return
        fi
        sleep 1
        ((count++))
    done
    
    error_exit "Ollama 服務啟動超時"
}

download_model() {
    log_step "下載 Gemma2 模型..."
    
    # 檢查模型是否已存在
    if ollama list | grep -q "gemma2:9b-instruct-q4_0"; then
        log_info "模型已存在，跳過下載"
        return
    fi
    
    log_info "開始下載模型 (約5.4GB，可能需要較長時間)..."
    
    # 顯示進度
    ollama pull gemma2:9b-instruct-q4_0 &
    local pid=$!
    
    # 簡單的進度指示
    while kill -0 $pid 2>/dev/null; do
        echo -n "."
        sleep 2
    done
    echo
    
    wait $pid
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "模型下載完成"
    else
        error_exit "模型下載失敗"
    fi
}

initialize_database() {
    log_step "初始化資料庫..."
    
    if [[ -f "scripts/setup_db.py" ]]; then
        log_info "執行資料庫初始化腳本..."
        python scripts/setup_db.py --create-schema
        log_success "資料庫初始化完成"
    else
        log_warning "資料庫初始化腳本不存在，請稍後手動執行"
    fi
}

run_health_check() {
    log_step "執行系統健康檢查..."
    
    # 檢查Ollama服務
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        log_success "✓ Ollama 服務正常"
    else
        log_error "✗ Ollama 服務異常"
    fi
    
    # 檢查模型
    if ollama list | grep -q "gemma2:9b-instruct-q4_0"; then
        log_success "✓ 模型載入正常"
    else
        log_error "✗ 模型未正確載入"
    fi
    
    # 檢查Python環境
    if python -c "import streamlit, pandas, ollama" 2>/dev/null; then
        log_success "✓ Python依賴正常"
    else
        log_error "✗ Python依賴缺失"
    fi
    
    # 執行詳細健康檢查
    if [[ -f "scripts/health_check.py" ]]; then
        log_info "執行詳細健康檢查..."
        python scripts/health_check.py
    fi
}

show_completion_message() {
    echo
    echo "🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉"
    log_success "診所AI查詢系統安裝完成！"
    echo "🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉"
    echo
    echo "🎯 啟動指令:"
    echo "   source venv/bin/activate      # 啟動虛擬環境"
    echo "   streamlit run src/app.py      # 啟動應用程式"
    echo
    echo "🌐 訪問網址:"
    echo "   http://localhost:8501"
    echo
    echo "🐳 Docker 快速啟動 (如果支援):"
    if [[ "$DOCKER_AVAILABLE" == "true" ]]; then
        echo "   docker-compose up -d          # 啟動所有服務"
        echo "   docker-compose logs -f        # 查看日誌"
    else
        echo "   (Docker 未安裝，請使用上方的本地啟動方式)"
    fi
    echo
    echo "📖 說明文檔:"
    echo "   - 安裝指南: docs/installation.md"
    echo "   - 配置說明: docs/configuration.md"
    echo "   - 使用手冊: README.md"
    echo
    echo "🆘 需要幫助？"
    echo "   - GitHub Issues: https://github.com/leon80148/chat4lab/issues"
    echo "   - 聯絡作者: leon80148@gmail.com"
    echo
}

show_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
    ____  _            _        ___    _____ 
   / ___|| |          (_)      / _ \  |_   _|
  | |    | |    _   _  _  __  | |_| |   | |  
  | |___ | |   | | | || ||  | |  _  |   | |  
   \____||_|   |_| |_||_||__|_|_| |_|  |_|  
                                              
   診所 AI 查詢系統 - Clinic AI Query System
   
   🏥 智能醫療資料查詢，讓數據說話！
   🤖 本地LLM部署，資料安全無憂！
   📊 自然語言查詢，簡單易用！
   
EOF
    echo -e "${NC}"
}

# ===================
# 主要安裝流程
# ===================
main() {
    show_banner
    
    log_info "開始安裝診所AI查詢系統..."
    echo "================================"
    
    # 檢查階段
    check_system
    check_dependencies
    
    # 安裝階段
    install_ollama
    setup_python_env
    setup_directories
    setup_config
    
    # 服務啟動階段
    start_ollama_service
    download_model
    initialize_database
    
    # 驗證階段
    run_health_check
    
    # 完成提示
    show_completion_message
}

# 執行主函數
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi