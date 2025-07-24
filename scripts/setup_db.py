#!/usr/bin/env python3
"""
資料庫初始化腳本

用於建立SQLite資料庫結構、索引，並可選擇性地匯入DBF資料。

Usage:
    python scripts/setup_db.py --create-schema
    python scripts/setup_db.py --import-data /path/to/dbf/files/
    python scripts/setup_db.py --create-schema --import-data /path/to/dbf/files/

Author: Leon Lu
Created: 2025-01-24
"""

import argparse
import logging
import sys
from pathlib import Path
import os

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.db_manager import DatabaseManager, DatabaseError
from src.modules.dbf_parser import ZhanWangDBFParser, DBFParseError
from src.config import ConfigManager

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_database_schema(db_manager: DatabaseManager) -> bool:
    """
    建立資料庫結構和索引
    
    Args:
        db_manager: 資料庫管理器實例
        
    Returns:
        bool: 是否成功
    """
    try:
        logger.info("開始建立資料庫結構...")
        
        # 建立資料表
        db_manager.create_tables()
        logger.info("✅ 資料表建立完成")
        
        # 建立索引
        db_manager.create_indexes()
        logger.info("✅ 索引建立完成")
        
        # 初始化系統資訊
        db_manager.execute_query("""
            INSERT OR REPLACE INTO system_info (key, value) 
            VALUES ('schema_version', '1.0.0')
        """)
        
        db_manager.execute_query("""
            INSERT OR REPLACE INTO system_info (key, value) 
            VALUES ('created_at', datetime('now'))
        """)
        
        logger.info("✅ 系統資訊初始化完成")
        
        return True
        
    except DatabaseError as e:
        logger.error(f"❌ 建立資料庫結構失敗: {e}")
        return False


def import_dbf_data(db_manager: DatabaseManager, dbf_path: Path) -> bool:
    """
    匯入DBF資料到資料庫
    
    Args:
        db_manager: 資料庫管理器實例
        dbf_path: DBF檔案目錄路徑
        
    Returns:
        bool: 是否成功
    """
    try:
        logger.info(f"開始匯入DBF資料: {dbf_path}")
        
        if not dbf_path.exists():
            logger.error(f"❌ DBF目錄不存在: {dbf_path}")
            return False
        
        parser = ZhanWangDBFParser(encoding='big5', strict_mode=False)
        
        # 定義檔案對應關係
        file_mappings = {
            'CO01M.dbf': 'CO01M',
            'CO02M.dbf': 'CO02M', 
            'CO03M.dbf': 'CO03M',
            'CO18H.dbf': 'CO18H'
        }
        
        imported_count = 0
        
        for filename, table_name in file_mappings.items():
            file_path = dbf_path / filename
            
            if not file_path.exists():
                logger.warning(f"⚠️  檔案不存在，跳過: {filename}")
                continue
            
            try:
                logger.info(f"正在處理: {filename}")
                
                # 解析DBF檔案
                if table_name == 'CO01M':
                    df = parser.parse_co01m(file_path)
                elif table_name == 'CO02M':
                    df = parser.parse_co02m(file_path)
                elif table_name == 'CO03M':
                    df = parser.parse_co03m(file_path)
                elif table_name == 'CO18H':
                    df = parser.parse_co18h(file_path)
                
                # 匯入資料庫
                success = db_manager.import_dbf_data(table_name, df, if_exists='append')
                
                if success:
                    logger.info(f"✅ {filename} 匯入成功: {len(df)} 筆記錄")
                    imported_count += 1
                else:
                    logger.error(f"❌ {filename} 匯入失敗")
                
            except DBFParseError as e:
                logger.error(f"❌ 解析 {filename} 失敗: {e}")
            except Exception as e:
                logger.error(f"❌ 處理 {filename} 發生錯誤: {e}")
        
        logger.info(f"✅ DBF資料匯入完成，成功處理 {imported_count} 個檔案")
        
        # 更新統計資訊
        stats = db_manager.get_table_stats()
        logger.info("📊 資料表統計:")
        for table, info in stats['tables'].items():
            if 'record_count' in info:
                logger.info(f"  {table}: {info['record_count']} 筆記錄")
        
        return imported_count > 0
        
    except Exception as e:
        logger.error(f"❌ 匯入DBF資料失敗: {e}")
        return False


def verify_database(db_manager: DatabaseManager) -> bool:
    """
    驗證資料庫完整性
    
    Args:
        db_manager: 資料庫管理器實例
        
    Returns:
        bool: 是否驗證通過
    """
    try:
        logger.info("開始驗證資料庫...")
        
        # 檢查資料表是否存在
        tables = ['CO01M', 'CO02M', 'CO03M', 'CO18H', 'system_info', 'query_log']
        
        for table in tables:
            try:
                info = db_manager.get_table_info(table)
                logger.info(f"✅ {table}: {info['record_count']} 筆記錄")
            except DatabaseError:
                logger.error(f"❌ 資料表不存在: {table}")
                return False
        
        # 檢查索引
        test_queries = [
            "SELECT COUNT(*) FROM CO01M WHERE mname LIKE '%測試%'",
            "SELECT COUNT(*) FROM CO03M WHERE idate >= '2024-01-01'",
            "SELECT COUNT(*) FROM CO18H WHERE hitem = 'TEST'"
        ]
        
        for query in test_queries:
            try:
                result = db_manager.execute_query(query)
                logger.debug(f"測試查詢成功: {query}")
            except DatabaseError as e:
                logger.warning(f"測試查詢失敗: {query} - {e}")
        
        logger.info("✅ 資料庫驗證完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 資料庫驗證失敗: {e}")
        return False


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description="診所AI查詢系統資料庫初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  %(prog)s --create-schema                    # 只建立資料庫結構
  %(prog)s --import-data ./data/dbf_files/    # 只匯入資料
  %(prog)s --create-schema --import-data ./data/dbf_files/  # 建立結構並匯入資料
  %(prog)s --verify                           # 驗證資料庫
        """
    )
    
    parser.add_argument(
        '--create-schema',
        action='store_true',
        help='建立資料庫結構和索引'
    )
    
    parser.add_argument(
        '--import-data',
        type=str,
        metavar='DBF_PATH',
        help='匯入DBF檔案資料的目錄路徑'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        help='驗證資料庫完整性'
    )
    
    parser.add_argument(
        '--database',
        type=str,
        default='./data/anchia_lab.db',
        help='SQLite資料庫檔案路徑 (預設: ./data/anchia_lab.db)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='顯示詳細日誌'
    )
    
    args = parser.parse_args()
    
    # 設置日誌級別
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 檢查參數
    if not any([args.create_schema, args.import_data, args.verify]):
        parser.print_help()
        sys.exit(1)
    
    try:
        # 載入配置
        config_manager = ConfigManager()
        db_config = config_manager.get('database', {})
        
        # 建立資料庫管理器
        db_manager = DatabaseManager(args.database, db_config)
        
        success = True
        
        # 執行建立結構
        if args.create_schema:
            success &= setup_database_schema(db_manager)
        
        # 執行資料匯入
        if args.import_data:
            dbf_path = Path(args.import_data)
            success &= import_dbf_data(db_manager, dbf_path)
        
        # 執行驗證
        if args.verify:
            success &= verify_database(db_manager)
        
        # 關閉資料庫連線
        db_manager.close()
        
        if success:
            logger.info("🎉 資料庫初始化完成！")
            sys.exit(0)
        else:
            logger.error("💥 資料庫初始化失敗！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("用戶中斷操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()