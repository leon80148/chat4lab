"""
診所AI查詢系統 - 主應用程式

Streamlit Web應用程式，提供直觀的用戶界面供醫護人員
進行自然語言查詢和資料檢索。

Author: Leon Lu
Created: 2025-01-24
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
from pathlib import Path
import sys
import json

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import ConfigManager, ConfigError
from src.modules.db_manager import DatabaseManager, DatabaseError
from src.modules.llm_agent_v2 import ModernLLMQueryAgent as LLMQueryAgent
from src.modules.sql_models import EnhancedQueryResult as QueryResult
from src.modules.query_templates import QueryTemplateManager

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 頁面配置
st.set_page_config(
    page_title="診所AI查詢系統",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義CSS樣式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .query-box {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .result-container {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .success-message {
        color: #28a745;
        font-weight: bold;
    }
    
    .error-message {
        color: #dc3545;
        font-weight: bold;
    }
    
    .info-box {
        background-color: #e7f3ff;
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """初始化系統組件"""
    try:
        # 載入配置
        config_manager = ConfigManager()
        
        # 初始化資料庫管理器
        db_config = config_manager.get_database_config()
        db_manager = DatabaseManager(
            db_config.get('path', './data/anchia_lab.db'),
            db_config
        )
        
        # 初始化LLM查詢代理
        llm_config = config_manager.get_llm_config()
        llm_agent = LLMQueryAgent(db_manager, llm_config)
        
        # 初始化查詢範本管理器
        template_manager = QueryTemplateManager()
        
        return {
            'config': config_manager,
            'db_manager': db_manager,
            'llm_agent': llm_agent,
            'template_manager': template_manager,
            'status': 'success'
        }
        
    except Exception as e:
        logger.error(f"系統初始化失敗: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


def initialize_session_state():
    """初始化session state"""
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    
    if 'current_results' not in st.session_state:
        st.session_state.current_results = None
    
    if 'show_sql' not in st.session_state:
        st.session_state.show_sql = False
    
    if 'selected_template' not in st.session_state:
        st.session_state.selected_template = None


def render_header():
    """渲染頁面標題"""
    st.markdown('<h1 class="main-header">🏥 診所AI查詢系統</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="info-box">
            <strong>功能說明：</strong> 使用自然語言查詢診所病患資料，支援病患資料、就診記錄、處方記錄、檢驗結果等查詢。
        </div>
        """, unsafe_allow_html=True)


def render_sidebar(components):
    """渲染側邊欄"""
    with st.sidebar:
        st.header("🔧 系統功能")
        
        # 系統狀態
        st.subheader("📊 系統狀態")
        
        if components['status'] == 'success':
            st.success("✅ 系統運行正常")
            
            # 獲取統計資訊
            try:
                db_stats = components['db_manager'].get_table_stats()
                llm_stats = components['llm_agent'].get_statistics()
                
                # 資料庫統計
                st.write("**資料庫統計：**")
                for table, stats in db_stats['tables'].items():
                    if 'record_count' in stats:
                        st.write(f"- {table}: {stats['record_count']:,} 筆")
                
                # LLM統計
                st.write("**查詢統計：**")
                st.write(f"- 總查詢次數: {llm_stats['total_queries']}")
                st.write(f"- 成功率: {llm_stats['success_rate']:.1%}")
                if llm_stats['avg_response_time'] > 0:
                    st.write(f"- 平均回應時間: {llm_stats['avg_response_time']:.2f}秒")
                
            except Exception as e:
                st.warning(f"無法取得統計資訊: {e}")
        else:
            st.error("❌ 系統初始化失敗")
            st.error(components.get('error', '未知錯誤'))
        
        st.divider()
        
        # 查詢範本
        st.subheader("📋 查詢範本")
        
        if components['status'] == 'success':
            template_manager = components['template_manager']
            categories = template_manager.get_categories()
            
            selected_category = st.selectbox(
                "選擇範本類別：",
                options=[""] + categories,
                index=0
            )
            
            if selected_category:
                templates = template_manager.list_templates(category=selected_category)
                template_names = {t.name: t.id for t in templates}
                
                selected_template_name = st.selectbox(
                    "選擇查詢範本：",
                    options=[""] + list(template_names.keys()),
                    index=0
                )
                
                if selected_template_name:
                    template_id = template_names[selected_template_name]
                    template = template_manager.get_template(template_id)
                    
                    st.write(f"**描述：** {template.description}")
                    
                    # 顯示範例參數
                    examples = template_manager.get_template_examples(template_id)
                    if examples:
                        st.write("**範例參數：**")
                        for param, value in examples.items():
                            st.write(f"- {param}: {value}")
                    
                    if st.button("使用此範本"):
                        st.session_state.selected_template = template_id
                        st.rerun()
        
        st.divider()
        
        # 系統設定
        st.subheader("⚙️ 系統設定")
        
        st.session_state.show_sql = st.checkbox(
            "顯示生成的SQL語句",
            value=st.session_state.show_sql
        )
        
        max_results = st.slider(
            "最大查詢結果數",
            min_value=10,
            max_value=1000,
            value=100,
            step=10
        )
        
        if st.button("清除查詢歷史"):
            st.session_state.query_history = []
            st.session_state.current_results = None
            st.success("查詢歷史已清除")
            st.rerun()


def render_query_interface(components):
    """渲染查詢界面"""
    if components['status'] != 'success':
        st.error("系統未正常初始化，無法使用查詢功能")
        return
    
    st.header("🔍 自然語言查詢")
    
    # 查詢範本處理
    template_query = ""
    if st.session_state.selected_template:
        template_manager = components['template_manager']
        template = template_manager.get_template(st.session_state.selected_template)
        
        if template:
            st.info(f"已選擇範本：{template.name}")
            
            # 如果範本需要參數，顯示參數輸入框
            if template.parameters:
                st.write("**請填入參數：**")
                params = {}
                
                for param_def in template.parameters:
                    param_name = param_def["name"]
                    param_type = param_def.get("type", "string")
                    description = param_def.get("description", "")
                    required = param_def.get("required", False)
                    default_value = param_def.get("default", "")
                    
                    label = f"{param_name}"
                    if required:
                        label += " *"
                    if description:
                        label += f" ({description})"
                    
                    if param_type == "integer":
                        params[param_name] = st.number_input(
                            label,
                            min_value=0,
                            value=int(default_value) if default_value else 0
                        )
                    elif param_type == "date":
                        params[param_name] = st.text_input(
                            label,
                            value=str(default_value),
                            placeholder="YYYYMMDD格式"
                        )
                    else:
                        params[param_name] = st.text_input(
                            label,
                            value=str(default_value)
                        )
                
                # 生成查詢按鈕
                if st.button("執行範本查詢"):
                    try:
                        sql = template_manager.generate_sql(st.session_state.selected_template, params)
                        
                        # 執行查詢
                        df_result = components['db_manager'].execute_query(sql)
                        
                        # 建立查詢結果
                        result = QueryResult(
                            success=True,
                            sql_query=sql,
                            results=df_result.to_dict('records'),
                            result_count=len(df_result),
                            interpretation=f"範本查詢完成，共找到 {len(df_result)} 筆資料。"
                        )
                        
                        # 更新session state
                        st.session_state.current_results = result
                        st.session_state.query_history.append({
                            'timestamp': datetime.now(),
                            'query': f"範本查詢: {template.name}",
                            'success': True,
                            'result_count': len(df_result)
                        })
                        
                        st.success("範本查詢執行成功！")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"範本查詢執行失敗: {e}")
                
                if st.button("清除範本選擇"):
                    st.session_state.selected_template = None
                    st.rerun()
            else:
                # 無參數範本，直接執行
                if st.button("執行範本查詢"):
                    try:
                        sql = template_manager.generate_sql(st.session_state.selected_template, {})
                        df_result = components['db_manager'].execute_query(sql)
                        
                        result = QueryResult(
                            success=True,
                            sql_query=sql,
                            results=df_result.to_dict('records'),
                            result_count=len(df_result),
                            interpretation=f"範本查詢完成，共找到 {len(df_result)} 筆資料。"
                        )
                        
                        st.session_state.current_results = result
                        st.session_state.query_history.append({
                            'timestamp': datetime.now(),
                            'query': f"範本查詢: {template.name}",
                            'success': True,
                            'result_count': len(df_result)
                        })
                        
                        st.success("範本查詢執行成功！")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"範本查詢執行失敗: {e}")
        
        st.divider()
    
    # 自然語言查詢
    st.write("**自然語言查詢：**")
    
    # 查詢建議
    with st.expander("💡 查詢建議", expanded=False):
        suggestions = components['llm_agent'].get_query_suggestions()
        for i, suggestion in enumerate(suggestions[:6]):
            if st.button(suggestion, key=f"suggestion_{i}"):
                st.session_state.query_input = suggestion
                st.rerun()
    
    # 查詢輸入框
    query_input = st.text_area(
        "請輸入您的查詢：",
        value=st.session_state.get('query_input', ''),
        height=100,
        placeholder="例如：查詢病患李小明的基本資料"
    )
    
    # 查詢按鈕
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("🔍 執行查詢", type="primary"):
            if query_input.strip():
                execute_query(components, query_input.strip())
            else:
                st.warning("請輸入查詢內容")
    
    with col2:
        if st.button("🗑️ 清除輸入"):
            st.session_state.query_input = ""
            st.rerun()


def execute_query(components, query):
    """執行查詢"""
    try:
        with st.spinner("正在處理查詢..."):
            # 使用LLM代理處理查詢
            result = components['llm_agent'].process_query(query, user_id="streamlit_user")
            
            # 更新session state
            st.session_state.current_results = result
            st.session_state.query_history.append({
                'timestamp': datetime.now(),
                'query': query,
                'success': result.success,
                'result_count': result.result_count if result.success else 0,
                'error': result.error_message if not result.success else ""
            })
            
            if result.success:
                st.success(f"✅ {result.interpretation}")
            else:
                st.error(f"❌ 查詢失敗: {result.error_message}")
            
            st.rerun()
            
    except Exception as e:
        st.error(f"查詢處理失敗: {e}")
        logger.error(f"查詢處理失敗: {e}")


def render_results(components):
    """渲染查詢結果"""
    if not st.session_state.current_results:
        return
    
    result = st.session_state.current_results
    
    st.header("📊 查詢結果")
    
    if result.success:
        # 結果摘要
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("查詢結果", f"{result.result_count} 筆")
        
        with col2:
            st.metric("執行時間", f"{result.execution_time:.3f} 秒")
        
        with col3:
            st.metric("資料表", "展望系統")
        
        with col4:
            if st.button("📥 下載結果"):
                if result.results:
                    df = pd.DataFrame(result.results)
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="下載CSV檔案",
                        data=csv,
                        file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
        
        # 顯示生成的SQL（如果啟用）
        if st.session_state.show_sql:
            with st.expander("🔍 生成的SQL語句", expanded=False):
                st.code(result.sql_query, language="sql")
        
        # 顯示查詢結果
        if result.results:
            st.subheader("📋 資料詳情")
            
            df = pd.DataFrame(result.results)
            
            # 顯示資料表
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            
            # 如果資料量適中，顯示一些基本分析
            if len(df) > 1 and len(df) <= 1000:
                render_data_analysis(df)
        else:
            st.info("查詢執行成功，但沒有找到符合條件的資料。")
    
    else:
        st.error("查詢執行失敗")
        st.error(result.error_message)


def render_data_analysis(df):
    """渲染資料分析"""
    try:
        st.subheader("📈 資料分析")
        
        # 基本統計
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**基本統計：**")
            st.write(f"- 總記錄數: {len(df)}")
            st.write(f"- 欄位數: {len(df.columns)}")
            
            # 數值欄位統計
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.write(f"- 數值欄位: {len(numeric_cols)}")
        
        with col2:
            # 如果有日期欄位，顯示日期範圍
            date_cols = [col for col in df.columns if 'date' in col.lower() or '日期' in col]
            if date_cols:
                st.write("**日期範圍：**")
                for col in date_cols[:2]:  # 最多顯示2個日期欄位
                    if df[col].notna().any():
                        try:
                            dates = pd.to_datetime(df[col], errors='coerce')
                            if dates.notna().any():
                                min_date = dates.min()
                                max_date = dates.max()
                                st.write(f"- {col}: {min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}")
                        except:
                            pass
        
        # 如果有合適的數值欄位，顯示圖表
        if len(numeric_cols) > 0 and len(df) > 1:
            with st.expander("📊 資料視覺化", expanded=False):
                
                # 選擇要視覺化的欄位
                chart_col = st.selectbox(
                    "選擇要視覺化的欄位：",
                    options=numeric_cols.tolist()
                )
                
                if chart_col:
                    # 直方圖
                    fig = px.histogram(
                        df,
                        x=chart_col,
                        title=f"{chart_col} 分布圖",
                        labels={chart_col: chart_col}
                    )
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        logger.warning(f"資料分析顯示失敗: {e}")


def render_query_history():
    """渲染查詢歷史"""
    if not st.session_state.query_history:
        st.info("尚無查詢歷史")
        return
    
    st.header("📚 查詢歷史")
    
    # 歷史統計
    total_queries = len(st.session_state.query_history)
    successful_queries = sum(1 for h in st.session_state.query_history if h['success'])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("總查詢次數", total_queries)
    
    with col2:
        st.metric("成功查詢", successful_queries)
    
    with col3:
        success_rate = successful_queries / total_queries if total_queries > 0 else 0
        st.metric("成功率", f"{success_rate:.1%}")
    
    # 查詢歷史列表
    st.subheader("查詢記錄")
    
    for i, history in enumerate(reversed(st.session_state.query_history[-20:])):  # 顯示最近20筆
        with st.expander(
            f"{'✅' if history['success'] else '❌'} {history['query'][:50]}... ({history['timestamp'].strftime('%H:%M:%S')})",
            expanded=False
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**查詢內容：** {history['query']}")
                st.write(f"**執行時間：** {history['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                if history['success']:
                    st.write(f"**結果數量：** {history['result_count']} 筆")
                else:
                    st.write(f"**錯誤訊息：** {history.get('error', '未知錯誤')}")
            
            with col2:
                if st.button(f"重新執行", key=f"rerun_{i}"):
                    st.session_state.query_input = history['query']
                    st.rerun()


def main():
    """主程式"""
    # 初始化session state
    initialize_session_state()
    
    # 初始化系統組件
    components = initialize_system()
    
    # 渲染頁面
    render_header()
    
    # 渲染側邊欄
    render_sidebar(components)
    
    # 主內容區域
    tab1, tab2, tab3 = st.tabs(["🔍 查詢", "📊 結果", "📚 歷史"])
    
    with tab1:
        render_query_interface(components)
    
    with tab2:
        render_results(components)
    
    with tab3:
        render_query_history()
    
    # 頁面底部資訊
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.9em;">
            🏥 診所AI查詢系統 v1.0.0 | 
            Powered by Ollama + Streamlit | 
            © 2025 Leon Lu
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()