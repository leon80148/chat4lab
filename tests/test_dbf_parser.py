"""
DBF解析器測試

測試展望診療系統DBF檔案解析器的各種功能。

Author: Leon Lu
Created: 2025-01-24
"""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.modules.dbf_parser import (
    ZhanWangDBFParser, 
    DBFParseError, 
    ANCHIA_LAB_SCHEMA
)


class TestZhanWangDBFParser:
    """DBF解析器測試類"""
    
    @pytest.fixture
    def parser(self):
        """建立解析器實例"""
        return ZhanWangDBFParser(encoding='big5', strict_mode=True)
    
    @pytest.fixture
    def sample_co01m_data(self):
        """CO01M測試資料"""
        return pd.DataFrame({
            'kcstmr': ['0000001', '0000002', '0000003'],
            'mname': ['測試病患一', '測試病患二', '測試病患三'],
            'msex': ['M', 'F', 'M'],
            'mbirthdt': ['19800101', '19900215', '19750520'],
            'mtelh': ['0912345678', '0987654321', ''],
            'mweight': ['70.5', '55.2', '80.0'],
            'mheight': ['175', '160', '180'],
            'mpersonid': ['A123456789', 'B987654321', 'C555666777']
        })
    
    @pytest.fixture  
    def sample_co02m_data(self):
        """CO02M測試資料"""
        return pd.DataFrame({
            'kcstmr': ['0000001', '0000001', '0000002'],
            'idate': ['20250124', '20250124', '20250123'],
            'itime': ['0900', '0900', '1030'],
            'dno': ['DRUG001', 'DRUG002', 'DRUG001'],
            'ptp': ['口服藥', '注射劑', '口服藥'],
            'pfq': ['TID', 'BID', 'QID'],
            'ptday': ['7', '3', '5']
        })
    
    @pytest.fixture
    def mock_dbf_file(self, tmp_path):
        """建立模擬DBF檔案"""
        dbf_file = tmp_path / "test_CO01M.dbf"
        dbf_file.write_bytes(b"mock dbf content")
        return dbf_file
    
    def test_parser_initialization(self):
        """測試解析器初始化"""
        # 使用預設參數
        parser1 = ZhanWangDBFParser()
        assert parser1.encoding == 'big5'
        assert parser1.strict_mode == True
        assert parser1.schema == ANCHIA_LAB_SCHEMA
        
        # 使用自訂參數
        parser2 = ZhanWangDBFParser(encoding='utf-8', strict_mode=False)
        assert parser2.encoding == 'utf-8'
        assert parser2.strict_mode == False
    
    def test_validate_file_path_success(self, parser, mock_dbf_file):
        """測試檔案路徑驗證成功"""
        result = parser._validate_file_path(mock_dbf_file)
        assert isinstance(result, Path)
        assert result.suffix.lower() == '.dbf'
    
    def test_validate_file_path_not_exists(self, parser):
        """測試檔案不存在"""
        with pytest.raises(FileNotFoundError):
            parser._validate_file_path("nonexistent.dbf")
    
    def test_validate_file_path_wrong_extension(self, parser, tmp_path):
        """測試錯誤的檔案副檔名"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test")
        
        with pytest.raises(DBFParseError, match="檔案格式錯誤"):
            parser._validate_file_path(txt_file)
    
    def test_validate_file_path_empty_file(self, parser, tmp_path):
        """測試空檔案"""
        empty_file = tmp_path / "empty.dbf"
        empty_file.touch()
        
        with pytest.raises(DBFParseError, match="DBF檔案為空"):
            parser._validate_file_path(empty_file)
    
    def test_detect_table_type_by_filename(self, parser, tmp_path):
        """測試通過檔案名檢測表類型"""
        test_cases = [
            ("CO01M.dbf", "CO01M"),
            ("co01m_backup.dbf", "CO01M"),
            ("DATA_CO02M_20250124.dbf", "CO02M"),
            ("co03m.dbf", "CO03M"),
            ("CO18H_export.dbf", "CO18H")
        ]
        
        for filename, expected_type in test_cases:
            dbf_file = tmp_path / filename
            dbf_file.write_bytes(b"mock content")
            
            result = parser._detect_table_type(dbf_file)
            assert result == expected_type
    
    def test_detect_table_type_unknown_file(self, parser, tmp_path):
        """測試無法識別的檔案類型"""
        unknown_file = tmp_path / "unknown.dbf"
        unknown_file.write_bytes(b"mock content")
        
        with patch('simpledbf.Dbf5') as mock_dbf:
            mock_dbf.side_effect = Exception("Cannot parse")
            
            with pytest.raises(DBFParseError, match="無法識別的DBF檔案類型"):
                parser._detect_table_type(unknown_file)
    
    @patch('simpledbf.Dbf5')
    def test_parse_dbf_file_success(self, mock_dbf_class, parser, mock_dbf_file, sample_co01m_data):
        """測試成功解析DBF檔案"""
        # 設置mock
        mock_dbf_instance = Mock()
        mock_dbf_instance.to_dataframe.return_value = sample_co01m_data
        mock_dbf_class.return_value = mock_dbf_instance
        
        # 執行解析
        result = parser._parse_dbf_file(mock_dbf_file, 'CO01M')
        
        # 驗證結果
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert 'kcstmr' in result.columns
        
        # 驗證mock調用
        mock_dbf_class.assert_called_once_with(str(mock_dbf_file), codec='big5')
        mock_dbf_instance.to_dataframe.assert_called_once()
    
    @patch('simpledbf.Dbf5')
    def test_parse_dbf_file_encoding_error(self, mock_dbf_class, parser, mock_dbf_file):
        """測試編碼錯誤"""
        mock_dbf_class.side_effect = UnicodeDecodeError('big5', b'', 0, 1, 'error')
        
        with pytest.raises(DBFParseError, match="編碼錯誤"):
            parser._parse_dbf_file(mock_dbf_file, 'CO01M')
    
    def test_clean_data(self, parser, sample_co01m_data):
        """測試資料清理"""
        # 添加需要清理的資料
        dirty_data = sample_co01m_data.copy()
        dirty_data.loc[0, 'mname'] = '  測試病患一  '  # 前後空白
        dirty_data.loc[1, 'mtelh'] = ''  # 空字串
        dirty_data.loc[2, 'mweight'] = 'nan'  # nan字串
        
        result = parser._clean_data(dirty_data, 'CO01M')
        
        # 驗證清理結果
        assert result.loc[0, 'mname'] == '測試病患一'  # 空白已移除
        assert pd.isna(result.loc[1, 'mtelh'])  # 空字串轉為None
        assert pd.isna(result.loc[2, 'mweight'])  # nan字串轉為None
    
    def test_standardize_date(self, parser):
        """測試日期標準化"""
        date_series = pd.Series([
            '20250124',      # YYYYMMDD
            '2025/01/24',    # YYYY/MM/DD
            '2025-01-24',    # YYYY-MM-DD
            '01/24/2025',    # MM/DD/YYYY
            '',              # 空字串
            None,            # None值
            'invalid_date'   # 無效日期
        ])
        
        result = parser._standardize_date(date_series)
        
        # 驗證結果
        assert result[0] == '2025-01-24'
        assert result[1] == '2025-01-24'
        assert result[2] == '2025-01-24'
        assert pd.isna(result[4])  # 空字串
        assert pd.isna(result[5])  # None值
        assert result[6] == 'invalid_date'  # 無效日期保持原樣
    
    def test_standardize_numeric(self, parser):
        """測試數值標準化"""
        numeric_series = pd.Series([
            '70.5',    # 正常數值
            '80',      # 整數
            '-1.5',    # 負數
            '',        # 空字串
            None,      # None值
            'abc',     # 非數值
            '.'        # 只有小數點
        ])
        
        result = parser._standardize_numeric(numeric_series)
        
        # 驗證結果
        assert result[0] == 70.5
        assert result[1] == 80.0
        assert result[2] == -1.5
        assert pd.isna(result[3])  # 空字串
        assert pd.isna(result[4])  # None值
        assert result[5] == 'abc'  # 非數值保持原樣
        assert pd.isna(result[6])  # 只有小數點
    
    def test_validate_data_integrity_success(self, parser, sample_co01m_data):
        """測試資料完整性驗證成功"""
        result = parser.validate_data_integrity(sample_co01m_data, 'CO01M')
        
        assert result['valid'] == True
        assert isinstance(result['errors'], list)
        assert isinstance(result['warnings'], list)
        assert isinstance(result['statistics'], dict)
        assert result['statistics']['total_records'] == 3
    
    def test_validate_data_integrity_duplicate_keys(self, parser):
        """測試主鍵重複驗證"""
        duplicate_data = pd.DataFrame({
            'kcstmr': ['0000001', '0000001', '0000002'],  # 重複主鍵
            'mname': ['病患一', '病患一重複', '病患二']
        })
        
        result = parser.validate_data_integrity(duplicate_data, 'CO01M')
        
        assert result['valid'] == False
        assert any('主鍵重複' in error for error in result['errors'])
    
    @patch.object(ZhanWangDBFParser, '_parse_dbf_file')
    @patch.object(ZhanWangDBFParser, '_validate_file_path')
    def test_parse_co01m_success(self, mock_validate, mock_parse, parser, mock_dbf_file, sample_co01m_data):
        """測試CO01M解析成功"""
        mock_validate.return_value = mock_dbf_file
        mock_parse.return_value = sample_co01m_data
        
        result = parser.parse_co01m(mock_dbf_file)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert parser.stats['parsed_files'] == 1
        assert parser.stats['total_records'] == 3
    
    @patch.object(ZhanWangDBFParser, '_parse_dbf_file')
    @patch.object(ZhanWangDBFParser, '_validate_file_path')
    def test_parse_co02m_success(self, mock_validate, mock_parse, parser, mock_dbf_file, sample_co02m_data):
        """測試CO02M解析成功"""
        mock_validate.return_value = mock_dbf_file
        mock_parse.return_value = sample_co02m_data
        
        result = parser.parse_co02m(mock_dbf_file)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert parser.stats['parsed_files'] == 1
        assert parser.stats['total_records'] == 3
    
    @patch.object(ZhanWangDBFParser, 'validate_data_integrity')
    @patch.object(ZhanWangDBFParser, '_parse_dbf_file')
    @patch.object(ZhanWangDBFParser, '_validate_file_path')
    def test_strict_mode_validation_failure(self, mock_validate_path, mock_parse, mock_validate_integrity, parser, mock_dbf_file, sample_co01m_data):
        """測試嚴格模式下驗證失敗"""
        mock_validate_path.return_value = mock_dbf_file
        mock_parse.return_value = sample_co01m_data
        mock_validate_integrity.return_value = {
            'valid': False,
            'errors': ['測試錯誤']
        }
        
        with pytest.raises(DBFParseError, match="CO01M資料驗證失敗"):
            parser.parse_co01m(mock_dbf_file)
    
    @patch.object(ZhanWangDBFParser, '_detect_table_type')
    @patch.object(ZhanWangDBFParser, 'parse_co01m')
    @patch.object(ZhanWangDBFParser, '_validate_file_path')
    def test_parse_auto_success(self, mock_validate, mock_parse_co01m, mock_detect, parser, mock_dbf_file, sample_co01m_data):
        """測試自動解析成功"""
        mock_validate.return_value = mock_dbf_file
        mock_detect.return_value = 'CO01M'
        mock_parse_co01m.return_value = sample_co01m_data
        
        result = parser.parse_auto(mock_dbf_file)
        
        assert result['table_type'] == 'CO01M'
        assert isinstance(result['data'], pd.DataFrame)
        assert 'validation' in result
        assert 'metadata' in result
        assert result['metadata']['record_count'] == 3
    
    def test_get_statistics(self, parser):
        """測試取得統計資訊"""
        # 手動設置統計資料
        parser.stats['parsed_files'] = 2
        parser.stats['total_records'] = 150
        parser.stats['errors'] = ['測試錯誤']
        
        result = parser.get_statistics()
        
        assert result['parsed_files'] == 2
        assert result['total_records'] == 150
        assert result['errors'] == ['測試錯誤']
        assert 'schema_info' in result
        assert len(result['schema_info']) == 4  # 四個表
    
    def test_reset_statistics(self, parser):
        """測試重置統計資訊"""  
        # 設置初始統計
        parser.stats['parsed_files'] = 5
        parser.stats['total_records'] = 1000
        parser.stats['errors'] = ['錯誤1', '錯誤2']
        
        # 重置統計
        parser.reset_statistics()
        
        assert parser.stats['parsed_files'] == 0
        assert parser.stats['total_records'] == 0
        assert parser.stats['errors'] == []
    
    def test_get_date_columns(self, parser):
        """測試取得日期欄位"""
        date_columns = parser._get_date_columns('CO01M')
        expected_columns = ['mbirthdt', 'mbegdt', 'mlcasedate', 'mmsdt']
        
        for col in expected_columns:
            assert col in date_columns
    
    def test_get_numeric_columns(self, parser):
        """測試取得數值欄位"""
        numeric_columns = parser._get_numeric_columns('CO01M')
        expected_columns = ['mweight', 'mheight']
        
        for col in expected_columns:
            assert col in numeric_columns
    
    def test_schema_constants(self):
        """測試結構定義常數"""
        assert 'CO01M' in ANCHIA_LAB_SCHEMA
        assert 'CO02M' in ANCHIA_LAB_SCHEMA
        assert 'CO03M' in ANCHIA_LAB_SCHEMA
        assert 'CO18H' in ANCHIA_LAB_SCHEMA
        
        # 檢查CO01M結構
        co01m_schema = ANCHIA_LAB_SCHEMA['CO01M']
        assert co01m_schema['primary_key'] == 'kcstmr'
        assert co01m_schema['encoding'] == 'big5'
        assert 'fields' in co01m_schema
        assert 'kcstmr' in co01m_schema['fields']
        assert co01m_schema['fields']['kcstmr']['required'] == True


class TestDBFParseError:
    """DBF解析異常測試"""
    
    def test_exception_creation(self):
        """測試異常建立"""
        error = DBFParseError("測試錯誤訊息")
        assert str(error) == "測試錯誤訊息"
        assert isinstance(error, Exception)
    
    def test_exception_inheritance(self):
        """測試異常繼承"""
        assert issubclass(DBFParseError, Exception)