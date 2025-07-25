"""
AI對話頁面

提供類似ChatGPT的聊天式AI查詢體驗，支援連續對話、上下文理解、
智能建議等功能。

Author: Leon Lu
Created: 2025-01-25
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path
import time
import json

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager, DatabaseError
from src.modules.llm_agent_v2 import ModernLLMQueryAgent as LLMQueryAgent
from src.modules.conversation_manager import (
    conversation_manager, MessageRole, MessageType, ChatMessage
)

# 頁面配置
st.set_page_config(
    page_title="AI對話 - 診所AI查詢系統",
    page_icon="💬",
    layout="wide"
)

# 自定義CSS樣式
st.markdown("""
<style>
    /* 聊天容器樣式 */
    .chat-container {
        height: 500px;
        overflow-y: auto;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #fafafa;
        margin-bottom: 1rem;
    }
    
    /* 用戶訊息氣泡 */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 5px 18px;
        margin: 0.5rem 0 0.5rem auto;
        max-width: 80%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        word-wrap: break-word;
    }
    
    /* AI助手訊息氣泡 */
    .assistant-message {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 18px 5px;
        margin: 0.5rem auto 0.5rem 0;
        max-width: 80%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        word-wrap: break-word;
    }
    
    /* 系統訊息 */
    .system-message {
        background-color: #e9ecef;
        color: #495057;
        padding: 0.5rem 1rem;
        border-radius: 15px;
        margin: 0.3rem auto;
        max-width: 60%;
        text-align: center;
        font-size: 0.9em;
        border: 1px solid #dee2e6;
    }
    
    /* 打字效果 */
    .typing-indicator {
        background-color: #f8f9fa;
        color: #6c757d;
        padding: 0.5rem 1rem;
        border-radius: 15px;
        margin: 0.3rem auto 0.3rem 0;
        max-width: 60%;
        border: 1px solid #dee2e6;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    
    /* 建議按鈕 */
    .suggestion-button {
        background-color: #e3f2fd;
        border: 1px solid #90caf9;
        border-radius: 20px;
        padding: 0.4rem 0.8rem;
        margin: 0.2rem;
        font-size: 0.9em;
        color: #1976d2;
        cursor: pointer;
        transition: all 0.2s;
        display: inline-block;
    }
    
    .suggestion-button:hover {
        background-color: #bbdefb;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 輸入框樣式 */
    .chat-input {
        border-radius: 25px;
        border: 2px solid #e0e0e0;
        padding: 0.8rem 1.2rem;
        font-size: 1rem;
        transition: border-color 0.2s;
    }
    
    .chat-input:focus {
        border-color: #667eea;
        outline: none;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* 結果表格容器 */
    .result-table-container {
        background-color: white;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 統計卡片 */
    .stats-card {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    /* 主要標題 */
    .chat-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 清除按鈕 */
    .clear-chat-btn {
        background-color: #ff6b6b;
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    
    .clear-chat-btn:hover {
        background-color: #ee5a52;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_components():
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


def initialize_session_state():
    """初始化session state"""
    if 'chat_initialized' not in st.session_state:
        st.session_state.chat_initialized = True
        # 添加歡迎訊息
        conversation_manager.add_message(
            MessageRole.ASSISTANT,
            "您好！我是診所AI助手 🏥\n\n我可以幫您查詢病患資料、分析檢驗結果、統計就診記錄等。請用自然語言告訴我您想了解什麼，例如：\n\n• 「盧盈良的最近檢驗結果」\n• 「上週的就診統計」\n• 「血糖異常的病患名單」\n\n有什麼我可以幫您的嗎？",
            MessageType.TEXT
        )
    
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    
    if 'last_suggestions' not in st.session_state:
        st.session_state.last_suggestions = []


def render_chat_message(message: ChatMessage):
    """渲染單一聊天訊息"""
    if message.role == MessageRole.USER:
        st.markdown(f"""
        <div class="user-message">
            <strong>您：</strong> {message.content}
        </div>
        """, unsafe_allow_html=True)
        
    elif message.role == MessageRole.ASSISTANT:
        st.markdown(f"""
        <div class="assistant-message">
            <strong>🤖 AI助手：</strong> {message.content}
        </div>
        """, unsafe_allow_html=True)
        
        # 如果有查詢結果，顯示表格
        if message.metadata and 'query_result' in message.metadata:
            render_query_result(message.metadata['query_result'])
            
    elif message.role == MessageRole.SYSTEM:
        st.markdown(f"""
        <div class="system-message">
            {message.content}
        </div>
        """, unsafe_allow_html=True)


def render_query_result(result: dict):
    """渲染查詢結果"""
    if not result.get('success'):
        return
    
    data = result.get('data')
    if data is not None and len(data) > 0:
        # 轉換為DataFrame
        df = pd.DataFrame(data)
        
        st.markdown('<div class="result-table-container">', unsafe_allow_html=True)
        
        # 顯示結果統計
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("查詢結果", f"{len(df)} 筆記錄")
        
        with col2:
            execution_time = result.get('execution_time', 0)
            st.metric("執行時間", f"{execution_time:.3f} 秒")
        
        with col3:
            confidence = result.get('confidence', 'unknown')
            st.metric("查詢信心度", confidence)
        
        # 顯示資料表
        st.dataframe(df, use_container_width=True, height=300)
        
        # 如果是數值資料，顯示簡單圖表
        numeric_columns = df.select_dtypes(include=['number']).columns
        if len(numeric_columns) > 0 and len(df) > 1:
            try:
                # 簡單的趨勢圖
                if 'hdate' in df.columns or 'idate' in df.columns:
                    date_col = 'hdate' if 'hdate' in df.columns else 'idate'
                    numeric_col = numeric_columns[0]
                    
                    fig = px.line(
                        df, 
                        x=date_col, 
                        y=numeric_col,
                        title=f"{numeric_col} 趨勢圖",
                        template="plotly_white"
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                pass  # 圖表顯示失敗不影響主要功能
        
        st.markdown('</div>', unsafe_allow_html=True)


def render_typing_indicator():
    """渲染打字指示器"""
    st.markdown("""
    <div class="typing-indicator">
        🤖 AI助手正在思考中...
    </div>
    """, unsafe_allow_html=True)


def render_suggestions(suggestions: list):
    """渲染智能建議"""
    if not suggestions:
        return
    
    st.markdown("**💡 您可能還想了解：**")
    
    # 創建建議按鈕
    cols = st.columns(min(len(suggestions), 3))
    
    for i, suggestion in enumerate(suggestions[:3]):
        with cols[i % 3]:
            if st.button(
                suggestion, 
                key=f"suggestion_{i}_{hash(suggestion)}", 
                use_container_width=True
            ):
                # 用戶點擊建議，作為新的查詢
                handle_user_input(suggestion)
                st.rerun()


def handle_user_input(user_input: str):
    """處理用戶輸入"""
    if not user_input.strip():
        return
    
    # 添加用戶訊息
    conversation_manager.add_message(
        MessageRole.USER,
        user_input,
        MessageType.TEXT
    )
    
    # 標記為處理中
    st.session_state.processing = True


def process_ai_response(components: dict, user_input: str):
    """處理AI回應"""
    try:
        # 獲取對話上下文
        context = conversation_manager.get_context_for_llm()
        
        # 準備查詢（包含上下文）
        enhanced_query = user_input
        if context:
            enhanced_query = f"對話上下文：\n{context}\n\n當前查詢：{user_input}"
        
        # 執行查詢
        llm_agent = components['llm_agent']
        result = llm_agent.process_query(enhanced_query)
        
        # 生成回應內容
        if result.success:
            # 成功的查詢
            response_content = f"✅ 查詢完成！\n\n"
            
            if result.data and len(result.data) > 0:
                response_content += f"找到 **{len(result.data)}** 筆相關記錄。"
            else:
                response_content += "查詢執行成功，但沒有找到符合條件的記錄。"
            
            if result.explanation:
                response_content += f"\n\n**查詢說明：** {result.explanation}"
            
            # 添加AI回應
            conversation_manager.add_message(
                MessageRole.ASSISTANT,
                response_content,
                MessageType.QUERY_RESULT,
                metadata={
                    'query_result': {
                        'success': True,
                        'data': result.data,
                        'sql_query': result.sql_query,
                        'execution_time': result.execution_time,
                        'confidence': result.confidence,
                        'explanation': result.explanation
                    }
                }
            )
            
            # 生成智能建議
            suggestions = conversation_manager.generate_suggestions({
                'success': True,
                'query_type': result.query_type,
                'sql_query': result.sql_query
            })
            st.session_state.last_suggestions = suggestions
            
        else:
            # 查詢失敗
            error_content = f"❌ 查詢失敗\n\n{result.error_message}\n\n請嘗試用不同的方式描述您的需求，或者檢查查詢條件是否正確。"
            
            conversation_manager.add_message(
                MessageRole.ASSISTANT,
                error_content,
                MessageType.ERROR,
                metadata={'error': result.error_message}
            )
            
            # 生成通用建議
            st.session_state.last_suggestions = [
                "查詢特定病患的基本資料",
                "分析最近一週的就診統計", 
                "查看常用檢驗項目的結果"
            ]
            
    except Exception as e:
        # 系統錯誤
        error_content = f"🔧 系統錯誤\n\n很抱歉，處理您的請求時發生了錯誤：{str(e)}\n\n請稍後再試，或聯繫系統管理員。"
        
        conversation_manager.add_message(
            MessageRole.ASSISTANT,
            error_content,
            MessageType.ERROR,
            metadata={'system_error': str(e)}
        )
        
        st.session_state.last_suggestions = []
    
    finally:
        # 重置處理狀態
        st.session_state.processing = False


def render_chat_stats():
    """渲染聊天統計"""
    stats = conversation_manager.context.session_stats
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stats-card">
            <h4>總查詢次數</h4>
            <h2>{}</h2>
        </div>
        """.format(stats['total_queries']), unsafe_allow_html=True)
    
    with col2:
        success_rate = (stats['successful_queries'] / max(stats['total_queries'], 1)) * 100
        st.markdown("""
        <div class="stats-card">
            <h4>成功率</h4>
            <h2>{:.1f}%</h2>
        </div>
        """.format(success_rate), unsafe_allow_html=True)
    
    with col3:
        message_count = len(conversation_manager.get_conversation_history())
        st.markdown("""
        <div class="stats-card">
            <h4>對話輪次</h4>
            <h2>{}</h2>
        </div>
        """.format(message_count), unsafe_allow_html=True)


def main():
    """主程式"""
    # 初始化
    initialize_session_state()
    components = initialize_components()
    
    # 檢查系統狀態
    if components['status'] != 'success':
        st.error(f"系統初始化失敗：{components.get('error', '未知錯誤')}")
        return
    
    # 頁面標題
    st.markdown("""
    <div class="chat-header">
        <h1>🤖 AI智能對話</h1>
        <p>與診所AI助手進行自然語言對話，獲取準確的醫療資料分析</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 主要布局
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 聊天歷史區域
        st.markdown("### 💬 對話歷史")
        
        # 聊天容器
        chat_container = st.container()
        
        with chat_container:
            # 顯示所有訊息
            messages = conversation_manager.get_conversation_history()
            
            for message in messages:
                render_chat_message(message)
            
            # 如果正在處理，顯示打字指示器
            if st.session_state.processing:
                render_typing_indicator()
        
        # 智能建議
        if st.session_state.last_suggestions:
            st.markdown("---")
            render_suggestions(st.session_state.last_suggestions)
        
        # 輸入區域
        st.markdown("---")
        st.markdown("### ✍️ 輸入您的問題")
        
        # 輸入框和發送按鈕
        input_col, button_col = st.columns([4, 1])
        
        with input_col:
            user_input = st.text_input(
                "請輸入您的問題...",
                key="chat_input",
                placeholder="例如：盧盈良的最近檢驗結果",
                label_visibility="collapsed",
                disabled=st.session_state.processing
            )
        
        with button_col:
            send_clicked = st.button(
                "發送 📤", 
                disabled=st.session_state.processing or not user_input.strip(),
                use_container_width=True
            )
        
        # 處理發送
        if send_clicked and user_input.strip():
            handle_user_input(user_input)
            st.rerun()
        
        # 處理AI回應
        if st.session_state.processing:
            # 獲取最後一條用戶訊息
            messages = conversation_manager.get_conversation_history()
            if messages and messages[-1].role == MessageRole.USER:
                last_user_message = messages[-1].content
                process_ai_response(components, last_user_message)
                st.rerun()
    
    with col2:
        # 側邊欄功能
        st.markdown("### 📊 對話統計")
        render_chat_stats()
        
        st.markdown("---")
        
        # 清除對話按鈕
        if st.button("🗑️ 清除對話", use_container_width=True):
            conversation_manager.clear_conversation()
            st.session_state.last_suggestions = []
            st.session_state.processing = False
            
            # 重新添加歡迎訊息
            conversation_manager.add_message(
                MessageRole.ASSISTANT,
                "對話已清除！我是診所AI助手，有什麼可以幫您的嗎？",
                MessageType.TEXT
            )
            st.rerun()
        
        # 導出對話
        if st.button("📥 導出對話", use_container_width=True):
            conversation_data = conversation_manager.export_conversation()
            st.download_button(
                "下載對話記錄",
                data=json.dumps(conversation_data, ensure_ascii=False, indent=2),
                file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # 快速查詢範例
        st.markdown("### 🔍 查詢範例")
        
        examples = [
            "盧盈良的基本資料",
            "最近一週的就診統計",
            "血糖超標的病患", 
            "常用藥物統計",
            "檢驗項目分析"
        ]
        
        for example in examples:
            if st.button(example, key=f"example_{hash(example)}", use_container_width=True):
                handle_user_input(example)
                st.rerun()
        
        st.markdown("---")
        st.markdown("""
        **💡 使用提示：**
        - 使用自然語言描述需求
        - 可以詢問病患、檢驗、處方等
        - 支援連續對話和追問
        - 系統會自動記住上下文
        """)


if __name__ == "__main__":
    main()