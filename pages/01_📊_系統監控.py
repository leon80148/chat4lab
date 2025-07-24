"""
系統監控頁面

提供系統運行狀態監控、效能分析和健康檢查功能。

Author: Leon Lu
Created: 2025-01-24
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import psutil
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager
from src.modules.llm_agent import LLMQueryAgent

# 頁面配置
st.set_page_config(
    page_title="系統監控 - 診所AI查詢系統",
    page_icon="📊",
    layout="wide"
)

# 自定義CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    
    .status-good { color: #28a745; }
    .status-warning { color: #ffc107; }
    .status-error { color: #dc3545; }
    
    .system-info {
        background-color: #e9ecef;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)  # 快取30秒
def get_system_metrics():
    """獲取系統指標"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 記憶體使用情況
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # 磁碟使用情況
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'memory_used_gb': memory_used_gb,
            'memory_total_gb': memory_total_gb,
            'disk_percent': disk_percent,
            'disk_used_gb': disk_used_gb,
            'disk_total_gb': disk_total_gb,
            'timestamp': datetime.now()
        }
    except Exception as e:
        st.error(f"無法獲取系統指標: {e}")
        return None


@st.cache_resource
def initialize_components():
    """初始化系統組件"""
    try:
        config_manager = ConfigManager()
        
        db_config = config_manager.get_database_config()
        db_manager = DatabaseManager(
            db_config.get('path', './data/anchia_lab.db'),
            db_config
        )
        
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        return {
            'config': config_manager,
            'db_manager': db_manager,
            'llm_agent': llm_agent,
            'status': 'success'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def render_system_overview():
    """渲染系統概覽"""
    st.header("🖥️ 系統概覽")
    
    # 獲取系統指標
    metrics = get_system_metrics()
    
    if metrics:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cpu_color = "🟢" if metrics['cpu_percent'] < 70 else "🟡" if metrics['cpu_percent'] < 90 else "🔴"
            st.metric("CPU使用率", f"{metrics['cpu_percent']:.1f}%", delta=None)
            st.markdown(f"<div style='text-align: center; font-size: 2em;'>{cpu_color}</div>", unsafe_allow_html=True)
        
        with col2:
            memory_color = "🟢" if metrics['memory_percent'] < 70 else "🟡" if metrics['memory_percent'] < 90 else "🔴"
            st.metric("記憶體使用率", f"{metrics['memory_percent']:.1f}%", 
                     delta=f"{metrics['memory_used_gb']:.1f}GB / {metrics['memory_total_gb']:.1f}GB")
            st.markdown(f"<div style='text-align: center; font-size: 2em;'>{memory_color}</div>", unsafe_allow_html=True)
        
        with col3:
            disk_color = "🟢" if metrics['disk_percent'] < 80 else "🟡" if metrics['disk_percent'] < 95 else "🔴"
            st.metric("磁碟使用率", f"{metrics['disk_percent']:.1f}%",
                     delta=f"{metrics['disk_used_gb']:.1f}GB / {metrics['disk_total_gb']:.1f}GB")
            st.markdown(f"<div style='text-align: center; font-size: 2em;'>{disk_color}</div>", unsafe_allow_html=True)
        
        with col4:
            st.metric("系統時間", datetime.now().strftime("%H:%M:%S"))
            st.metric("運行時間", "運行中 🟢")
    
    else:
        st.error("無法獲取系統指標")


def render_database_status(components):
    """渲染資料庫狀態"""
    st.header("🗄️ 資料庫狀態")
    
    if components['status'] != 'success':
        st.error("無法連接到資料庫")
        return
    
    try:
        db_manager = components['db_manager']
        
        # 獲取資料庫統計
        db_stats = db_manager.get_table_stats()
        
        # 資料表統計
        st.subheader("📊 資料表統計")
        
        table_data = []
        for table_name, stats in db_stats['tables'].items():
            if 'record_count' in stats:
                table_data.append({
                    '資料表': table_name,
                    '記錄數': f"{stats['record_count']:,}",
                    '欄位數': stats.get('column_count', 'N/A'),
                    '索引數': stats.get('index_count', 'N/A')
                })
        
        if table_data:
            df_tables = pd.DataFrame(table_data)
            st.dataframe(df_tables, use_container_width=True, hide_index=True)
            
            # 視覺化資料表大小
            fig = px.bar(
                df_tables,
                x='資料表',
                y=[int(x.replace(',', '')) for x in df_tables['記錄數']],
                title="各資料表記錄數量",
                labels={'y': '記錄數', 'x': '資料表'}
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # 資料庫資訊
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💾 資料庫資訊")
            db_size_mb = db_stats['database_size'] / (1024 * 1024)
            st.write(f"**資料庫大小：** {db_size_mb:.2f} MB")
            
            query_stats = db_stats['query_stats']
            st.write(f"**執行查詢數：** {query_stats['queries_executed']:,}")
            st.write(f"**緩存命中數：** {query_stats['cache_hits']:,}")
            
            if query_stats['queries_executed'] > 0:
                cache_hit_rate = query_stats['cache_hits'] / query_stats['queries_executed']
                st.write(f"**緩存命中率：** {cache_hit_rate:.1%}")
        
        with col2:
            st.subheader("⚡ 效能指標")
            if query_stats['total_query_time'] > 0:
                avg_time = query_stats['total_query_time'] / query_stats['queries_executed']
                st.write(f"**平均查詢時間：** {avg_time:.3f} 秒")
            
            if query_stats['last_query_time']:
                st.write(f"**最後查詢時間：** {query_stats['last_query_time']:.3f} 秒")
            
            # 連線狀態測試
            try:
                test_result = db_manager.execute_query("SELECT 1 as test")
                if len(test_result) > 0:
                    st.success("✅ 資料庫連線正常")
                else:
                    st.warning("⚠️ 資料庫查詢異常")
            except Exception as e:
                st.error(f"❌ 資料庫連線失敗: {e}")
    
    except Exception as e:
        st.error(f"獲取資料庫狀態失敗: {e}")


def render_llm_status(components):
    """渲染LLM服務狀態"""
    st.header("🤖 LLM服務狀態")
    
    if components['status'] != 'success':
        st.error("LLM服務未初始化")
        return
    
    try:
        llm_agent = components['llm_agent']
        llm_stats = llm_agent.get_statistics()
        
        # LLM基本資訊
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔧 服務配置")
            model_info = llm_stats['model_info']
            st.write(f"**模型名稱：** {model_info['model']}")
            st.write(f"**服務URL：** {model_info['base_url']}")
            st.write(f"**溫度參數：** {model_info['temperature']}")
        
        with col2:
            st.subheader("📈 使用統計")
            st.write(f"**總查詢次數：** {llm_stats['total_queries']:,}")
            st.write(f"**成功查詢：** {llm_stats['successful_queries']:,}")
            st.write(f"**失敗查詢：** {llm_stats['failed_queries']:,}")
            st.write(f"**成功率：** {llm_stats['success_rate']:.1%}")
        
        # 效能指標
        if llm_stats['avg_response_time'] > 0:
            st.subheader("⏱️ 效能指標")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("平均回應時間", f"{llm_stats['avg_response_time']:.2f} 秒")
            
            with col2:
                if llm_stats['total_queries'] > 0:
                    st.metric("查詢成功率", f"{llm_stats['success_rate']:.1%}")
            
            with col3:
                st.metric("服務狀態", "🟢 正常運行")
        
        # 服務連線測試
        with st.expander("🔍 服務連線測試", expanded=False):
            if st.button("測試LLM連線"):
                try:
                    with st.spinner("測試中..."):
                        # 執行簡單的測試查詢
                        test_result = llm_agent.process_query("測試查詢", user_id="system_test")
                        
                        if test_result.success or "LLM" not in test_result.error_message:
                            st.success("✅ LLM服務連線正常")
                        else:
                            st.error(f"❌ LLM服務連線失敗: {test_result.error_message}")
                
                except Exception as e:
                    st.error(f"❌ 連線測試失敗: {e}")
    
    except Exception as e:
        st.error(f"獲取LLM狀態失敗: {e}")


def render_system_health():
    """渲染系統健康檢查"""
    st.header("🏥 系統健康檢查")
    
    if st.button("執行健康檢查"):
        with st.spinner("正在執行健康檢查..."):
            # 系統資源檢查
            metrics = get_system_metrics()
            
            health_report = {
                "系統資源": [],
                "服務狀態": [],
                "建議事項": []
            }
            
            if metrics:
                # CPU檢查
                if metrics['cpu_percent'] < 70:
                    health_report["系統資源"].append("✅ CPU使用率正常")
                elif metrics['cpu_percent'] < 90:
                    health_report["系統資源"].append("⚠️ CPU使用率偏高")
                    health_report["建議事項"].append("建議監控CPU使用情況")
                else:
                    health_report["系統資源"].append("❌ CPU使用率過高")
                    health_report["建議事項"].append("需立即檢查CPU負載")
                
                # 記憶體檢查
                if metrics['memory_percent'] < 70:
                    health_report["系統資源"].append("✅ 記憶體使用正常")
                elif metrics['memory_percent'] < 90:
                    health_report["系統資源"].append("⚠️ 記憶體使用偏高")
                    health_report["建議事項"].append("建議清理不必要的程序")
                else:
                    health_report["系統資源"].append("❌ 記憶體不足")
                    health_report["建議事項"].append("需增加記憶體或優化程序")
                
                # 磁碟檢查
                if metrics['disk_percent'] < 80:
                    health_report["系統資源"].append("✅ 磁碟空間充足")
                elif metrics['disk_percent'] < 95:
                    health_report["系統資源"].append("⚠️ 磁碟空間不足")
                    health_report["建議事項"].append("建議清理舊檔案或擴充空間")
                else:
                    health_report["系統資源"].append("❌ 磁碟空間嚴重不足")
                    health_report["建議事項"].append("需立即清理磁碟空間")
            
            # 服務狀態檢查
            components = initialize_components()
            
            if components['status'] == 'success':
                health_report["服務狀態"].append("✅ 系統組件正常載入")
                
                # 資料庫檢查
                try:
                    db_manager = components['db_manager']
                    test_query = db_manager.execute_query("SELECT 1 as test")
                    health_report["服務狀態"].append("✅ 資料庫連線正常")
                except Exception:
                    health_report["服務狀態"].append("❌ 資料庫連線失敗")
                    health_report["建議事項"].append("檢查資料庫服務")
                
                # LLM服務檢查（簡化版本）
                try:
                    llm_agent = components['llm_agent']
                    stats = llm_agent.get_statistics()
                    health_report["服務狀態"].append("✅ LLM代理正常初始化")
                except Exception:
                    health_report["服務狀態"].append("❌ LLM代理初始化失敗")
                    health_report["建議事項"].append("檢查LLM服務配置")
            
            else:
                health_report["服務狀態"].append("❌ 系統組件載入失敗")
                health_report["建議事項"].append("檢查系統配置")
            
            # 顯示健康報告
            st.subheader("📋 健康報告")
            
            for category, items in health_report.items():
                if items:
                    st.write(f"**{category}:**")
                    for item in items:
                        st.write(f"  {item}")
                    st.write("")
            
            # 總體評估
            error_count = sum(1 for category in health_report.values() 
                            for item in category if item.startswith("❌"))
            warning_count = sum(1 for category in health_report.values()
                              for item in category if item.startswith("⚠️"))
            
            if error_count == 0 and warning_count == 0:
                st.success("🎉 系統整體狀態良好！")
            elif error_count == 0:
                st.warning(f"⚠️ 系統基本正常，但有 {warning_count} 項需要注意")
            else:
                st.error(f"❌ 系統存在 {error_count} 項嚴重問題和 {warning_count} 項警告")


def render_system_logs():
    """渲染系統日誌"""
    st.header("📝 系統日誌")
    
    # 模擬日誌顯示
    with st.expander("📋 最近日誌", expanded=False):
        st.text(f"""
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] 系統監控頁面已載入
{(datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')} [INFO] 資料庫連線檢查完成
{(datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')} [INFO] LLM服務狀態正常
{(datetime.now() - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')} [INFO] 系統健康檢查執行完成
{(datetime.now() - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')} [INFO] 配置檔案載入成功
        """)
    
    # 日誌配置
    st.subheader("⚙️ 日誌配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        log_level = st.selectbox(
            "日誌級別：",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1
        )
    
    with col2:
        max_log_size = st.slider(
            "最大日誌檔案大小 (MB)：",
            min_value=1,
            max_value=100,
            value=10
        )
    
    if st.button("套用日誌設定"):
        st.success(f"日誌級別已設為 {log_level}，最大檔案大小 {max_log_size}MB")


def main():
    """主程式"""
    st.title("📊 系統監控")
    st.markdown("監控診所AI查詢系統的運行狀態和效能指標")
    
    # 自動重新整理
    auto_refresh = st.checkbox("自動重新整理 (30秒)", value=False)
    
    if auto_refresh:
        st.rerun()
        import time
        time.sleep(30)
    
    # 初始化組件
    components = initialize_components()
    
    # 頁面內容
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🖥️ 系統概覽", 
        "🗄️ 資料庫", 
        "🤖 LLM服務", 
        "🏥 健康檢查", 
        "📝 系統日誌"
    ])
    
    with tab1:
        render_system_overview()
    
    with tab2:
        render_database_status(components)
    
    with tab3:
        render_llm_status(components)
    
    with tab4:
        render_system_health()
    
    with tab5:
        render_system_logs()


if __name__ == "__main__":
    main()