"""
展望診療系統DBF檔案解析器

這個模組專門處理展望診療系統的DBF格式檔案，支援Big5編碼和
四個主要檔案格式：CO01M、CO02M、CO03M、CO18H。

Author: Leon Lu
Created: 2025-01-24
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import pandas as pd
import simpledbf
from datetime import datetime

# 設置日誌
logger = logging.getLogger(__name__)

# 展望系統資料庫結構定義
ANCHIA_LAB_SCHEMA = {
    'CO01M': {
        'description': '病患主資料表 - 儲存病患核心靜態資料',
        'primary_key': 'kcstmr',
        'encoding': 'big5',
        'fields': {
            'kcstmr': {'type': 'str', 'description': '病歷號 (七位數字，主鍵)', 'required': True},
            'mname': {'type': 'str', 'description': '病患姓名', 'required': False},
            'msex': {'type': 'str', 'description': '性別', 'required': False},
            'mbirthdt': {'type': 'str', 'description': '出生年月日', 'required': False},
            'mtelh': {'type': 'str', 'description': '電話/行動電話', 'required': False},
            'mfml': {'type': 'str', 'description': '住家電話', 'required': False},
            'mweight': {'type': 'str', 'description': '體重', 'required': False},
            'mheight': {'type': 'str', 'description': '身高', 'required': False},
            'mbegdt': {'type': 'str', 'description': '初診/建檔日期', 'required': False},
            'mtyp': {'type': 'str', 'description': '病患類型 (VIP, 自費)', 'required': False},
            'maddr': {'type': 'str', 'description': '地址', 'required': False},
            'mlcasedate': {'type': 'str', 'description': '最後就診日期', 'required': False},
            'mmsdt': {'type': 'str', 'description': '會員資格起始日', 'required': False},
            'mremark': {'type': 'str', 'description': '備註', 'required': False},
            'mmedi': {'type': 'str', 'description': '特殊註記', 'required': False},
            'mlcasedise': {'type': 'str', 'description': '最後就診主診斷', 'required': False},
            'mpersonid': {'type': 'str', 'description': '身分證字號/ID', 'required': False}
        }
    },
    'CO02M': {
        'description': '處方記錄檔 - 記錄病患用藥處方或治療項目',
        'primary_key': ['kcstmr', 'idate', 'itime', 'dno'],
        'encoding': 'big5',
        'fields': {
            'kcstmr': {'type': 'str', 'description': '病歷號', 'required': True},
            'idate': {'type': 'str', 'description': '開立日期', 'required': True},
            'itime': {'type': 'str', 'description': '開立時間', 'required': True},
            'ptp': {'type': 'str', 'description': '藥品類型', 'required': False},
            'dno': {'type': 'str', 'description': '藥品代碼/醫令代碼', 'required': True},
            'pfq': {'type': 'str', 'description': '使用頻率 (如：TID)', 'required': False},
            'ptday': {'type': 'str', 'description': '總天數', 'required': False}
        }
    },
    'CO03M': {
        'description': '就診摘要檔 - 記錄就診申請單摘要資訊，包含診斷與帳務資料',
        'primary_key': ['kcstmr', 'idate', 'itime'],
        'encoding': 'big5',
        'fields': {
            'kcstmr': {'type': 'str', 'description': '病歷號', 'required': True},
            'idate': {'type': 'str', 'description': '就醫日期', 'required': True},
            'itime': {'type': 'str', 'description': '就醫時間', 'required': True},
            'labno': {'type': 'str', 'description': '主診斷', 'required': False},
            'iuldt': {'type': 'str', 'description': '上傳日期', 'required': False},
            'lacd05': {'type': 'str', 'description': '次診斷05', 'required': False},
            'tot': {'type': 'str', 'description': '金額:申報金額', 'required': False},
            'sa98': {'type': 'str', 'description': '金額:部分負擔', 'required': False},
            'lacd03': {'type': 'str', 'description': '次診斷03', 'required': False},
            'lacd04': {'type': 'str', 'description': '次診斷04', 'required': False},
            'stot': {'type': 'str', 'description': '金額:申報金額', 'required': False},
            'ipk2': {'type': 'str', 'description': '檢驗套餐代碼 2', 'required': False},
            'ipk3': {'type': 'str', 'description': '醫師', 'required': False},
            'lacd02': {'type': 'str', 'description': '次診斷02', 'required': False},
            'a98': {'type': 'str', 'description': '金額:部分負擔', 'required': False},
            'lacd01': {'type': 'str', 'description': '次診斷01', 'required': False}
        }
    },
    'CO18H': {
        'description': '檢驗結果歷史檔 - 主要讀取檢驗數據以及生理數據',
        'primary_key': ['kcstmr', 'hdate', 'htime', 'hitem'],
        'encoding': 'big5',
        'fields': {
            'kcstmr': {'type': 'str', 'description': '病歷號', 'required': True},
            'hdate': {'type': 'str', 'description': '紀錄日期', 'required': True},
            'htime': {'type': 'str', 'description': '紀錄時間', 'required': True},
            'hitem': {'type': 'str', 'description': '檢驗項目代碼', 'required': True},
            'hdscp': {'type': 'str', 'description': '項目描述', 'required': False},
            'hval': {'type': 'str', 'description': '檢驗數值', 'required': False},
            'hinpdt': {'type': 'str', 'description': '輸入日期', 'required': False},
            'hsnddt': {'type': 'str', 'description': '報告發送日期', 'required': False},
            'hresult': {'type': 'str', 'description': '檢驗結果 (文字)', 'required': False},
            'hrule': {'type': 'str', 'description': '參考值範圍', 'required': False}
        }
    }
}


class DBFParseError(Exception):
    """DBF解析異常類別"""
    pass


class ZhanWangDBFParser:
    """
    展望診療系統DBF檔案解析器
    
    專門處理展望診療系統的四種主要DBF檔案格式，
    支援Big5編碼和資料完整性驗證。
    
    Attributes:
        encoding (str): 檔案編碼，預設為big5
        schema (dict): 資料庫結構定義
        strict_mode (bool): 是否啟用嚴格模式驗證
    """
    
    def __init__(self, encoding: str = 'big5', strict_mode: bool = True):
        """
        初始化解析器
        
        Args:
            encoding: DBF檔案編碼
            strict_mode: 是否啟用嚴格模式驗證
        """
        self.encoding = encoding
        self.schema = ANCHIA_LAB_SCHEMA
        self.strict_mode = strict_mode
        self.stats = {
            'parsed_files': 0,
            'total_records': 0,
            'errors': []
        }
        
        logger.info(f"DBF解析器已初始化 (編碼: {encoding}, 嚴格模式: {strict_mode})")
    
    def _validate_file_path(self, file_path: Union[str, Path]) -> Path:
        """
        驗證檔案路徑
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            Path: 驗證後的Path物件
            
        Raises:
            FileNotFoundError: 檔案不存在
            DBFParseError: 檔案格式錯誤
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"DBF檔案不存在: {path}")
        
        if path.suffix.lower() != '.dbf':
            raise DBFParseError(f"檔案格式錯誤，必須是DBF檔案: {path}")
        
        if path.stat().st_size == 0:
            raise DBFParseError(f"DBF檔案為空: {path}")
        
        return path
    
    def _detect_table_type(self, file_path: Path) -> str:
        """
        根據檔案名稱檢測資料表類型
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            str: 資料表類型 (CO01M, CO02M, CO03M, CO18H)
            
        Raises:
            DBFParseError: 無法識別的檔案類型
        """
        file_name = file_path.stem.upper()
        
        for table_name in self.schema.keys():
            if table_name in file_name:
                return table_name
        
        # 嘗試通過檔案內容推斷
        try:
            dbf = simpledbf.Dbf5(str(file_path), codec=self.encoding)
            columns = [col.lower() for col in dbf.columns]
            
            # 檢查特徵欄位
            if 'mname' in columns and 'mpersonid' in columns:
                return 'CO01M'
            elif 'dno' in columns and 'pfq' in columns:
                return 'CO02M'
            elif 'labno' in columns and 'tot' in columns:
                return 'CO03M'
            elif 'hitem' in columns and 'hval' in columns:
                return 'CO18H'
                
        except Exception as e:
            logger.warning(f"無法通過內容推斷檔案類型: {e}")
        
        raise DBFParseError(f"無法識別的DBF檔案類型: {file_path}")
    
    def _parse_dbf_file(self, file_path: Path, table_type: str) -> pd.DataFrame:
        """
        解析DBF檔案為DataFrame
        
        Args:
            file_path: DBF檔案路徑
            table_type: 資料表類型
            
        Returns:
            pd.DataFrame: 解析後的資料框
            
        Raises:
            DBFParseError: 解析失敗
        """
        try:
            logger.info(f"開始解析 {table_type} 檔案: {file_path}")
            
            # 使用simpledbf讀取DBF檔案
            dbf = simpledbf.Dbf5(str(file_path), codec=self.encoding)
            
            # 轉換為DataFrame
            df = dbf.to_dataframe()
            
            # 清理欄位名稱 (轉為小寫)
            df.columns = df.columns.str.lower()
            
            # 清理資料
            df = self._clean_data(df, table_type)
            
            logger.info(f"成功解析 {table_type}: {len(df)} 筆記錄")
            return df
            
        except UnicodeDecodeError as e:
            raise DBFParseError(f"編碼錯誤 (嘗試使用 {self.encoding}): {e}")
        except Exception as e:
            raise DBFParseError(f"解析DBF檔案失敗: {e}")
    
    def _clean_data(self, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        """
        清理和標準化資料
        
        Args:
            df: 原始DataFrame
            table_type: 資料表類型
            
        Returns:
            pd.DataFrame: 清理後的資料框
        """
        # 移除字串欄位的前後空白
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        
        # 處理空值
        df = df.replace('', None)
        df = df.replace('nan', None)
        
        # 日期欄位標準化
        date_columns = self._get_date_columns(table_type)
        for col in date_columns:
            if col in df.columns:
                df[col] = self._standardize_date(df[col])
        
        # 數值欄位處理
        numeric_columns = self._get_numeric_columns(table_type)
        for col in numeric_columns:
            if col in df.columns:
                df[col] = self._standardize_numeric(df[col])
        
        return df
    
    def _get_date_columns(self, table_type: str) -> List[str]:
        """取得日期類型欄位清單"""
        date_patterns = ['date', 'dt', 'time']
        schema = self.schema.get(table_type, {})
        fields = schema.get('fields', {})
        
        return [field_name for field_name in fields.keys() 
                if any(pattern in field_name.lower() for pattern in date_patterns)]
    
    def _get_numeric_columns(self, table_type: str) -> List[str]:
        """取得數值類型欄位清單"""
        numeric_patterns = ['tot', 'val', 'weight', 'height', 'day']
        schema = self.schema.get(table_type, {})
        fields = schema.get('fields', {})
        
        return [field_name for field_name in fields.keys() 
                if any(pattern in field_name.lower() for pattern in numeric_patterns)]
    
    def _standardize_date(self, series: pd.Series) -> pd.Series:
        """
        標準化日期格式
        
        Args:
            series: 日期欄位Series
            
        Returns:
            pd.Series: 標準化後的日期Series
        """
        def parse_date(date_str):
            if pd.isna(date_str) or str(date_str).strip() == '':
                return None
            
            date_str = str(date_str).strip()
            
            # 常見的展望日期格式
            formats = [
                '%Y%m%d',     # 20250124
                '%Y/%m/%d',   # 2025/01/24
                '%Y-%m-%d',   # 2025-01-24
                '%m/%d/%Y',   # 01/24/2025
                '%d/%m/%Y',   # 24/01/2025
            ]
            
            for fmt in formats:
                try:
                    return pd.to_datetime(date_str, format=fmt).strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    continue
            
            # 嘗試pandas的自動解析
            try:
                return pd.to_datetime(date_str).strftime('%Y-%m-%d')
            except:
                logger.warning(f"無法解析日期格式: {date_str}")
                return date_str
        
        return series.apply(parse_date)
    
    def _standardize_numeric(self, series: pd.Series) -> pd.Series:
        """
        標準化數值格式
        
        Args:
            series: 數值欄位Series
            
        Returns:
            pd.Series: 標準化後的數值Series
        """
        def parse_numeric(value):
            if pd.isna(value) or str(value).strip() == '':
                return None
            
            try:
                # 移除非數字字符 (保留小數點和負號)
                cleaned = str(value).strip()
                cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
                
                if cleaned == '' or cleaned == '.' or cleaned == '-':
                    return None
                
                return float(cleaned)
            except (ValueError, TypeError):
                logger.warning(f"無法解析數值格式: {value}")
                return value
        
        return series.apply(parse_numeric)
    
    def validate_data_integrity(self, df: pd.DataFrame, table_type: str) -> Dict[str, Any]:
        """
        驗證資料完整性
        
        Args:
            df: 要驗證的DataFrame
            table_type: 資料表類型
            
        Returns:
            dict: 驗證結果
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        schema = self.schema.get(table_type, {})
        fields = schema.get('fields', {})
        primary_key = schema.get('primary_key', [])
        
        # 檢查必填欄位
        for field_name, field_info in fields.items():
            if field_info.get('required', False) and field_name in df.columns:
                null_count = df[field_name].isnull().sum()
                if null_count > 0:
                    validation_result['warnings'].append(
                        f"必填欄位 {field_name} 有 {null_count} 筆空值"
                    )
        
        # 檢查主鍵唯一性
        if isinstance(primary_key, list):
            pk_columns = [col for col in primary_key if col in df.columns]
        else:
            pk_columns = [primary_key] if primary_key in df.columns else []
        
        if pk_columns:
            duplicate_count = df.duplicated(subset=pk_columns).sum()
            if duplicate_count > 0:
                validation_result['errors'].append(
                    f"主鍵重複: {duplicate_count} 筆記錄"
                )
                validation_result['valid'] = False
        
        # 統計資訊
        validation_result['statistics'] = {
            'total_records': len(df),
            'columns': len(df.columns),
            'null_values': df.isnull().sum().sum(),
            'duplicate_records': duplicate_count if pk_columns else 0
        }
        
        return validation_result
    
    def parse_co01m(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        解析CO01M病患主資料表
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            pd.DataFrame: 解析後的病患資料
        """
        path = self._validate_file_path(file_path)
        df = self._parse_dbf_file(path, 'CO01M')
        
        if self.strict_mode:
            validation = self.validate_data_integrity(df, 'CO01M')
            if not validation['valid']:
                raise DBFParseError(f"CO01M資料驗證失敗: {validation['errors']}")
        
        self.stats['parsed_files'] += 1
        self.stats['total_records'] += len(df)
        
        return df
    
    def parse_co02m(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        解析CO02M處方記錄檔
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            pd.DataFrame: 解析後的處方資料
        """
        path = self._validate_file_path(file_path)
        df = self._parse_dbf_file(path, 'CO02M')
        
        if self.strict_mode:
            validation = self.validate_data_integrity(df, 'CO02M')
            if not validation['valid']:
                raise DBFParseError(f"CO02M資料驗證失敗: {validation['errors']}")
        
        self.stats['parsed_files'] += 1
        self.stats['total_records'] += len(df)
        
        return df
    
    def parse_co03m(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        解析CO03M就診摘要檔
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            pd.DataFrame: 解析後的就診資料
        """
        path = self._validate_file_path(file_path)
        df = self._parse_dbf_file(path, 'CO03M')
        
        if self.strict_mode:
            validation = self.validate_data_integrity(df, 'CO03M')
            if not validation['valid']:
                raise DBFParseError(f"CO03M資料驗證失敗: {validation['errors']}")
        
        self.stats['parsed_files'] += 1
        self.stats['total_records'] += len(df)
        
        return df
    
    def parse_co18h(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        解析CO18H檢驗結果歷史檔
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            pd.DataFrame: 解析後的檢驗資料
        """
        path = self._validate_file_path(file_path)
        df = self._parse_dbf_file(path, 'CO18H')
        
        if self.strict_mode:
            validation = self.validate_data_integrity(df, 'CO18H')
            if not validation['valid']:
                raise DBFParseError(f"CO18H資料驗證失敗: {validation['errors']}")
        
        self.stats['parsed_files'] += 1
        self.stats['total_records'] += len(df)
        
        return df
    
    def parse_auto(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        自動識別並解析DBF檔案
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            dict: 包含解析結果和元資料的字典
        """
        path = self._validate_file_path(file_path)
        table_type = self._detect_table_type(path)
        
        # 根據類型調用對應的解析方法
        parse_methods = {
            'CO01M': self.parse_co01m,
            'CO02M': self.parse_co02m,
            'CO03M': self.parse_co03m,
            'CO18H': self.parse_co18h
        }
        
        df = parse_methods[table_type](path)
        validation = self.validate_data_integrity(df, table_type)
        
        return {
            'table_type': table_type,
            'data': df,
            'validation': validation,
            'metadata': {
                'file_path': str(path),
                'file_size': path.stat().st_size,
                'parse_time': datetime.now().isoformat(),
                'encoding': self.encoding,
                'record_count': len(df)
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        取得解析統計資訊
        
        Returns:
            dict: 統計資訊
        """
        return {
            'parsed_files': self.stats['parsed_files'],
            'total_records': self.stats['total_records'],
            'errors': self.stats['errors'],
            'schema_info': {
                table: info['description'] 
                for table, info in self.schema.items()
            }
        }
    
    def reset_statistics(self):
        """重置統計資訊"""
        self.stats = {
            'parsed_files': 0,
            'total_records': 0,
            'errors': []
        }