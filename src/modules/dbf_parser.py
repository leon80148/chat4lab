"""
展望診療系統DBF檔案解析器

這個模組專門處理展望診療系統的DBF格式檔案，支援Big5編碼和
四個主要檔案格式：CO01M、CO02M、CO03M、CO18H。

Author: Leon Lu
Created: 2025-01-24
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import pandas as pd
import simpledbf
import dbfread
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
        解析DBF檔案為DataFrame (支援多套件fallback)
        
        Args:
            file_path: DBF檔案路徑
            table_type: 資料表類型
            
        Returns:
            pd.DataFrame: 解析後的資料框
            
        Raises:
            DBFParseError: 解析失敗
        """
        logger.info(f"開始解析 {table_type} 檔案: {file_path}")
        
        # 嘗試多種DBF讀取方法
        methods = [
            ("dbfread", self._parse_with_dbfread),
            ("simpledbf", self._parse_with_simpledbf),
        ]
        
        last_error = None
        
        for method_name, method_func in methods:
            try:
                logger.debug(f"嘗試使用 {method_name} 解析 {table_type}")
                df = method_func(file_path)
                
                if df is not None and not df.empty:
                    # 清理欄位名稱 (轉為小寫)
                    df.columns = df.columns.str.lower()
                    
                    # 清理資料
                    df = self._clean_data(df, table_type)
                    
                    logger.info(f"成功使用 {method_name} 解析 {table_type}: {len(df)} 筆記錄")
                    return df
                    
            except Exception as e:
                logger.warning(f"{method_name} 解析失敗: {e}")
                last_error = e
                continue
        
        # 所有方法都失敗
        raise DBFParseError(f"所有DBF解析方法都失敗，最後錯誤: {last_error}")
    
    def _parse_with_dbfread(self, file_path: Path) -> pd.DataFrame:
        """使用dbfread套件解析DBF檔案"""
        try:
            # 嘗試不同的編碼策略
            encoding_strategies = [
                # 策略1: 使用Big5相關編碼直接讀取
                ('direct_chinese', [self.encoding, 'cp950', 'big5-hkscs']),
                # 策略2: 使用latin1讀取後重新編碼 (處理編碼問題的常見方法)
                ('latin1_recode', ['latin1']),
                # 策略3: 其他編碼嘗試
                ('fallback', ['utf-8', 'gb2312'])
            ]
            
            for strategy_name, encodings in encoding_strategies:
                logger.debug(f"嘗試策略: {strategy_name}")
                
                for encoding in encodings:
                    try:
                        logger.debug(f"  嘗試編碼: {encoding}")
                        
                        # 使用dbfread讀取
                        with dbfread.DBF(str(file_path), encoding=encoding, ignore_missing_memofile=True) as dbf:
                            # 轉換為字典列表
                            records = []
                            record_count = 0
                            
                            for record in dbf:
                                # dbfread在某些版本中record是OrderedDict，沒有deleted屬性
                                is_deleted = False
                                if hasattr(record, 'deleted'):
                                    is_deleted = record.deleted
                                
                                if not is_deleted:
                                    record_dict = dict(record)
                                    
                                    # 如果是latin1策略，嘗試重新編碼中文字段
                                    if strategy_name == 'latin1_recode':
                                        record_dict = self._recode_chinese_fields(record_dict)
                                    
                                    records.append(record_dict)
                                    record_count += 1
                                    
                                    # 限制讀取數量以避免記憶體問題
                                    if record_count >= 50000:  # 最多讀取5萬筆
                                        logger.warning(f"達到記錄數限制，停止讀取: {record_count}")
                                        break
                        
                        if records:
                            df = pd.DataFrame(records)
                            logger.debug(f"dbfread 成功讀取 {len(df)} 筆記錄，策略: {strategy_name}, 編碼: {encoding}")
                            return df
                            
                    except Exception as e:
                        logger.debug(f"  編碼 {encoding} 失敗: {e}")
                        continue
            
            raise Exception("所有編碼策略都失敗")
            
        except Exception as e:
            raise Exception(f"dbfread 解析失敗: {e}")
    
    def _recode_chinese_fields(self, record_dict: Dict[str, Any]) -> Dict[str, Any]:
        """重新編碼中文字段（從latin1到big5）"""
        try:
            # 定義可能包含中文的字段
            chinese_fields = ['mname', 'maddr', 'mremark', 'hdscp', 'hresult']
            
            for field_name, value in record_dict.items():
                if (field_name.lower() in chinese_fields and 
                    isinstance(value, str) and value.strip()):
                    try:
                        # 嘗試將latin1編碼的字符串重新編碼為big5
                        bytes_data = value.encode('latin1')
                        decoded_value = bytes_data.decode('big5', errors='ignore')
                        if decoded_value.strip():  # 如果解碼成功且非空
                            record_dict[field_name] = decoded_value
                    except (UnicodeError, UnicodeDecodeError, UnicodeEncodeError):
                        # 編碼轉換失敗，保持原值
                        pass
            
            return record_dict
            
        except Exception as e:
            logger.debug(f"重新編碼失敗: {e}")
            return record_dict
    
    def _parse_with_simpledbf(self, file_path: Path) -> pd.DataFrame:
        """使用simpledbf套件解析DBF檔案"""
        try:
            # 嘗試不同的編碼
            encodings = [self.encoding, 'cp950', 'big5-hkscs', 'utf-8', 'latin1']
            
            for encoding in encodings:
                try:
                    logger.debug(f"simpledbf 嘗試編碼: {encoding}")
                    
                    dbf = simpledbf.Dbf5(str(file_path), codec=encoding)
                    df = dbf.to_dataframe()
                    
                    if not df.empty:
                        logger.debug(f"simpledbf 成功讀取 {len(df)} 筆記錄，編碼: {encoding}")
                        return df
                        
                except Exception as e:
                    logger.debug(f"simpledbf 編碼 {encoding} 失敗: {e}")
                    continue
            
            raise Exception("所有編碼都失敗")
            
        except Exception as e:
            raise Exception(f"simpledbf 解析失敗: {e}")
    
    def _detect_dbf_format(self, file_path: Path) -> Dict[str, Any]:
        """
        檢測DBF檔案格式和版本
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            Dict: 檔案格式資訊
        """
        try:
            format_info = {
                'file_size': file_path.stat().st_size,
                'dbf_version': None,
                'encoding_detected': None,
                'record_count': None,
                'field_count': None
            }
            
            # 讀取DBF檔案頭部
            with open(file_path, 'rb') as f:
                header = f.read(32)
                
                if len(header) >= 32:
                    # DBF版本 (第一個位元組)
                    version_byte = header[0]
                    format_info['dbf_version'] = f"0x{version_byte:02X}"
                    
                    # 記錄數量 (位元組 4-7，小端序)
                    record_count = int.from_bytes(header[4:8], byteorder='little')
                    format_info['record_count'] = record_count
                    
                    # 頭部長度 (位元組 8-9)
                    header_length = int.from_bytes(header[8:10], byteorder='little')
                    
                    # 記錄長度 (位元組 10-11)
                    record_length = int.from_bytes(header[10:12], byteorder='little')
                    
                    # 估算欄位數
                    if header_length > 32:
                        field_count = (header_length - 32 - 1) // 32  # 每個欄位描述子32位元組
                        format_info['field_count'] = field_count
            
            logger.debug(f"DBF格式資訊: {format_info}")
            return format_info
            
        except Exception as e:
            logger.warning(f"DBF格式檢測失敗: {e}")
            return {'error': str(e)}
    
    def _detect_encoding(self, file_path: Path) -> str:
        """
        自動檢測DBF檔案編碼
        
        Args:
            file_path: DBF檔案路徑
            
        Returns:
            str: 最佳編碼
        """
        try:
            # 嘗試讀取一小部分資料來檢測編碼
            test_encodings = ['big5', 'cp950', 'big5-hkscs', 'gb2312', 'utf-8', 'latin1']
            best_encoding = self.encoding  # 預設編碼
            max_success_count = 0
            
            with open(file_path, 'rb') as f:
                # 跳過頭部，讀取一些記錄資料
                f.seek(32)
                sample_data = f.read(1024)  # 讀取1KB樣本
            
            for encoding in test_encodings:
                try:
                    decoded = sample_data.decode(encoding)
                    # 統計可顯示的中文字符數
                    chinese_chars = sum(1 for char in decoded if '\u4e00' <= char <= '\u9fff')
                    
                    if chinese_chars > max_success_count:
                        max_success_count = chinese_chars
                        best_encoding = encoding
                        
                except UnicodeDecodeError:
                    continue
            
            logger.debug(f"檢測到最佳編碼: {best_encoding} (中文字符數: {max_success_count})")
            return best_encoding
            
        except Exception as e:
            logger.warning(f"編碼檢測失敗，使用預設編碼 {self.encoding}: {e}")
            return self.encoding
    
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
        標準化日期格式（支援民國年格式）
        
        Args:
            series: 日期欄位Series
            
        Returns:
            pd.Series: 標準化後的日期Series
        """
        def parse_date(date_str):
            if pd.isna(date_str) or str(date_str).strip() == '':
                return None
            
            date_str = str(date_str).strip()
            
            # 檢查是否為民國年格式（7位數字：YYYMMDD）
            if re.match(r'^\d{7}$', date_str):
                try:
                    taiwan_year = int(date_str[:3])  # 前3位是民國年
                    month = int(date_str[3:5])       # 第4-5位是月
                    day = int(date_str[5:7])         # 第6-7位是日
                    
                    # 民國年轉西元年：民國年 + 1911
                    western_year = taiwan_year + 1911
                    
                    # 驗證日期有效性
                    if 1 <= month <= 12 and 1 <= day <= 31 and western_year >= 1912:
                        try:
                            # 使用datetime驗證日期
                            from datetime import datetime
                            datetime(western_year, month, day)
                            return f"{western_year:04d}-{month:02d}-{day:02d}"
                        except ValueError:
                            # 日期無效（如2月30日）
                            pass
                except (ValueError, IndexError):
                    pass
            
            # 常見的西元年日期格式
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
                logger.debug(f"無法解析日期格式: {date_str}")
                return date_str  # 保留原值而不是None
        
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