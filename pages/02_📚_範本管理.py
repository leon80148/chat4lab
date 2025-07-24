"""
查詢範本管理頁面

提供查詢範本的瀏覽、測試、編輯和管理功能。

Author: Leon Lu
Created: 2025-01-24
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.query_templates import QueryTemplateManager, QueryTemplate
from src.modules.db_manager import DatabaseManager
from src.config import ConfigManager

# 頁面配置
st.set_page_config(
    page_title="範本管理 - 診所AI查詢系統",
    page_icon="📚",
    layout="wide"
)

# 自定義CSS
st.markdown("""
<style>
    .template-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 4px solid #007bff;
        margin: 1rem 0;
    }
    
    .template-header {
        font-size: 1.2em;
        font-weight: bold;
        color: #007bff;
        margin-bottom: 0.5rem;
    }
    
    .template-description {
        color: #6c757d;
        margin-bottom: 1rem;
    }
    
    .sql-code {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        overflow-x: auto;
    }
    
    .parameter-list {
        background-color: #e9ecef;
        border-radius: 4px;
        padding: 0.5rem;
        margin: 0.5rem 0;
    }
    
    .tag {
        background-color: #e7f3ff;
        color: #0066cc;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8em;
        margin: 0.2rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_components():
    """初始化系統組件"""
    try:
        config_manager = ConfigManager()
        template_manager = QueryTemplateManager()
        
        db_config = config_manager.get_database_config()
        db_manager = DatabaseManager(
            db_config.get('path', './data/anchia_lab.db'),
            db_config
        )
        
        return {
            'template_manager': template_manager,
            'db_manager': db_manager,
            'config_manager': config_manager,
            'status': 'success'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def render_template_browser(template_manager):
    """渲染範本瀏覽器"""
    st.header("🔍 瀏覽查詢範本")
    
    # 篩選選項
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categories = template_manager.get_categories()
        selected_category = st.selectbox(
            "類別篩選：",
            options=["全部"] + categories,
            index=0
        )
    
    with col2:
        all_tags = set()
        for template in template_manager.templates.values():
            all_tags.update(template.tags)
        
        selected_tags = st.multiselect(
            "標籤篩選：",
            options=sorted(list(all_tags))
        )
    
    with col3:
        search_keyword = st.text_input(
            "關鍵字搜尋：",
            placeholder="搜尋範本名稱或描述"
        )
    
    # 獲取篩選後的範本
    if search_keyword:
        templates = template_manager.search_templates(search_keyword)
    else:
        filter_category = None if selected_category == "全部" else selected_category
        templates = template_manager.list_templates(
            category=filter_category,
            tags=selected_tags if selected_tags else None
        )
    
    # 顯示範本數量
    st.write(f"找到 {len(templates)} 個範本")
    
    # 顯示範本
    if templates:
        for template in templates:
            render_template_card(template, template_manager)
    else:
        st.info("沒有找到符合條件的範本")


def render_template_card(template, template_manager):
    """渲染範本卡片"""
    with st.container():
        st.markdown(f"""
        <div class="template-card">
            <div class="template-header">{template.name}</div>
            <div class="template-description">{template.description}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 範本資訊
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 顯示參數
            if template.parameters:
                st.write("**參數：**")
                for param in template.parameters:
                    required_mark = " *" if param.get("required", False) else ""
                    default_info = f" (預設: {param['default']})" if "default" in param else ""
                    st.write(f"- `{param['name']}`{required_mark}: {param.get('description', '')}{default_info}")
            
            # 顯示標籤
            if template.tags:
                st.write("**標籤：**")
                tags_html = "".join([f'<span class="tag">{tag}</span>' for tag in template.tags])
                st.markdown(tags_html, unsafe_allow_html=True)
        
        with col2:
            st.write(f"**類別：** {template.category}")
            st.write(f"**ID：** `{template.id}`")
            
            # 操作按鈕
            col_test, col_edit = st.columns(2)
            
            with col_test:
                if st.button("🧪 測試", key=f"test_{template.id}"):
                    st.session_state.test_template_id = template.id
                    st.rerun()
            
            with col_edit:
                if st.button("👁️ 詳情", key=f"view_{template.id}"):
                    st.session_state.view_template_id = template.id
                    st.rerun()
        
        # 顯示SQL範本（摺疊）
        with st.expander(f"SQL範本 - {template.name}", expanded=False):
            st.code(template.sql_template, language="sql")
            
            # 範例參數
            examples = template_manager.get_template_examples(template.id)
            if examples:
                st.write("**範例參數：**")
                st.json(examples)
        
        st.divider()


def render_template_tester(components):
    """渲染範本測試器"""
    st.header("🧪 範本測試")
    
    if 'test_template_id' not in st.session_state:
        st.info("請從範本瀏覽器中選擇要測試的範本")
        return
    
    template_manager = components['template_manager']
    db_manager = components['db_manager']
    
    template_id = st.session_state.test_template_id
    template = template_manager.get_template(template_id)
    
    if not template:
        st.error("範本不存在")
        return
    
    st.write(f"**測試範本：** {template.name}")
    st.write(f"**描述：** {template.description}")
    
    # 參數輸入
    params = {}
    if template.parameters:
        st.subheader("📝 參數設定")
        
        # 使用範例參數按鈕
        examples = template_manager.get_template_examples(template_id)
        if examples and st.button("使用範例參數"):
            st.session_state.template_params = examples
            st.rerun()
        
        # 參數輸入表單
        for param_def in template.parameters:
            param_name = param_def["name"]
            param_type = param_def.get("type", "string")
            description = param_def.get("description", "")
            required = param_def.get("required", False)
            default_value = param_def.get("default", "")
            
            # 從session state獲取之前的值
            session_key = f"param_{template_id}_{param_name}"
            previous_value = st.session_state.get('template_params', {}).get(param_name, default_value)
            
            label = f"{param_name}"
            if required:
                label += " *"
            if description:
                label += f" ({description})"
            
            if param_type == "integer":
                params[param_name] = st.number_input(
                    label,
                    min_value=0,
                    value=int(previous_value) if previous_value else 0,
                    key=session_key
                )
            elif param_type == "date":
                params[param_name] = st.text_input(
                    label,
                    value=str(previous_value),
                    placeholder="YYYYMMDD格式",
                    key=session_key
                )
            else:
                params[param_name] = st.text_input(
                    label,
                    value=str(previous_value),
                    key=session_key
                )
    
    # 執行測試
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🚀 執行測試", type="primary"):
            try:
                # 生成SQL
                sql = template_manager.generate_sql(template_id, params)
                
                st.subheader("📋 生成的SQL")
                st.code(sql, language="sql")
                
                # 執行查詢
                with st.spinner("執行查詢中..."):
                    result = db_manager.execute_query(sql, user_id="template_test")
                
                st.subheader("📊 查詢結果")
                
                if len(result) > 0:
                    st.success(f"查詢成功！共找到 {len(result)} 筆資料")
                    
                    # 顯示結果
                    st.dataframe(result, use_container_width=True)
                    
                    # 下載按鈕
                    csv = result.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 下載結果",
                        data=csv,
                        file_name=f"template_test_{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("查詢執行成功，但沒有找到符合條件的資料")
                
            except Exception as e:
                st.error(f"測試失敗: {e}")
    
    with col2:
        if st.button("🗑️ 清除測試"):
            if 'test_template_id' in st.session_state:
                del st.session_state.test_template_id
            if 'template_params' in st.session_state:
                del st.session_state.template_params
            st.rerun()


def render_custom_template_creator(template_manager):
    """渲染自訂範本創建器"""
    st.header("➕ 創建自訂範本")
    
    with st.form("custom_template_form"):
        st.subheader("📝 範本基本資訊")
        
        col1, col2 = st.columns(2)
        
        with col1:
            template_id = st.text_input(
                "範本ID *",
                placeholder="例如: custom_patient_query",
                help="唯一識別符，只能包含字母、數字和底線"
            )
            
            template_name = st.text_input(
                "範本名稱 *",
                placeholder="例如: 自訂病患查詢"
            )
            
            template_category = st.selectbox(
                "範本類別 *",
                options=["病患資料", "就診記錄", "處方記錄", "檢驗結果", "統計分析", "自訂類別"]
            )
        
        with col2:
            template_description = st.text_area(
                "範本描述 *",
                placeholder="詳細描述這個範本的用途和功能",
                height=100
            )
            
            template_tags = st.text_input(
                "標籤",
                placeholder="用逗號分隔，例如: 病患,查詢,自訂"
            )
        
        st.subheader("💻 SQL範本")
        sql_template = st.text_area(
            "SQL語句範本 *",
            placeholder="使用 {參數名稱} 的格式來定義參數位置",
            height=150,
            help="範例: SELECT * FROM CO01M WHERE mname LIKE '%{name}%' LIMIT {limit}"
        )
        
        st.subheader("⚙️ 參數定義")
        st.write("定義SQL範本中使用的參數：")
        
        # 參數定義
        num_params = st.number_input("參數數量", min_value=0, max_value=10, value=0)
        
        parameters = []
        example_values = {}
        
        if num_params > 0:
            for i in range(num_params):
                st.write(f"**參數 {i+1}:**")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    param_name = st.text_input(f"參數名稱", key=f"param_name_{i}")
                
                with col2:
                    param_type = st.selectbox(
                        f"資料類型",
                        options=["string", "integer", "date"],
                        key=f"param_type_{i}"
                    )
                
                with col3:
                    param_required = st.checkbox(f"必填", key=f"param_required_{i}")
                
                with col4:
                    param_default = st.text_input(f"預設值", key=f"param_default_{i}")
                
                param_description = st.text_input(
                    f"參數描述",
                    key=f"param_desc_{i}",
                    placeholder="描述這個參數的用途"
                )
                
                example_value = st.text_input(
                    f"範例值",
                    key=f"param_example_{i}",
                    placeholder="提供一個範例值"
                )
                
                if param_name:
                    param_def = {
                        "name": param_name,
                        "type": param_type,
                        "required": param_required,
                        "description": param_description
                    }
                    
                    if param_default:
                        param_def["default"] = param_default
                    
                    parameters.append(param_def)
                    
                    if example_value:
                        example_values[param_name] = example_value
                
                st.divider()
        
        # 提交按鈕
        submitted = st.form_submit_button("🚀 創建範本", type="primary")
        
        if submitted:
            # 驗證輸入
            errors = []
            
            if not template_id:
                errors.append("範本ID為必填項目")
            elif template_id in template_manager.templates:
                errors.append("範本ID已存在")
            
            if not template_name:
                errors.append("範本名稱為必填項目")
            
            if not template_description:
                errors.append("範本描述為必填項目")
            
            if not sql_template:
                errors.append("SQL範本為必填項目")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    # 處理標籤
                    tags = [tag.strip() for tag in template_tags.split(",") if tag.strip()]
                    
                    # 創建範本
                    custom_template = QueryTemplate(
                        id=template_id,
                        name=template_name,
                        description=template_description,
                        category=template_category,
                        sql_template=sql_template,
                        parameters=parameters,
                        example_values=example_values,
                        tags=tags
                    )
                    
                    # 添加到管理器
                    success = template_manager.add_custom_template(custom_template)
                    
                    if success:
                        st.success(f"✅ 自訂範本 '{template_name}' 創建成功！")
                        st.balloons()
                    else:
                        st.error("創建範本失敗")
                
                except Exception as e:
                    st.error(f"創建範本時發生錯誤: {e}")


def render_template_statistics(template_manager):
    """渲染範本統計"""
    st.header("📊 範本統計")
    
    templates = list(template_manager.templates.values())
    
    # 基本統計
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("總範本數", len(templates))
    
    with col2:
        categories = len(template_manager.get_categories())
        st.metric("類別數", categories)
    
    with col3:
        all_tags = set()
        for template in templates:
            all_tags.update(template.tags)
        st.metric("標籤數", len(all_tags))
    
    with col4:
        avg_params = sum(len(t.parameters) for t in templates) / len(templates) if templates else 0
        st.metric("平均參數數", f"{avg_params:.1f}")
    
    # 類別分布
    st.subheader("📈 類別分布")
    
    category_counts = {}
    for template in templates:
        category = template.category
        category_counts[category] = category_counts.get(category, 0) + 1
    
    if category_counts:
        df_categories = pd.DataFrame(
            list(category_counts.items()),
            columns=['類別', '數量']
        )
        
        import plotly.express as px
        fig = px.pie(
            df_categories,
            values='數量',
            names='類別',
            title="範本類別分布"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 標籤雲
    st.subheader("🏷️ 標籤統計")
    
    tag_counts = {}
    for template in templates:
        for tag in template.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    if tag_counts:
        # 顯示前10個最常用的標籤
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        df_tags = pd.DataFrame(sorted_tags, columns=['標籤', '使用次數'])
        
        fig = px.bar(
            df_tags,
            x='標籤',
            y='使用次數',
            title="最常用標籤 (前10名)"
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def main():
    """主程式"""
    st.title("📚 查詢範本管理")
    st.markdown("管理和測試系統查詢範本")
    
    # 初始化組件
    components = initialize_components()
    
    if components['status'] != 'success':
        st.error(f"系統初始化失敗: {components.get('error', '未知錯誤')}")
        return
    
    template_manager = components['template_manager']
    
    # 主要功能標籤
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 瀏覽範本",
        "🧪 測試範本", 
        "➕ 創建範本",
        "📊 範本統計"
    ])
    
    with tab1:
        render_template_browser(template_manager)
    
    with tab2:
        render_template_tester(components)
    
    with tab3:
        render_custom_template_creator(template_manager)
    
    with tab4:
        render_template_statistics(template_manager)


if __name__ == "__main__":
    main()