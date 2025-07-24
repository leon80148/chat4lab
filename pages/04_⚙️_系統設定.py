"""
系統設定頁面

提供系統配置管理、用戶設定、安全設定等功能。

Author: Leon Lu
Created: 2025-01-24
"""

import streamlit as st
import yaml
import json
from datetime import datetime
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, ConfigError

# 頁面配置
st.set_page_config(
    page_title="系統設定 - 診所AI查詢系統",
    page_icon="⚙️",
    layout="wide"
)

# 自定義CSS
st.markdown("""
<style>
    .settings-section {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #6c757d;
    }
    
    .config-preview {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        max-height: 300px;
        overflow-y: auto;
    }
    
    .warning-banner {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .success-banner {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .info-box {
        background-color: #e7f3ff;
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_config_manager():
    """初始化配置管理器"""
    try:
        return ConfigManager()
    except Exception as e:
        st.error(f"配置管理器初始化失敗: {e}")
        return None


def render_database_settings(config_manager):
    """渲染資料庫設定"""
    st.header("🗄️ 資料庫設定")
    
    current_config = config_manager.get_database_config()
    
    with st.form("database_settings"):
        st.subheader("資料庫連線設定")
        
        db_path = st.text_input(
            "資料庫路徑",
            value=current_config.get('path', './data/anchia_lab.db'),
            help="SQLite資料庫檔案的完整路徑"
        )
        
        db_encoding = st.selectbox(
            "預設編碼",
            options=['big5', 'utf-8', 'gbk'],
            index=['big5', 'utf-8', 'gbk'].index(current_config.get('encoding', 'big5'))
        )
        
        st.subheader("效能設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            journal_mode = st.selectbox(
                "Journal模式",
                options=['WAL', 'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'OFF'],
                index=['WAL', 'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'OFF'].index(
                    current_config.get('performance', {}).get('journal_mode', 'WAL')
                )
            )
            
            synchronous = st.selectbox(
                "同步模式",
                options=['FULL', 'NORMAL', 'OFF'],
                index=['FULL', 'NORMAL', 'OFF'].index(
                    current_config.get('performance', {}).get('synchronous', 'NORMAL')
                )
            )
            
            cache_size = st.number_input(
                "快取大小 (KB)",
                min_value=1000,
                max_value=100000,
                value=current_config.get('performance', {}).get('cache_size', 10000)
            )
        
        with col2:
            temp_store = st.selectbox(
                "暫存儲存",
                options=['MEMORY', 'FILE', 'DEFAULT'],
                index=['MEMORY', 'FILE', 'DEFAULT'].index(
                    current_config.get('performance', {}).get('temp_store', 'MEMORY')
                )
            )
            
            mmap_size = st.number_input(
                "記憶體映射大小 (MB)",
                min_value=0,
                max_value=1024,
                value=current_config.get('performance', {}).get('mmap_size', 268435456) // (1024*1024)
            )
        
        if st.form_submit_button("💾 儲存資料庫設定"):
            try:
                # 更新配置
                config_manager.set('database.path', db_path)
                config_manager.set('database.encoding', db_encoding)
                config_manager.set('database.performance.journal_mode', journal_mode)
                config_manager.set('database.performance.synchronous', synchronous)
                config_manager.set('database.performance.cache_size', cache_size)
                config_manager.set('database.performance.temp_store', temp_store)
                config_manager.set('database.performance.mmap_size', mmap_size * 1024 * 1024)
                
                st.success("✅ 資料庫設定已儲存")
                st.rerun()
                
            except Exception as e:
                st.error(f"儲存設定失敗: {e}")


def render_llm_settings(config_manager):
    """渲染LLM設定"""
    st.header("🤖 LLM服務設定")
    
    current_config = config_manager.get_llm_config()
    
    with st.form("llm_settings"):
        st.subheader("服務連線設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            provider = st.selectbox(
                "LLM提供商",
                options=['ollama', 'openai', 'anthropic'],
                index=['ollama', 'openai', 'anthropic'].index(current_config.get('provider', 'ollama'))
            )
            
            base_url = st.text_input(
                "服務URL",
                value=current_config.get('base_url', 'http://localhost:11434'),
                help="LLM服務的基礎URL"
            )
        
        with col2:
            model = st.text_input(
                "模型名稱",
                value=current_config.get('model', 'llama3:8b-instruct'),
                help="要使用的LLM模型名稱"
            )
        
        st.subheader("模型參數")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            temperature = st.slider(
                "溫度參數",
                min_value=0.0,
                max_value=2.0,
                value=current_config.get('parameters', {}).get('temperature', 0.2),
                step=0.1,
                help="控制輸出的隨機性，越低越確定"
            )
        
        with col2:
            max_tokens = st.number_input(
                "最大token數",
                min_value=256,
                max_value=8192,
                value=current_config.get('parameters', {}).get('max_tokens', 2048)
            )
        
        with col3:
            top_p = st.slider(
                "Top-p",
                min_value=0.1,
                max_value=1.0,
                value=current_config.get('parameters', {}).get('top_p', 0.9),
                step=0.1,
                help="控制詞彙選擇的多樣性"
            )
        
        st.subheader("超時設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            connection_timeout = st.number_input(
                "連線超時 (秒)",
                min_value=5,
                max_value=60,
                value=current_config.get('timeout', {}).get('connection', 10)
            )
        
        with col2:
            inference_timeout = st.number_input(
                "推理超時 (秒)",
                min_value=10,
                max_value=300,
                value=current_config.get('timeout', {}).get('inference', 30)
            )
        
        if st.form_submit_button("💾 儲存LLM設定"):
            try:
                # 更新配置
                config_manager.set('llm.provider', provider)
                config_manager.set('llm.base_url', base_url)
                config_manager.set('llm.model', model)
                config_manager.set('llm.parameters.temperature', temperature)
                config_manager.set('llm.parameters.max_tokens', max_tokens)
                config_manager.set('llm.parameters.top_p', top_p)
                config_manager.set('llm.timeout.connection', connection_timeout)
                config_manager.set('llm.timeout.inference', inference_timeout)
                
                st.success("✅ LLM設定已儲存")
                st.rerun()
                
            except Exception as e:
                st.error(f"儲存設定失敗: {e}")
    
    # LLM連線測試
    st.subheader("🔍 連線測試")
    
    if st.button("測試LLM連線"):
        try:
            import requests
            
            with st.spinner("測試連線中..."):
                # 測試基本連線
                response = requests.get(f"{base_url}/api/tags", timeout=10)
                
                if response.status_code == 200:
                    st.success("✅ LLM服務連線成功")
                    
                    # 檢查模型是否存在
                    models = response.json().get('models', [])
                    model_names = [m.get('name', '') for m in models]
                    
                    if model in model_names:
                        st.success(f"✅ 模型 '{model}' 可用")
                    else:
                        st.warning(f"⚠️ 模型 '{model}' 未找到")
                        st.write("**可用模型：**")
                        for model_name in model_names[:5]:  # 顯示前5個模型
                            st.write(f"- {model_name}")
                else:
                    st.error(f"❌ 連線失敗: HTTP {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            st.error("❌ 無法連接到LLM服務，請檢查URL和服務狀態")
        except requests.exceptions.Timeout:
            st.error("❌ 連線超時")
        except Exception as e:
            st.error(f"❌ 測試失敗: {e}")


def render_security_settings(config_manager):
    """渲染安全設定"""
    st.header("🔒 安全設定")
    
    current_config = config_manager.get_security_config()
    
    with st.form("security_settings"):
        st.subheader("認證設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            auth_enabled = st.checkbox(
                "啟用身份驗證",
                value=current_config.get('authentication', {}).get('enabled', True)
            )
            
            session_timeout = st.number_input(
                "會話超時 (分鐘)",
                min_value=5,
                max_value=1440,
                value=current_config.get('authentication', {}).get('session_timeout', 1800) // 60
            )
        
        with col2:
            max_login_attempts = st.number_input(
                "最大登入嘗試次數",
                min_value=1,
                max_value=10,
                value=current_config.get('authentication', {}).get('max_login_attempts', 3)
            )
        
        st.subheader("查詢限制")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_results = st.number_input(
                "最大查詢結果數",
                min_value=100,
                max_value=10000,
                value=current_config.get('query_limits', {}).get('max_results', 1000)
            )
        
        with col2:
            max_execution_time = st.number_input(
                "最大執行時間 (秒)",
                min_value=10,
                max_value=300,
                value=current_config.get('query_limits', {}).get('max_execution_time', 30)
            )
        
        st.subheader("敏感欄位設定")
        
        sensitive_fields = st.text_area(
            "敏感欄位列表 (每行一個)",
            value='\n'.join(current_config.get('sensitive_fields', ['mpersonid', 'mtelh', 'mfml'])),
            help="這些欄位在日誌和匯出時會被遮蔽"
        )
        
        if st.form_submit_button("💾 儲存安全設定"):
            try:
                # 處理敏感欄位
                fields_list = [field.strip() for field in sensitive_fields.split('\n') if field.strip()]
                
                # 更新配置
                config_manager.set('security.authentication.enabled', auth_enabled)
                config_manager.set('security.authentication.session_timeout', session_timeout * 60)
                config_manager.set('security.authentication.max_login_attempts', max_login_attempts)
                config_manager.set('security.query_limits.max_results', max_results)
                config_manager.set('security.query_limits.max_execution_time', max_execution_time)
                config_manager.set('security.sensitive_fields', fields_list)
                
                st.success("✅ 安全設定已儲存")
                st.rerun()
                
            except Exception as e:
                st.error(f"儲存設定失敗: {e}")


def render_ui_settings(config_manager):
    """渲染UI設定"""
    st.header("🎨 用戶界面設定")
    
    current_config = config_manager.get_ui_config()
    
    with st.form("ui_settings"):
        st.subheader("外觀設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            theme = st.selectbox(
                "主題",
                options=['light', 'dark', 'auto'],
                index=['light', 'dark', 'auto'].index(current_config.get('theme', 'light'))
            )
            
            language = st.selectbox(
                "語言",
                options=['zh-TW', 'zh-CN', 'en-US'],
                index=['zh-TW', 'zh-CN', 'en-US'].index(current_config.get('language', 'zh-TW'))
            )
        
        with col2:
            page_title = st.text_input(
                "頁面標題",
                value=current_config.get('page', {}).get('title', '診所AI查詢系統')
            )
            
            page_icon = st.text_input(
                "頁面圖示",
                value=current_config.get('page', {}).get('icon', '🏥')
            )
        
        st.subheader("布局設定")
        
        layout = st.selectbox(
            "頁面布局",
            options=['wide', 'centered'],
            index=['wide', 'centered'].index(current_config.get('page', {}).get('layout', 'wide'))
        )
        
        sidebar_state = st.selectbox(
            "側邊欄預設狀態",
            options=['expanded', 'collapsed'],
            index=['expanded', 'collapsed'].index(current_config.get('sidebar', {}).get('initial_state', 'expanded'))
        )
        
        if st.form_submit_button("💾 儲存UI設定"):
            try:
                # 更新配置
                config_manager.set('ui.theme', theme)
                config_manager.set('ui.language', language)
                config_manager.set('ui.page.title', page_title)
                config_manager.set('ui.page.icon', page_icon)
                config_manager.set('ui.page.layout', layout)
                config_manager.set('ui.sidebar.initial_state', sidebar_state)
                
                st.success("✅ UI設定已儲存")
                st.rerun()
                
            except Exception as e:
                st.error(f"儲存設定失敗: {e}")


def render_logging_settings(config_manager):
    """渲染日誌設定"""
    st.header("📝 日誌設定")
    
    current_config = config_manager.get_logging_config()
    
    with st.form("logging_settings"):
        st.subheader("日誌配置")
        
        col1, col2 = st.columns(2)
        
        with col1:
            log_level = st.selectbox(
                "日誌級別",
                options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                index=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(current_config.get('level', 'INFO'))
            )
            
            log_file = st.text_input(
                "日誌檔案路徑",
                value=current_config.get('file', './logs/clinic_ai.log')
            )
        
        with col2:
            max_file_size = st.number_input(
                "最大檔案大小 (MB)",
                min_value=1,
                max_value=100,
                value=current_config.get('max_file_size', 10)
            )
            
            backup_count = st.number_input(
                "備份檔案數量",
                min_value=1,
                max_value=10,
                value=current_config.get('backup_count', 5)
            )
        
        log_format = st.text_area(
            "日誌格式",
            value=current_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            help="Python logging格式字串"
        )
        
        # 日誌選項
        st.subheader("日誌選項")
        
        log_queries = st.checkbox(
            "記錄所有查詢",
            value=current_config.get('log_queries', True)
        )
        
        log_performance = st.checkbox(
            "記錄效能資訊",  
            value=current_config.get('log_performance', True)
        )
        
        if st.form_submit_button("💾 儲存日誌設定"):
            try:
                # 更新配置
                config_manager.set('logging.level', log_level)
                config_manager.set('logging.file', log_file)
                config_manager.set('logging.format', log_format)
                config_manager.set('logging.max_file_size', max_file_size)
                config_manager.set('logging.backup_count', backup_count)
                config_manager.set('logging.log_queries', log_queries)
                config_manager.set('logging.log_performance', log_performance)
                
                st.success("✅ 日誌設定已儲存")
                st.rerun()
                
            except Exception as e:
                st.error(f"儲存設定失敗: {e}")


def render_config_management(config_manager):
    """渲染配置管理"""
    st.header("📄 配置管理")
    
    # 匯出配置
    st.subheader("📤 匯出配置")
    
    if st.button("匯出當前配置"):
        try:
            # 獲取安全的配置（遮蔽敏感資訊）
            safe_config = config_manager.export_config()
            
            # 轉換為YAML格式
            yaml_content = yaml.dump(safe_config, default_flow_style=False, allow_unicode=True)
            
            st.download_button(
                label="📥 下載配置檔案",
                data=yaml_content.encode('utf-8'),
                file_name=f"clinic_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml",
                mime="application/x-yaml"
            )
            
            st.success("✅ 配置已準備下載")
        
        except Exception as e:
            st.error(f"匯出配置失敗: {e}")
    
    # 配置預覽
    st.subheader("👁️ 配置預覽")
    
    if st.button("顯示當前配置"):
        try:
            safe_config = config_manager.export_config()
            yaml_content = yaml.dump(safe_config, default_flow_style=False, allow_unicode=True)
            
            st.markdown(f"""
            <div class="config-preview">{yaml_content}</div>
            """, unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"顯示配置失敗: {e}")
    
    # 重置配置
    st.subheader("🔄 重置配置")
    
    st.markdown("""
    <div class="warning-banner">
        <strong>⚠️ 警告：</strong> 重置配置將會：
        <ul>
            <li>將所有設定恢復為預設值</li>
            <li>清除所有自訂配置</li>
            <li>需要重新啟動系統才能生效</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🗑️ 重置為預設配置", type="secondary"):
        if st.button("⚠️ 確認重置", type="secondary"):
            try:
                # 重新載入配置（會使用預設值）
                config_manager.reload()
                st.success("✅ 配置已重置為預設值")
                st.rerun()
            
            except Exception as e:
                st.error(f"重置配置失敗: {e}")


def render_system_info(config_manager):
    """渲染系統資訊"""
    st.header("ℹ️ 系統資訊")
    
    # 基本資訊
    st.subheader("📋 基本資訊")
    
    system_info = config_manager.get('system', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**系統名稱：** {system_info.get('name', '診所AI查詢系統')}")
        st.write(f"**版本：** {system_info.get('version', '1.0.0')}")
        st.write(f"**作者：** {system_info.get('author', 'Leon Lu')}")
        st.write(f"**授權：** {system_info.get('license', 'MIT')}")
    
    with col2:
        st.write(f"**Python版本：** {sys.version.split()[0]}")
        st.write(f"**Streamlit版本：** {st.__version__}")
        st.write(f"**配置路徑：** {config_manager.config_path}")
        st.write(f"**環境檔案：** {config_manager.env_file}")
    
    # 環境變數
    st.subheader("🌍 環境變數")
    
    env_vars = [
        'DATABASE_PATH',
        'OLLAMA_BASE_URL', 
        'OLLAMA_MODEL',
        'LOG_LEVEL',
        'LOG_FILE'
    ]
    
    import os
    
    env_data = []
    for var in env_vars:
        value = os.getenv(var, '未設定')
        # 遮蔽敏感資訊
        if any(sensitive in var.lower() for sensitive in ['password', 'key', 'secret', 'token']):
            value = '***MASKED***' if value != '未設定' else value
        
        env_data.append({
            '環境變數': var,
            '值': value
        })
    
    if env_data:
        import pandas as pd
        df_env = pd.DataFrame(env_data)
        st.dataframe(df_env, use_container_width=True, hide_index=True)
    
    # 系統狀態
    st.subheader("📊 系統狀態")
    
    status_checks = [
        ("配置管理器", "✅ 正常" if config_manager else "❌ 異常"),
        ("配置檔案", "✅ 存在" if config_manager.config_path.exists() else "⚠️ 不存在"),
        ("日誌目錄", "✅ 存在" if Path("./logs").exists() else "⚠️ 不存在"),
        ("資料目錄", "✅ 存在" if Path("./data").exists() else "⚠️ 不存在"),
    ]
    
    for check_name, status in status_checks:
        st.write(f"**{check_name}：** {status}")


def main():
    """主程式"""
    st.title("⚙️ 系統設定")
    st.markdown("管理診所AI查詢系統的各項配置")
    
    # 初始化配置管理器
    config_manager = initialize_config_manager()
    
    if not config_manager:
        st.error("無法載入配置管理器")
        return
    
    # 主要功能標籤
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🗄️ 資料庫",
        "🤖 LLM服務", 
        "🔒 安全",
        "🎨 界面",
        "📝 日誌",
        "📄 配置管理",
        "ℹ️ 系統資訊"
    ])
    
    with tab1:
        render_database_settings(config_manager)
    
    with tab2:
        render_llm_settings(config_manager)
    
    with tab3:
        render_security_settings(config_manager)
    
    with tab4:
        render_ui_settings(config_manager)
    
    with tab5:
        render_logging_settings(config_manager)
    
    with tab6:
        render_config_management(config_manager)
    
    with tab7:
        render_system_info(config_manager)


if __name__ == "__main__":
    main()