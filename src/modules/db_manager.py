"""
診所AI查詢系統資料庫管理器

負責SQLite資料庫的建立、管理和查詢操作，
包含資料匯入、索引優化、安全查詢等功能。

Author: Leon Lu
Created: 2025-01-24
"""

import logging
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
import pandas as pd
from datetime import datetime
import hashlib
import re

# 設置日誌
logger = logging.getLogger(__name__)

# SQL注入防護的危險關鍵字
DANGEROUS_SQL_KEYWORDS = [
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
    'EXEC', 'EXECUTE', 'UNION', 'SCRIPT', '--', '/*', '*/', ';--'
]

# 允許的SQL查詢關鍵字
ALLOWED_SQL_KEYWORDS = [
    'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER',
    'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'ON',
    'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL'
]


class DatabaseError(Exception):
    """資料庫操作異常類別"""
    pass


class DatabaseManager:
    """
    SQLite資料庫管理器
    
    提供完整的資料庫操作功能，包括建表、索引、查詢、
    資料匯入和安全性控制等。
    
    Attributes:
        db_path (str): 資料庫檔案路徑
        config (dict): 資料庫配置
        connection (sqlite3.Connection): 資料庫連線
    """
    
    def __init__(self, db_path: str, config: Optional[Dict] = None):
        """
        初始化資料庫管理器
        
        Args:
            db_path: SQLite資料庫檔案路徑
            config: 資料庫配置參數
        """
        self.db_path = Path(db_path)
        self.config = config or self._get_default_config()
        self.connection = None
        self._query_cache = {}
        self._cache_size = self.config.get('cache_size', 100)
        
        # 統計資訊
        self.stats = {
            'queries_executed': 0,
            'cache_hits': 0,
            'last_query_time': None,
            'total_query_time': 0
        }
        
        self._init_connection()
        logger.info(f"資料庫管理器已初始化: {self.db_path}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """取得預設資料庫配置"""
        return {
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
            'cache_size': 10000,      # 40MB快取
            'temp_store': 'MEMORY',
            'mmap_size': 268435456,   # 256MB記憶體映射
            'foreign_keys': True,
            'query_timeout': 30,      # 查詢逾時時間
            'max_results': 1000       # 最大查詢結果數
        }
    
    def _init_connection(self):
        """初始化資料庫連線"""
        try:
            # 確保資料庫目錄存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 建立連線
            self.connection = sqlite3.connect(
                str(self.db_path),
                timeout=self.config.get('query_timeout', 30),
                check_same_thread=False
            )
            
            # 設置Row Factory以支援欄位名稱存取
            self.connection.row_factory = sqlite3.Row
            
            # 套用效能優化設定
            self._apply_performance_settings()
            
            logger.info("資料庫連線已建立")
            
        except sqlite3.Error as e:
            raise DatabaseError(f"建立資料庫連線失敗: {e}")
    
    def _apply_performance_settings(self):
        """套用效能優化設定"""
        try:
            cursor = self.connection.cursor()
            
            # 設置WAL模式
            cursor.execute(f"PRAGMA journal_mode = {self.config['journal_mode']}")
            
            # 設置同步模式
            cursor.execute(f"PRAGMA synchronous = {self.config['synchronous']}")
            
            # 設置快取大小
            cursor.execute(f"PRAGMA cache_size = {self.config['cache_size']}")
            
            # 設置暫存儲存方式
            cursor.execute(f"PRAGMA temp_store = {self.config['temp_store']}")
            
            # 設置記憶體映射大小
            cursor.execute(f"PRAGMA mmap_size = {self.config['mmap_size']}")
            
            # 啟用外鍵約束
            if self.config['foreign_keys']:
                cursor.execute("PRAGMA foreign_keys = ON")
            
            cursor.close()
            logger.info("資料庫效能設定已套用")
            
        except sqlite3.Error as e:
            logger.warning(f"套用效能設定失敗: {e}")
    
    def create_tables(self) -> None:
        """
        建立所有資料表結構
        
        根據展望系統的四個主要檔案建立對應的資料表
        """
        try:
            cursor = self.connection.cursor()
            
            # CO01M 病患主資料表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CO01M (
                    kcstmr TEXT PRIMARY KEY,              -- 病歷號
                    mname TEXT,                           -- 病患姓名
                    msex TEXT,                            -- 性別
                    mbirthdt TEXT,                        -- 出生年月日
                    mtelh TEXT,                           -- 電話/行動電話
                    mfml TEXT,                            -- 住家電話
                    mweight REAL,                         -- 體重
                    mheight REAL,                         -- 身高
                    mbegdt TEXT,                          -- 初診/建檔日期
                    mtyp TEXT,                            -- 病患類型
                    maddr TEXT,                           -- 地址
                    mlcasedate TEXT,                      -- 最後就診日期
                    mmsdt TEXT,                           -- 會員資格起始日
                    mremark TEXT,                         -- 備註
                    mmedi TEXT,                           -- 特殊註記
                    mlcasedise TEXT,                      -- 最後就診主診斷
                    mpersonid TEXT,                       -- 身分證字號
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # CO02M 處方記錄檔
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CO02M (
                    kcstmr TEXT NOT NULL,                 -- 病歷號
                    idate TEXT NOT NULL,                  -- 開立日期
                    itime TEXT NOT NULL,                  -- 開立時間
                    dno TEXT NOT NULL,                    -- 藥品代碼/醫令代碼
                    ptp TEXT,                             -- 藥品類型
                    pfq TEXT,                             -- 使用頻率
                    ptday INTEGER,                        -- 總天數
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kcstmr, idate, itime, dno),
                    FOREIGN KEY (kcstmr) REFERENCES CO01M(kcstmr)
                )
            """)
            
            # CO03M 就診摘要檔
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CO03M (
                    kcstmr TEXT NOT NULL,                 -- 病歷號
                    idate TEXT NOT NULL,                  -- 就醫日期
                    itime TEXT NOT NULL,                  -- 就醫時間
                    labno TEXT,                           -- 主診斷
                    iuldt TEXT,                           -- 上傳日期
                    lacd01 TEXT,                          -- 次診斷01
                    lacd02 TEXT,                          -- 次診斷02
                    lacd03 TEXT,                          -- 次診斷03
                    lacd04 TEXT,                          -- 次診斷04
                    lacd05 TEXT,                          -- 次診斷05
                    tot REAL,                             -- 申報金額
                    sa98 REAL,                            -- 部分負擔
                    stot REAL,                            -- 申報金額
                    a98 REAL,                             -- 部分負擔
                    ipk2 TEXT,                            -- 檢驗套餐代碼2
                    ipk3 TEXT,                            -- 醫師
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kcstmr, idate, itime),
                    FOREIGN KEY (kcstmr) REFERENCES CO01M(kcstmr)
                )
            """)
            
            # CO18H 檢驗結果歷史檔
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CO18H (
                    kcstmr TEXT NOT NULL,                 -- 病歷號
                    hdate TEXT NOT NULL,                  -- 紀錄日期
                    htime TEXT NOT NULL,                  -- 紀錄時間
                    hitem TEXT NOT NULL,                  -- 檢驗項目代碼
                    hdscp TEXT,                           -- 項目描述
                    hval REAL,                            -- 檢驗數值
                    hinpdt TEXT,                          -- 輸入日期
                    hsnddt TEXT,                          -- 報告發送日期
                    hresult TEXT,                         -- 檢驗結果(文字)
                    hrule TEXT,                           -- 參考值範圍
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kcstmr, hdate, htime, hitem),
                    FOREIGN KEY (kcstmr) REFERENCES CO01M(kcstmr)
                )
            """)
            
            # 建立系統資訊表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_info (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 建立查詢日誌表 (審計追蹤)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    query_hash TEXT,
                    query_text TEXT,
                    result_count INTEGER,
                    execution_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
            cursor.close()
            
            logger.info("所有資料表建立完成")
            
        except sqlite3.Error as e:
            raise DatabaseError(f"建立資料表失敗: {e}")
    
    def create_indexes(self) -> None:
        """
        建立查詢索引以提升效能
        """
        try:
            cursor = self.connection.cursor()
            
            # CO01M 索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_co01m_name ON CO01M(mname)",
                "CREATE INDEX IF NOT EXISTS idx_co01m_birthdt ON CO01M(mbirthdt)",
                "CREATE INDEX IF NOT EXISTS idx_co01m_lastcase ON CO01M(mlcasedate)",
                "CREATE INDEX IF NOT EXISTS idx_co01m_personid ON CO01M(mpersonid)",
                
                # CO02M 索引
                "CREATE INDEX IF NOT EXISTS idx_co02m_patient_date ON CO02M(kcstmr, idate)",
                "CREATE INDEX IF NOT EXISTS idx_co02m_drug ON CO02M(dno)",
                "CREATE INDEX IF NOT EXISTS idx_co02m_date ON CO02M(idate)",
                
                # CO03M 索引
                "CREATE INDEX IF NOT EXISTS idx_co03m_patient_date ON CO03M(kcstmr, idate)",
                "CREATE INDEX IF NOT EXISTS idx_co03m_diagnosis ON CO03M(labno)",
                "CREATE INDEX IF NOT EXISTS idx_co03m_doctor ON CO03M(ipk3)",
                "CREATE INDEX IF NOT EXISTS idx_co03m_date ON CO03M(idate)",
                
                # CO18H 索引
                "CREATE INDEX IF NOT EXISTS idx_co18h_patient_date ON CO18H(kcstmr, hdate)",
                "CREATE INDEX IF NOT EXISTS idx_co18h_item ON CO18H(hitem)",
                "CREATE INDEX IF NOT EXISTS idx_co18h_desc ON CO18H(hdscp)",
                "CREATE INDEX IF NOT EXISTS idx_co18h_date ON CO18H(hdate)",
                
                # 查詢日誌索引
                "CREATE INDEX IF NOT EXISTS idx_query_log_date ON query_log(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_query_log_user ON query_log(user_id)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            self.connection.commit()
            cursor.close()
            
            logger.info("所有索引建立完成")
            
        except sqlite3.Error as e:
            raise DatabaseError(f"建立索引失敗: {e}")
    
    def import_dbf_data(self, table_name: str, df: pd.DataFrame, 
                       if_exists: str = 'append') -> bool:
        """
        匯入DBF資料到資料庫
        
        Args:
            table_name: 目標資料表名稱
            df: 要匯入的DataFrame
            if_exists: 如果表已存在的處理方式 ('append', 'replace', 'fail')
            
        Returns:
            bool: 是否匯入成功
        """
        try:
            # 資料預處理
            df_clean = df.copy()
            
            # 處理無窮大和NaN值
            df_clean = df_clean.replace([float('inf'), float('-inf')], None)
            df_clean = df_clean.where(pd.notnull(df_clean), None)
            
            # 匯入資料
            df_clean.to_sql(
                table_name, 
                self.connection, 
                if_exists=if_exists,
                index=False,
                method='multi'
            )
            
            logger.info(f"成功匯入 {len(df_clean)} 筆記錄到 {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"匯入資料失敗: {e}")
            return False
    
    def _validate_sql_query(self, sql: str) -> Tuple[bool, str]:
        """
        驗證SQL查詢的安全性
        
        Args:
            sql: 要驗證的SQL查詢
            
        Returns:
            tuple: (是否安全, 錯誤訊息)
        """
        sql_upper = sql.upper().strip()
        
        # 檢查危險關鍵字
        for keyword in DANGEROUS_SQL_KEYWORDS:
            if keyword in sql_upper:
                return False, f"禁止使用關鍵字: {keyword}"
        
        # 檢查是否以SELECT開始
        if not sql_upper.startswith('SELECT'):
            return False, "只允許SELECT查詢"
        
        # 檢查分號數量 (防止多重查詢)
        if sql.count(';') > 1:
            return False, "不允許多重查詢"
        
        # 檢查註釋符號
        if '--' in sql or '/*' in sql:
            return False, "不允許SQL註釋"
        
        return True, ""
    
    def _generate_query_hash(self, sql: str) -> str:
        """生成查詢雜湊值用於快取"""
        return hashlib.md5(sql.encode()).hexdigest()
    
    def _log_query(self, user_id: str, sql: str, result_count: int, 
                   execution_time: float):
        """記錄查詢日誌"""
        try:
            cursor = self.connection.cursor()
            query_hash = self._generate_query_hash(sql)
            
            cursor.execute("""
                INSERT INTO query_log 
                (user_id, query_hash, query_text, result_count, execution_time)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, query_hash, sql, result_count, execution_time))
            
            self.connection.commit()
            cursor.close()
            
        except sqlite3.Error as e:
            logger.warning(f"記錄查詢日誌失敗: {e}")
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None,
                     user_id: str = "system") -> pd.DataFrame:
        """
        安全執行SQL查詢
        
        Args:
            sql: SQL查詢語句
            params: 查詢參數
            user_id: 使用者ID (用於審計)
            
        Returns:
            pd.DataFrame: 查詢結果
            
        Raises:
            DatabaseError: 查詢執行失敗
        """
        start_time = datetime.now()
        
        try:
            # 驗證SQL安全性
            is_safe, error_msg = self._validate_sql_query(sql)
            if not is_safe:
                raise DatabaseError(f"SQL查詢不安全: {error_msg}")
            
            # 檢查快取
            query_hash = self._generate_query_hash(sql + str(params or ''))
            if query_hash in self._query_cache:
                self.stats['cache_hits'] += 1
                logger.debug("使用快取結果")
                return self._query_cache[query_hash].copy()
            
            # 執行查詢
            if params:
                df = pd.read_sql_query(sql, self.connection, params=params)
            else:
                df = pd.read_sql_query(sql, self.connection)
            
            # 限制結果數量
            max_results = self.config.get('max_results', 1000)
            if len(df) > max_results:
                df = df.head(max_results)
                logger.warning(f"查詢結果已限制為 {max_results} 筆")
            
            # 更新快取
            if len(self._query_cache) < self._cache_size:
                self._query_cache[query_hash] = df.copy()
            
            # 計算執行時間
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 記錄統計和日誌
            self.stats['queries_executed'] += 1
            self.stats['last_query_time'] = execution_time
            self.stats['total_query_time'] += execution_time
            
            self._log_query(user_id, sql, len(df), execution_time)
            
            logger.info(f"查詢執行完成: {len(df)} 筆結果, 耗時 {execution_time:.3f}秒")
            
            return df
            
        except sqlite3.Error as e:
            raise DatabaseError(f"SQL查詢執行失敗: {e}")
        except Exception as e:
            raise DatabaseError(f"查詢處理失敗: {e}")
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        取得資料表資訊
        
        Args:
            table_name: 資料表名稱
            
        Returns:
            dict: 資料表資訊
        """
        try:
            cursor = self.connection.cursor()
            
            # 取得表結構
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 取得記錄數
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            record_count = cursor.fetchone()[0]
            
            # 取得索引資訊
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            
            cursor.close()
            
            return {
                'table_name': table_name,
                'columns': [dict(col) for col in columns],
                'record_count': record_count,
                'indexes': [dict(idx) for idx in indexes]
            }
            
        except sqlite3.Error as e:
            raise DatabaseError(f"取得表資訊失敗: {e}")
    
    def get_table_stats(self) -> Dict[str, Any]:
        """
        取得所有資料表統計資訊
        
        Returns:
            dict: 統計資訊
        """
        tables = ['CO01M', 'CO02M', 'CO03M', 'CO18H']
        stats = {}
        
        for table in tables:
            try:
                info = self.get_table_info(table)
                stats[table] = {
                    'record_count': info['record_count'],
                    'column_count': len(info['columns']),
                    'index_count': len(info['indexes'])
                }
            except DatabaseError:
                stats[table] = {'error': '表不存在或無法存取'}
        
        return {
            'tables': stats,
            'database_size': self._get_database_size(),
            'query_stats': self.stats.copy()
        }
    
    def _get_database_size(self) -> int:
        """取得資料庫檔案大小"""
        try:
            return self.db_path.stat().st_size if self.db_path.exists() else 0
        except:
            return 0
    
    def backup_database(self, backup_path: str) -> bool:
        """
        備份資料庫
        
        Args:
            backup_path: 備份檔案路徑
            
        Returns:
            bool: 是否備份成功
        """
        try:
            backup_conn = sqlite3.connect(backup_path)
            self.connection.backup(backup_conn)
            backup_conn.close()
            
            logger.info(f"資料庫備份完成: {backup_path}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"資料庫備份失敗: {e}")
            return False
    
    def clear_cache(self):
        """清除查詢快取"""
        self._query_cache.clear()
        logger.info("查詢快取已清除")
    
    def close(self):
        """關閉資料庫連線"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("資料庫連線已關閉")
    
    def __enter__(self):
        """Context manager進入"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager退出"""
        self.close()
    
    def __del__(self):
        """析構函數"""
        self.close()