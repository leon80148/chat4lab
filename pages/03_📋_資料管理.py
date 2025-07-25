"""
資料管理頁面

提供資料庫管理、DBF檔案匯入、資料匯出等功能。

Author: Leon Lu
Created: 2025-01-24
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path
import tempfile
import shutil

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.modules.db_manager import DatabaseManager, DatabaseError
from src.modules.dbf_parser import ZhanWangDBFParser, DBFParseError

# 頁面配置
st.set_page_config(
    page_title="資料管理 - 診所AI查詢系統",
    page_icon="📋",
    layout="wide"
)

# 自定義CSS
st.markdown("""
<style>
    .data-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    
    .import-section {
        background-color: #e7f3ff;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .table-info {
        background-color: #f8f9fa;
        border-radius: 4px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


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
        
        dbf_parser = ZhanWangDBFParser(encoding='big5', strict_mode=False)
        
        return {
            'config_manager': config_manager,
            'db_manager': db_manager,
            'dbf_parser': dbf_parser,
            'status': 'success'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def render_database_overview(db_manager):
    """渲染資料庫概覽"""
    st.header("🗄️ 資料庫概覽")
    
    try:
        # 獲取資料庫統計
        db_stats = db_manager.get_table_stats()
        
        # 基本統計
        col1, col2, col3, col4 = st.columns(4)
        
        total_records = sum(
            stats.get('record_count', 0) 
            for stats in db_stats['tables'].values()
            if 'record_count' in stats
        )
        
        db_size_mb = db_stats['database_size'] / (1024 * 1024)
        
        with col1:
            st.metric("總記錄數", f"{total_records:,}")
        
        with col2:
            st.metric("資料表數", len(db_stats['tables']))
        
        with col3:
            st.metric("資料庫大小", f"{db_size_mb:.2f} MB")
        
        with col4:
            query_stats = db_stats['query_stats']
            st.metric("執行查詢數", f"{query_stats['queries_executed']:,}")
        
        # 資料表詳情
        st.subheader("📊 資料表統計")
        
        table_data = []
        for table_name, stats in db_stats['tables'].items():
            if 'record_count' in stats:
                table_data.append({
                    '資料表': table_name,
                    '記錄數': stats['record_count'],
                    '欄位數': stats.get('column_count', 'N/A'),
                    '索引數': stats.get('index_count', 'N/A')
                })
        
        if table_data:
            df_tables = pd.DataFrame(table_data)
            
            # 顯示表格
            st.dataframe(df_tables, use_container_width=True, hide_index=True)
            
            # 視覺化
            fig = px.bar(
                df_tables,
                x='資料表',
                y='記錄數',
                title="各資料表記錄數量",
                color='記錄數',
                color_continuous_scale='viridis'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # 資料表詳細資訊
        with st.expander("🔍 資料表結構詳情", expanded=False):
            selected_table = st.selectbox(
                "選擇資料表：",
                options=list(db_stats['tables'].keys())
            )
            
            if selected_table and st.button("查看結構"):
                try:
                    table_info = db_manager.get_table_info(selected_table)
                    
                    st.write(f"**資料表：** {table_info['table_name']}")
                    st.write(f"**記錄數：** {table_info['record_count']:,}")
                    
                    # 欄位資訊
                    st.write("**欄位結構：**")
                    columns_data = []
                    for col in table_info['columns']:
                        columns_data.append({
                            '欄位名稱': col['name'],
                            '資料類型': col['type'],
                            '允許NULL': '是' if col['notnull'] == 0 else '否',
                            '預設值': col['dflt_value'] if col['dflt_value'] else '',
                            '主鍵': '是' if col['pk'] == 1 else '否'
                        })
                    
                    df_columns = pd.DataFrame(columns_data)
                    st.dataframe(df_columns, use_container_width=True, hide_index=True)
                    
                    # 索引資訊
                    if table_info['indexes']:
                        st.write("**索引資訊：**")
                        for idx in table_info['indexes']:
                            st.write(f"- {idx['name']}: {'唯一' if idx['unique'] else '一般'}")
                
                except Exception as e:
                    st.error(f"無法獲取資料表資訊: {e}")
    
    except Exception as e:
        st.error(f"無法獲取資料庫統計: {e}")


def render_dbf_importer(components):
    """渲染DBF檔案匯入器"""
    st.header("📥 DBF檔案匯入")
    
    db_manager = components['db_manager']
    dbf_parser = components['dbf_parser']
    
    st.markdown("""
    <div class="import-section">
        <h4>📋 匯入說明</h4>
        <p>支援展望診療系統的DBF檔案匯入，包括：</p>
        <ul>
            <li><strong>CO01M.dbf</strong> - 病患主資料檔</li>
            <li><strong>CO02M.dbf</strong> - 處方記錄檔</li>
            <li><strong>CO03M.dbf</strong> - 就診摘要檔</li>
            <li><strong>CO18H.dbf</strong> - 檢驗結果歷史檔</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 匯入方式選擇
    st.subheader("🎯 選擇匯入方式")
    import_method = st.radio(
        "",
        ["🔗 檔案上傳", "📁 本地路徑"],
        horizontal=True
    )
    
    if import_method == "🔗 檔案上傳":
        # 檔案上傳方式
        st.markdown("### 📤 拖拉上傳檔案")
        uploaded_files = st.file_uploader(
            "選擇DBF檔案",
            type=['dbf'],
            accept_multiple_files=True,
            help="支援拖拉多個DBF檔案，或點擊瀏覽選擇檔案"
        )
    else:
        # 本地路徑方式
        st.markdown("### 📁 本地檔案路徑")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            local_path = st.text_input(
                "DBF檔案路徑",
                placeholder="輸入完整檔案路徑，例如：/Users/username/data/CO01M.dbf",
                help="支援絕對路徑和相對路徑"
            )
        with col2:
            if st.button("🔍 瀏覽", help="在未來版本將支援檔案瀏覽器"):
                st.info("檔案瀏覽器功能開發中...")
        
        # 檢查路徑是否存在
        uploaded_files = None
        if local_path:
            if Path(local_path).exists() and local_path.endswith('.dbf'):
                st.success(f"✅ 檔案存在：{Path(local_path).name}")
                # 模擬上傳檔案格式
                uploaded_files = [{'name': Path(local_path).name, 'path': local_path, 'is_local': True}]
            elif local_path:
                st.error("❌ 檔案不存在或非DBF格式")
    
    # 檔案處理
    if import_method == "🔗 檔案上傳":
        files_to_process = uploaded_files
    else:
        files_to_process = uploaded_files
    
    if files_to_process:
        st.write(f"已選擇 {len(files_to_process)} 個檔案：")
        
        # 檔案資訊顯示
        for file_item in files_to_process:
            if import_method == "🔗 檔案上傳":
                file_size = f"({file_item.size:,} bytes)" if hasattr(file_item, 'size') else ""
                st.write(f"- {file_item.name} {file_size}")
            else:
                file_size = Path(file_item['path']).stat().st_size if Path(file_item['path']).exists() else 0
                st.write(f"- {file_item['name']} ({file_size:,} bytes) 📁")
        
        # 匯入選項
        col1, col2 = st.columns(2)
        
        with col1:
            import_mode = st.selectbox(
                "匯入模式：",
                options=[
                    ("append", "追加 - 在現有資料後添加"),
                    ("replace", "替換 - 清空後重新匯入"),
                    ("fail", "失敗 - 如果表已存在則失敗")
                ],
                format_func=lambda x: x[1]
            )
        
        with col2:
            strict_mode = st.checkbox(
                "嚴格模式",
                value=False,
                help="啟用資料驗證，發現錯誤時停止匯入"
            )
        
        # 預覽檔案內容
        if st.checkbox("📋 預覽檔案結構", value=False):
            if import_method == "🔗 檔案上傳":
                preview_file = st.selectbox(
                    "選擇要預覽的檔案：",
                    options=[f.name for f in files_to_process]
                )
                selected_file = next(f for f in files_to_process if f.name == preview_file)
            else:
                preview_file = files_to_process[0]['name']
                selected_file = files_to_process[0]
                st.write(f"📄 預覽檔案：{preview_file}")
            
            try:
                # 處理檔案路徑
                if import_method == "🔗 檔案上傳":
                    # 儲存暫存檔案
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.dbf') as tmp_file:
                        tmp_file.write(selected_file.getvalue())
                        tmp_path = tmp_file.name
                else:
                    # 使用本地檔案路徑
                    tmp_path = selected_file['path']
                
                # 解析預覽
                with st.spinner("解析檔案中..."):
                    try:
                        result = dbf_parser.parse_auto(tmp_path)
                        
                        st.success(f"檔案類型：{result['table_type']}")
                        st.write(f"記錄數：{result['metadata']['record_count']}")
                        
                        # 顯示前幾行資料
                        df_preview = pd.DataFrame(result['data'])
                        st.write("**資料預覽（前10行）：**")
                        st.dataframe(df_preview.head(10), use_container_width=True)
                        
                        # 驗證結果
                        if result['validation']['valid']:
                            st.success("✅ 資料驗證通過")
                        else:
                            st.warning("⚠️ 資料驗證有警告")
                            for error in result['validation']['errors']:
                                st.warning(f"- {error}")
                    
                    except Exception as e:
                        st.error(f"解析失敗：{e}")
                    finally:
                        # 清理暫存檔案（只在上傳檔案時）
                        if import_method == "🔗 檔案上傳":
                            Path(tmp_path).unlink(missing_ok=True)
            
            except Exception as e:
                st.error(f"檔案處理失敗：{e}")
        
        # 匯入按鈕
        if st.button("🚀 開始匯入", type="primary"):
            import_files_enhanced(files_to_process, db_manager, dbf_parser, import_mode[0], strict_mode, import_method)


def import_files_enhanced(files_to_process, db_manager, dbf_parser, import_mode, strict_mode, import_method):
    """增強版檔案匯入器"""
    
    # 創建進度條和狀態顯示
    st.markdown("### 📊 匯入進度")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 結果統計
    results = {
        'success': 0,
        'failed': 0,
        'total_records': 0,
        'details': []
    }
    
    try:
        with st.spinner("🚀 智能匯入處理中..."):
            for i, file_item in enumerate(files_to_process):
                # 取得檔案資訊
                if import_method == "🔗 檔案上傳":
                    file_name = file_item.name
                    status_text.text(f"📤 處理上傳檔案：{file_name}")
                else:
                    file_name = file_item['name']
                    status_text.text(f"📁 處理本地檔案：{file_name}")
                
                try:
                    # 處理檔案路徑
                    if import_method == "🔗 檔案上傳":
                        # 儲存暫存檔案
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.dbf') as tmp_file:
                            tmp_file.write(file_item.getvalue())
                            tmp_path = tmp_file.name
                    else:
                        # 使用本地檔案路徑
                        tmp_path = file_item['path']
                    
                    # 解析檔案
                    with st.spinner(f"🔍 解析 {file_name}..."):
                        result = dbf_parser.parse_auto(tmp_path)
                        
                        table_type = result['table_type']
                        df_data = pd.DataFrame(result['data'])
                        record_count = len(df_data)
                        
                        # 嚴格模式檢查
                        if strict_mode and not result['validation']['valid']:
                            raise Exception(f"資料驗證失敗：{result['validation']['errors']}")
                        
                        # 匯入資料庫
                        success = db_manager.import_dbf_data(
                            table_type, 
                            df_data, 
                            if_exists=import_mode
                        )
                        
                        if success:
                            results['success'] += 1
                            results['total_records'] += record_count
                            results['details'].append({
                                'file': file_name,
                                'table': table_type,
                                'records': record_count,
                                'status': '✅ 成功',
                                'method': '📤 上傳' if import_method == "🔗 檔案上傳" else '📁 本地'
                            })
                            st.success(f"✅ {file_name} 匯入成功（{record_count:,} 筆）")
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'file': file_name,
                                'table': table_type,
                                'records': 0,
                                'status': '❌ 失敗',
                                'method': '📤 上傳' if import_method == "🔗 檔案上傳" else '📁 本地'
                            })
                            st.error(f"❌ {file_name} 匯入失敗")
                
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'file': file_name,
                        'table': 'N/A',
                        'records': 0,
                        'status': f'💥 錯誤：{str(e)}',
                        'method': '📤 上傳' if import_method == "🔗 檔案上傳" else '📁 本地'
                    })
                    st.error(f"❌ {file_name} 處理失敗：{e}")
                
                finally:
                    # 清理暫存檔案（只在上傳檔案時）
                    if import_method == "🔗 檔案上傳" and 'tmp_path' in locals():
                        Path(tmp_path).unlink(missing_ok=True)
                
                # 更新進度
                progress = (i + 1) / len(files_to_process)
                progress_bar.progress(progress)
            
            # 顯示匯入摘要
            status_text.text("🎉 匯入完成")
            
            st.markdown("### 📊 匯入摘要")
            
            # 統計卡片
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="stats-card" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);">
                    <h4>成功匯入</h4>
                    <h2>{results['success']}</h2>
                    <p>個檔案</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="stats-card" style="background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);">
                    <h4>匯入失敗</h4>
                    <h2>{results['failed']}</h2>
                    <p>個檔案</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="stats-card" style="background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);">
                    <h4>總記錄數</h4>
                    <h2>{results['total_records']:,}</h2>
                    <p>筆資料</p>
                </div>
                """, unsafe_allow_html=True)
            
            # 詳細結果表格
            if results['details']:
                st.markdown("### 📋 詳細結果")
                df_results = pd.DataFrame(results['details'])
                st.dataframe(df_results, use_container_width=True, hide_index=True)
                
                # 下載結果報告
                csv_report = df_results.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下載匯入報告",
                    data=csv_report,
                    file_name=f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    except Exception as e:
        st.error(f"💥 匯入過程發生錯誤：{e}")
    
    results = {
        'success': 0,
        'failed': 0,
        'total_records': 0,
        'details': []
    }
    
    try:
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"處理檔案：{uploaded_file.name}")
            
            try:
                # 儲存暫存檔案
                with tempfile.NamedTemporaryFile(delete=False, suffix='.dbf') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                # 解析檔案
                with st.spinner(f"解析 {uploaded_file.name}..."):
                    result = dbf_parser.parse_auto(tmp_path)
                    
                    table_type = result['table_type']
                    df_data = pd.DataFrame(result['data'])
                    record_count = len(df_data)
                    
                    # 嚴格模式檢查
                    if strict_mode and not result['validation']['valid']:
                        raise Exception(f"資料驗證失敗：{result['validation']['errors']}")
                    
                    # 匯入資料庫
                    success = db_manager.import_dbf_data(
                        table_type, 
                        df_data, 
                        if_exists=import_mode
                    )
                    
                    if success:
                        results['success'] += 1
                        results['total_records'] += record_count
                        results['details'].append({
                            'file': uploaded_file.name,
                            'table': table_type,
                            'records': record_count,
                            'status': '成功'
                        })
                        st.success(f"✅ {uploaded_file.name} 匯入成功（{record_count:,} 筆）")
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'file': uploaded_file.name,
                            'table': table_type,
                            'records': 0,
                            'status': '失敗'
                        })
                        st.error(f"❌ {uploaded_file.name} 匯入失敗")
            
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'file': uploaded_file.name,
                    'table': 'N/A',
                    'records': 0,
                    'status': f'錯誤：{str(e)}'
                })
                st.error(f"❌ {uploaded_file.name} 處理失敗：{e}")
            
            finally:
                # 清理暫存檔案
                if 'tmp_path' in locals():
                    Path(tmp_path).unlink(missing_ok=True)
            
            # 更新進度
            progress = (i + 1) / len(uploaded_files)
            progress_bar.progress(progress)
        
        # 顯示匯入摘要
        status_text.text("匯入完成")
        
        st.subheader("📊 匯入摘要")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("成功檔案", results['success'])
        
        with col2:
            st.metric("失敗檔案", results['failed'])
        
        with col3:
            st.metric("總記錄數", f"{results['total_records']:,}")
        
        # 詳細結果
        if results['details']:
            st.write("**詳細結果：**")
            df_results = pd.DataFrame(results['details'])
            st.dataframe(df_results, use_container_width=True, hide_index=True)
        
        if results['success'] > 0:
            st.balloons()
    
    except Exception as e:
        st.error(f"匯入過程發生錯誤：{e}")


def render_data_browser(db_manager):
    """渲染資料瀏覽器"""
    st.header("🔍 資料瀏覽")
    
    try:
        # 選擇資料表
        db_stats = db_manager.get_table_stats()
        table_names = list(db_stats['tables'].keys())
        
        selected_table = st.selectbox(
            "選擇資料表：",
            options=table_names
        )
        
        if selected_table:
            # 查詢選項
            col1, col2, col3 = st.columns(3)
            
            with col1:
                limit = st.number_input("顯示筆數", min_value=10, max_value=1000, value=100)
            
            with col2:
                offset = st.number_input("跳過筆數", min_value=0, value=0)
            
            with col3:
                order_by = st.text_input("排序欄位", placeholder="例如: kcstmr")
            
            # 篩選條件
            with st.expander("🔧 進階篩選", expanded=False):
                filter_column = st.text_input("篩選欄位", placeholder="例如: mname")
                filter_operator = st.selectbox("運算子", options=["LIKE", "=", ">", "<", ">=", "<="])
                filter_value = st.text_input("篩選值", placeholder="例如: %李%")
            
            # 執行查詢
            if st.button("🔍 查詢資料"):
                try:
                    # 構建SQL
                    sql = f"SELECT * FROM {selected_table}"
                    
                    # 添加篩選條件
                    if filter_column and filter_value:
                        if filter_operator == "LIKE":
                            sql += f" WHERE {filter_column} LIKE '{filter_value}'"
                        else:
                            sql += f" WHERE {filter_column} {filter_operator} '{filter_value}'"
                    
                    # 添加排序
                    if order_by:
                        sql += f" ORDER BY {order_by}"
                    
                    # 添加限制
                    sql += f" LIMIT {limit} OFFSET {offset}"
                    
                    # 執行查詢
                    with st.spinner("查詢中..."):
                        df_result = db_manager.execute_query(sql)
                    
                    st.success(f"查詢完成，共 {len(df_result)} 筆結果")
                    
                    # 顯示結果
                    if len(df_result) > 0:
                        st.dataframe(df_result, use_container_width=True)
                        
                        # 下載按鈕
                        csv = df_result.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 下載CSV",
                            data=csv,
                            file_name=f"{selected_table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        # 基本統計
                        if st.checkbox("顯示統計資訊"):
                            render_data_statistics(df_result)
                    else:
                        st.info("沒有找到符合條件的資料")
                
                except Exception as e:
                    st.error(f"查詢失敗：{e}")
    
    except Exception as e:
        st.error(f"無法載入資料表列表：{e}")


def render_data_statistics(df):
    """渲染資料統計"""
    st.subheader("📈 資料統計")
    
    # 基本統計
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**基本資訊：**")
        st.write(f"- 總記錄數: {len(df)}")
        st.write(f"- 欄位數: {len(df.columns)}")
        st.write(f"- 缺失值: {df.isnull().sum().sum()}")
    
    with col2:
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            st.write("**數值欄位統計：**")
            selected_col = st.selectbox("選擇欄位：", options=numeric_cols)
            if selected_col:
                st.write(f"- 平均值: {df[selected_col].mean():.2f}")
                st.write(f"- 中位數: {df[selected_col].median():.2f}")
                st.write(f"- 標準差: {df[selected_col].std():.2f}")
    
    with col3:
        # 顯示欄位資訊
        st.write("**欄位資訊：**")
        dtypes_info = []
        for col in df.columns[:5]:  # 只顯示前5個欄位
            dtype = str(df[col].dtype)
            null_count = df[col].isnull().sum()
            dtypes_info.append(f"- {col}: {dtype} ({null_count} null)")
        
        for info in dtypes_info:
            st.write(info)
    
    # 如果有數值欄位，顯示分布圖
    if len(numeric_cols) > 0:
        st.write("**數值分布：**")
        chart_col = st.selectbox("選擇要視覺化的欄位：", options=numeric_cols)
        
        if chart_col:
            fig = px.histogram(
                df,
                x=chart_col,
                title=f"{chart_col} 分布圖"
            )
            st.plotly_chart(fig, use_container_width=True)


def render_data_export(db_manager):
    """渲染資料匯出"""
    st.header("📤 資料匯出")
    
    export_options = [
        ("table", "匯出整個資料表"),
        ("query", "匯出查詢結果"),
        ("backup", "完整資料庫備份")
    ]
    
    export_type = st.selectbox(
        "匯出類型：",
        options=export_options,
        format_func=lambda x: x[1]
    )
    
    if export_type[0] == "table":
        render_table_export(db_manager)
    elif export_type[0] == "query":
        render_query_export(db_manager)
    elif export_type[0] == "backup":
        render_backup_export(db_manager)


def render_table_export(db_manager):
    """渲染資料表匯出"""
    try:
        db_stats = db_manager.get_table_stats()
        table_names = list(db_stats['tables'].keys())
        
        selected_tables = st.multiselect(
            "選擇要匯出的資料表：",
            options=table_names,
            default=[]
        )
        
        if selected_tables:
            # 匯出格式
            export_format = st.selectbox(
                "匯出格式：",
                options=[
                    ("csv", "CSV"),
                    ("excel", "Excel"),
                    ("json", "JSON")
                ],
                format_func=lambda x: x[1]
            )
            
            # 匯出選項
            include_headers = st.checkbox("包含欄位名稱", value=True)
            
            if st.button("📥 匯出資料"):
                try:
                    with st.spinner("匯出中..."):
                        export_data = {}
                        
                        for table in selected_tables:
                            sql = f"SELECT * FROM {table}"
                            df = db_manager.execute_query(sql)
                            export_data[table] = df
                        
                        if export_format[0] == "csv":
                            # CSV匯出（打包成ZIP）
                            import zipfile
                            import io
                            
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for table, df in export_data.items():
                                    csv_data = df.to_csv(index=False, header=include_headers).encode('utf-8-sig')
                                    zip_file.writestr(f"{table}.csv", csv_data)
                            
                            st.download_button(
                                label="📥 下載ZIP檔案",
                                data=zip_buffer.getvalue(),
                                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                                mime="application/zip"
                            )
                        
                        elif export_format[0] == "excel":
                            # Excel匯出
                            import io
                            excel_buffer = io.BytesIO()
                            
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                for table, df in export_data.items():
                                    df.to_excel(writer, sheet_name=table, index=False, header=include_headers)
                            
                            st.download_button(
                                label="📥 下載Excel檔案",
                                data=excel_buffer.getvalue(),
                                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        elif export_format[0] == "json":
                            # JSON匯出
                            json_data = {}
                            for table, df in export_data.items():
                                json_data[table] = df.to_dict('records')
                            
                            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
                            
                            st.download_button(
                                label="📥 下載JSON檔案",
                                data=json_str.encode('utf-8'),
                                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )
                        
                        st.success("匯出完成！")
                
                except Exception as e:
                    st.error(f"匯出失敗：{e}")
    
    except Exception as e:
        st.error(f"無法載入資料表：{e}")


def render_query_export(db_manager):
    """渲染查詢結果匯出"""
    st.write("**自訂SQL查詢匯出：**")
    
    sql_query = st.text_area(
        "輸入SQL查詢：",
        placeholder="SELECT * FROM CO01M WHERE mname LIKE '%李%'",
        height=100
    )
    
    if sql_query.strip():
        if st.button("🔍 預覽查詢結果"):
            try:
                with st.spinner("執行查詢..."):
                    df_result = db_manager.execute_query(sql_query + " LIMIT 10")
                
                st.write(f"**預覽結果（前10筆）：**")
                st.dataframe(df_result, use_container_width=True)
                
                if st.button("📥 匯出完整結果"):
                    try:
                        df_full = db_manager.execute_query(sql_query)
                        csv = df_full.to_csv(index=False).encode('utf-8-sig')
                        
                        st.download_button(
                            label="📥 下載CSV檔案",
                            data=csv,
                            file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        st.success(f"查詢完成，共 {len(df_full)} 筆資料")
                    
                    except Exception as e:
                        st.error(f"匯出失敗：{e}")
            
            except Exception as e:
                st.error(f"查詢執行失敗：{e}")


def render_backup_export(db_manager):
    """渲染資料庫備份"""
    st.write("**完整資料庫備份：**")
    
    st.markdown("""
    <div class="warning-box">
        <strong>⚠️ 注意事項：</strong>
        <ul>
            <li>備份將包含所有資料表和結構</li>
            <li>備份檔案較大，請確保有足夠的儲存空間</li>
            <li>建議定期進行資料庫備份</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    backup_name = st.text_input(
        "備份檔案名稱：",
        value=f"clinic_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    if st.button("🗄️ 建立備份"):
        try:
            with st.spinner("建立備份中..."):
                import tempfile
                
                # 建立暫存備份檔案
                with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
                    backup_path = tmp_file.name
                
                # 執行備份
                success = db_manager.backup_database(backup_path)
                
                if success:
                    # 讀取備份檔案
                    with open(backup_path, 'rb') as f:
                        backup_data = f.read()
                    
                    st.download_button(
                        label="📥 下載備份檔案",
                        data=backup_data,
                        file_name=f"{backup_name}.db",
                        mime="application/octet-stream"
                    )
                    
                    st.success("✅ 備份建立成功！")
                    
                    # 顯示備份資訊
                    backup_size_mb = len(backup_data) / (1024 * 1024)
                    st.write(f"**備份大小：** {backup_size_mb:.2f} MB")
                else:
                    st.error("❌ 備份建立失敗")
                
                # 清理暫存檔案
                Path(backup_path).unlink(missing_ok=True)
        
        except Exception as e:
            st.error(f"備份過程發生錯誤：{e}")


def main():
    """主程式"""
    st.title("📋 資料管理")
    st.markdown("管理診所資料庫、匯入DBF檔案、匯出資料")
    
    # 初始化組件
    components = initialize_components()
    
    if components['status'] != 'success':
        st.error(f"系統初始化失敗: {components.get('error', '未知錯誤')}")
        return
    
    db_manager = components['db_manager']
    
    # 主要功能標籤
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗄️ 資料庫概覽",
        "📥 DBF匯入",
        "🔍 資料瀏覽",
        "📤 資料匯出"
    ])
    
    with tab1:
        render_database_overview(db_manager)
    
    with tab2:
        render_dbf_importer(components)
    
    with tab3:
        render_data_browser(db_manager)
    
    with tab4:
        render_data_export(db_manager)


if __name__ == "__main__":
    main()