"""
配置管理器

負責載入和管理系統配置，支援環境變數覆蓋和配置驗證。

Author: Leon Lu
Created: 2025-01-24
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置相關異常"""
    pass


class ConfigManager:
    """
    配置管理器
    
    負責載入YAML配置檔案、環境變數，並提供配置存取介面。
    支援配置驗證和預設值處理。
    """
    
    def __init__(self, config_path: Optional[str] = None, env_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: YAML配置檔案路徑
            env_file: .env環境變數檔案路徑
        """
        self.config_path = Path(config_path or "config/settings.yaml")
        self.env_file = env_file or ".env"
        self.config = {}
        
        # 載入配置
        self._load_environment()
        self._load_config_file()
        self._override_with_env()
        self._validate_config()
        
        logger.info(f"配置管理器已初始化: {self.config_path}")
    
    def _load_environment(self):
        """載入.env環境變數檔案"""
        try:
            if os.path.exists(self.env_file):
                load_dotenv(self.env_file)
                logger.info(f"已載入環境變數檔案: {self.env_file}")
            else:
                logger.info("未找到.env檔案，使用系統環境變數")
        except Exception as e:
            logger.warning(f"載入環境變數檔案失敗: {e}")
    
    def _load_config_file(self):
        """載入YAML配置檔案"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f"已載入配置檔案: {self.config_path}")
            else:
                logger.warning(f"配置檔案不存在，使用預設配置: {self.config_path}")
                self.config = self._get_default_config()
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML配置檔案格式錯誤: {e}")
        except Exception as e:
            raise ConfigError(f"載入配置檔案失敗: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """取得預設配置"""
        return {
            'system': {
                'name': '診所AI查詢系統',
                'version': '1.0.0',
                'author': 'Leon Lu',
                'license': 'MIT'
            },
            'database': {
                'type': 'sqlite',
                'path': './data/anchia_lab.db',
                'encoding': 'big5',
                'performance': {
                    'journal_mode': 'WAL',
                    'synchronous': 'NORMAL',
                    'cache_size': 10000,
                    'temp_store': 'MEMORY',
                    'mmap_size': 268435456
                }
            },
            'llm': {
                'provider': 'ollama',
                'base_url': 'http://localhost:11434',
                'model': 'llama3:8b-instruct',
                'parameters': {
                    'temperature': 0.2,
                    'max_tokens': 2048,
                    'top_p': 0.9,
                    'top_k': 40
                },
                'timeout': {
                    'connection': 10,
                    'inference': 30
                }
            },
            'security': {
                'authentication': {
                    'enabled': True,
                    'session_timeout': 1800,
                    'max_login_attempts': 3
                },
                'query_limits': {
                    'max_results': 1000,
                    'max_execution_time': 30
                },
                'sensitive_fields': ['mpersonid', 'mtelh', 'mfml']
            },
            'ui': {
                'theme': 'light',
                'language': 'zh-TW',
                'page': {
                    'title': '診所AI查詢系統',
                    'icon': '🏥',
                    'layout': 'wide'
                }
            },
            'logging': {
                'level': 'INFO',
                'file': './logs/clinic_ai.log',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }
    
    def _override_with_env(self):
        """使用環境變數覆蓋配置"""
        env_mappings = {
            # 系統設定
            'APP_NAME': ['system', 'name'],
            'APP_VERSION': ['system', 'version'],
            'DEBUG': ['development', 'debug'],
            
            # 資料庫設定
            'DATABASE_PATH': ['database', 'path'],
            'DB_ENCODING': ['database', 'encoding'],
            
            # LLM設定
            'OLLAMA_BASE_URL': ['llm', 'base_url'],
            'OLLAMA_MODEL': ['llm', 'model'],
            'OLLAMA_TIMEOUT': ['llm', 'timeout', 'inference'],
            
            # 安全設定
            'SESSION_TIMEOUT': ['security', 'authentication', 'session_timeout'],
            'MAX_QUERY_RESULTS': ['security', 'query_limits', 'max_results'],
            'MAX_LOGIN_ATTEMPTS': ['security', 'authentication', 'max_login_attempts'],
            
            # Streamlit設定
            'STREAMLIT_SERVER_PORT': ['ui', 'streamlit', 'port'],
            'STREAMLIT_SERVER_ADDRESS': ['ui', 'streamlit', 'address'],
            
            # 日誌設定
            'LOG_LEVEL': ['logging', 'level'],
            'LOG_FILE': ['logging', 'file']
        }
        
        for env_key, config_keys in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                self._set_nested_config(config_keys, env_value)
    
    def _set_nested_config(self, keys: list, value: str):
        """設置嵌套配置值"""
        # 嘗試轉換資料類型
        converted_value = self._convert_env_value(value)
        
        # 設置嵌套字典值
        current = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = converted_value
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool, None]:
        """轉換環境變數值的資料類型"""
        # 布林值
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # None值
        if value.lower() in ('null', 'none', ''):
            return None
        
        # 數值
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # 字串 (預設)
        return value
    
    def _validate_config(self):
        """驗證配置完整性"""
        required_sections = ['system', 'database', 'llm', 'security']
        
        for section in required_sections:
            if section not in self.config:
                logger.warning(f"缺少配置區段: {section}")
                self.config[section] = {}
        
        # 驗證關鍵配置
        validations = [
            (['database', 'path'], str, "資料庫路徑必須是字串"),
            (['llm', 'base_url'], str, "LLM基礎URL必須是字串"),
            (['security', 'authentication', 'session_timeout'], int, "會話逾時必須是整數"),
            (['logging', 'level'], str, "日誌級別必須是字串")
        ]
        
        for keys, expected_type, error_msg in validations:
            value = self.get_nested(keys)
            if value is not None and not isinstance(value, expected_type):
                logger.warning(f"配置類型錯誤: {error_msg}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        取得配置值
        
        Args:
            key: 配置鍵 (支援點號分隔的嵌套鍵)
            default: 預設值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        return self.get_nested(keys, default)
    
    def get_nested(self, keys: list, default: Any = None) -> Any:
        """
        取得嵌套配置值
        
        Args:
            keys: 配置鍵列表
            default: 預設值
            
        Returns:
            配置值
        """
        current = self.config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any):
        """
        設置配置值
        
        Args:
            key: 配置鍵 (支援點號分隔的嵌套鍵)
            value: 配置值
        """
        keys = key.split('.')
        self._set_nested_config(keys, str(value))
    
    def get_database_config(self) -> Dict[str, Any]:
        """
        取得資料庫配置
        
        將嵌套的performance配置展平到根層級，以確保DatabaseManager能正確存取配置項目。
        
        Returns:
            展平後的資料庫配置字典
        """
        db_config = self.get('database', {}).copy()
        
        # 將performance配置展平到根層級
        if 'performance' in db_config:
            performance_config = db_config.pop('performance')
            if isinstance(performance_config, dict):
                # 將performance下的配置項目提升到根層級
                db_config.update(performance_config)
        
        # 確保必要的配置項目存在，使用預設值
        default_performance = {
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL', 
            'cache_size': 10000,
            'temp_store': 'MEMORY',
            'mmap_size': 268435456,
            'foreign_keys': True,
            'busy_timeout': 30000
        }
        
        for key, default_value in default_performance.items():
            if key not in db_config:
                db_config[key] = default_value
        
        return db_config
    
    def get_llm_config(self) -> Dict[str, Any]:
        """取得LLM配置"""
        return self.get('llm', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """取得安全配置"""
        return self.get('security', {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """取得UI配置"""
        return self.get('ui', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """取得日誌配置"""
        return self.get('logging', {})
    
    def is_debug_mode(self) -> bool:
        """是否為除錯模式"""
        return self.get('development.debug', False)
    
    def is_production_mode(self) -> bool:
        """是否為生產模式"""
        return not self.is_debug_mode()
    
    def get_sensitive_fields(self) -> list:
        """取得敏感欄位清單"""
        return self.get('security.sensitive_fields', [])
    
    def export_config(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        匯出配置 (隱藏敏感資訊)
        
        Args:
            output_path: 輸出檔案路徑 (可選)
            
        Returns:
            配置字典
        """
        # 複製配置並隱藏敏感資訊
        safe_config = self._mask_sensitive_data(self.config.copy())
        
        # 如果指定輸出路徑，則寫入檔案
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    yaml.dump(safe_config, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
                logger.info(f"配置已匯出到: {output_path}")
            except Exception as e:
                logger.error(f"匯出配置失敗: {e}")
        
        return safe_config
    
    def _mask_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """遮蔽敏感資訊"""
        sensitive_keys = ['password', 'key', 'secret', 'token', 'api_key']
        
        def mask_recursive(obj):
            if isinstance(obj, dict):
                return {
                    k: '***MASKED***' if any(sens in k.lower() for sens in sensitive_keys) 
                    else mask_recursive(v) 
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [mask_recursive(item) for item in obj]
            else:
                return obj
        
        return mask_recursive(config)
    
    def reload(self):
        """重新載入配置"""
        self.config = {}
        self._load_environment()
        self._load_config_file()
        self._override_with_env()
        self._validate_config()
        logger.info("配置已重新載入")
    
    def __str__(self) -> str:
        """字串表示"""
        return f"ConfigManager(config_path={self.config_path})"
    
    def __repr__(self) -> str:
        """詳細字串表示"""
        return f"ConfigManager(config_path={self.config_path}, sections={list(self.config.keys())})"