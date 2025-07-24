#!/usr/bin/env python3
"""
系統健康檢查腳本

檢查診所AI查詢系統的各個組件是否正常運作，
包括資料庫、LLM服務、配置檔案等。

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --verbose
    python scripts/health_check.py --json

Author: Leon Lu  
Created: 2025-01-24
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import requests
from datetime import datetime

# 添加項目根目錄到Python路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, ConfigError
from src.modules.db_manager import DatabaseManager, DatabaseError

# 設置日誌
logging.basicConfig(
    level=logging.WARNING,  # 預設只顯示警告和錯誤
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """系統健康檢查器"""
    
    def __init__(self, verbose: bool = False):
        """
        初始化健康檢查器
        
        Args:
            verbose: 是否顯示詳細資訊
        """
        self.verbose = verbose
        self.results = {}
        self.overall_status = True
        
        if verbose:
            logging.getLogger().setLevel(logging.INFO)
    
    def _log_info(self, message: str):
        """記錄資訊日誌"""
        if self.verbose:
            print(f"ℹ️  {message}")
    
    def _log_success(self, message: str):
        """記錄成功日誌"""
        print(f"✅ {message}")
    
    def _log_warning(self, message: str):
        """記錄警告日誌"""
        print(f"⚠️  {message}")
    
    def _log_error(self, message: str):
        """記錄錯誤日誌"""
        print(f"❌ {message}")
        self.overall_status = False
    
    def check_config(self) -> Dict[str, Any]:
        """檢查配置檔案"""
        self._log_info("檢查配置檔案...")
        
        result = {
            'status': 'ok',
            'details': {},
            'errors': []
        }
        
        try:
            # 載入配置管理器
            config = ConfigManager()
            
            # 檢查關鍵配置
            checks = [
                ('database.path', '資料庫路徑'),
                ('llm.base_url', 'LLM服務URL'),
                ('llm.model', 'LLM模型名稱'),
                ('security.authentication.enabled', '認證設定'),
                ('logging.level', '日誌級別')
            ]
            
            for config_key, description in checks:
                value = config.get(config_key)
                if value is not None:
                    result['details'][config_key] = str(value)
                    self._log_info(f"  {description}: {value}")
                else:
                    error_msg = f"缺少配置: {config_key}"
                    result['errors'].append(error_msg)
                    self._log_warning(error_msg)
            
            if result['errors']:
                result['status'] = 'warning'
            
            self._log_success("配置檔案檢查完成")
            
        except ConfigError as e:
            result['status'] = 'error'
            result['errors'].append(f"配置錯誤: {e}")
            self._log_error(f"配置檢查失敗: {e}")
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"未知錯誤: {e}")
            self._log_error(f"配置檢查發生錯誤: {e}")
        
        return result
    
    def check_database(self) -> Dict[str, Any]:
        """檢查資料庫連線和結構"""
        self._log_info("檢查資料庫...")
        
        result = {
            'status': 'ok',
            'details': {},
            'errors': []
        }
        
        try:
            config = ConfigManager()
            db_path = config.get('database.path', './data/anchia_lab.db')
            
            # 檢查資料庫檔案是否存在
            if not Path(db_path).exists():
                result['status'] = 'error'
                result['errors'].append(f"資料庫檔案不存在: {db_path}")
                self._log_error(f"資料庫檔案不存在: {db_path}")
                return result
            
            # 連線資料庫
            db_manager = DatabaseManager(db_path)
            
            # 檢查資料表
            tables = ['CO01M', 'CO02M', 'CO03M', 'CO18H']
            table_stats = {}
            
            for table in tables:
                try:
                    info = db_manager.get_table_info(table)
                    table_stats[table] = info['record_count']
                    self._log_info(f"  {table}: {info['record_count']} 筆記錄")
                except DatabaseError:
                    table_stats[table] = 0
                    self._log_warning(f"  {table}: 表不存在或無法存取")
            
            result['details']['tables'] = table_stats
            result['details']['database_size'] = Path(db_path).stat().st_size
            
            # 測試查詢
            try:
                test_result = db_manager.execute_query("SELECT COUNT(*) as total FROM CO01M")
                result['details']['test_query'] = 'success'
                self._log_info(f"  測試查詢成功")
            except DatabaseError as e:
                result['status'] = 'warning'
                result['errors'].append(f"測試查詢失敗: {e}")
                self._log_warning(f"測試查詢失敗: {e}")
            
            db_manager.close()
            self._log_success("資料庫檢查完成")
            
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"資料庫檢查失敗: {e}")
            self._log_error(f"資料庫檢查失敗: {e}")
        
        return result
    
    def check_ollama_service(self) -> Dict[str, Any]:
        """檢查Ollama LLM服務"""
        self._log_info("檢查Ollama服務...")
        
        result = {
            'status': 'ok',
            'details': {},
            'errors': []
        }
        
        try:
            config = ConfigManager()
            base_url = config.get('llm.base_url', 'http://localhost:11434')
            model_name = config.get('llm.model', 'gemma2:9b-instruct-q4_0')
            timeout = config.get('llm.timeout.connection', 10)
            
            # 檢查服務是否運行
            try:
                start_time = time.time()
                response = requests.get(f"{base_url}/api/tags", timeout=timeout)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result['details']['service_status'] = 'running'
                    result['details']['response_time'] = round(response_time, 3)
                    self._log_info(f"  服務回應時間: {response_time:.3f}秒")
                    
                    # 檢查模型是否存在
                    models = response.json().get('models', [])
                    model_names = [model.get('name', '') for model in models]
                    
                    if model_name in model_names:
                        result['details']['model_status'] = 'available'
                        self._log_info(f"  模型 {model_name} 已載入")
                    else:
                        result['status'] = 'warning'
                        result['errors'].append(f"模型 {model_name} 未找到")
                        self._log_warning(f"模型 {model_name} 未找到")
                    
                    result['details']['available_models'] = model_names
                    
                else:
                    result['status'] = 'error'
                    result['errors'].append(f"服務回應錯誤: HTTP {response.status_code}")
                    self._log_error(f"Ollama服務回應錯誤: HTTP {response.status_code}")
                
            except requests.exceptions.ConnectionError:
                result['status'] = 'error'
                result['errors'].append("無法連線到Ollama服務")
                self._log_error("無法連線到Ollama服務，請確認服務是否啟動")
            except requests.exceptions.Timeout:
                result['status'] = 'error'
                result['errors'].append("連線Ollama服務逾時")
                self._log_error("連線Ollama服務逾時")
            
            if result['status'] == 'ok':
                self._log_success("Ollama服務檢查完成")
            
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"Ollama服務檢查失敗: {e}")
            self._log_error(f"Ollama服務檢查失敗: {e}")
        
        return result
    
    def check_file_system(self) -> Dict[str, Any]:
        """檢查檔案系統和目錄權限"""
        self._log_info("檢查檔案系統...")
        
        result = {
            'status': 'ok',
            'details': {},
            'errors': []
        }
        
        try:
            # 檢查重要目錄
            directories = [
                ('data', '資料目錄'),
                ('logs', '日誌目錄'),
                ('config', '配置目錄')
            ]
            
            for dir_name, description in directories:
                dir_path = Path(dir_name)
                
                if dir_path.exists():
                    result['details'][dir_name] = {
                        'exists': True,
                        'writable': os.access(dir_path, os.W_OK),
                        'size': sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                    }
                    self._log_info(f"  {description}: 存在且可存取")
                else:
                    result['details'][dir_name] = {'exists': False}
                    result['status'] = 'warning'
                    result['errors'].append(f"{description}不存在: {dir_path}")
                    self._log_warning(f"{description}不存在: {dir_path}")
            
            # 檢查磁碟空間
            import shutil
            free_space = shutil.disk_usage('.').free
            result['details']['free_space_mb'] = free_space // (1024 * 1024)
            
            if free_space < 100 * 1024 * 1024:  # 少於100MB
                result['status'] = 'warning'
                result['errors'].append("磁碟空間不足")
                self._log_warning("磁碟空間不足")
            
            self._log_success("檔案系統檢查完成")
            
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"檔案系統檢查失敗: {e}")
            self._log_error(f"檔案系統檢查失敗: {e}")
        
        return result
    
    def check_dependencies(self) -> Dict[str, Any]:
        """檢查Python依賴套件"""
        self._log_info("檢查依賴套件...")
        
        result = {
            'status': 'ok',
            'details': {},
            'errors': []
        }
        
        try:
            # 重要依賴清單
            dependencies = [
                ('streamlit', 'Web框架'),
                ('pandas', '資料處理'),
                ('simpledbf', 'DBF檔案處理'),
                ('sqlite3', 'SQLite資料庫'),
                ('requests', 'HTTP請求'),
                ('yaml', 'YAML處理'),
                ('dotenv', '環境變數')
            ]
            
            import importlib
            
            for module_name, description in dependencies:
                try:
                    module = importlib.import_module(module_name)
                    version = getattr(module, '__version__', 'unknown')
                    result['details'][module_name] = {
                        'installed': True,
                        'version': version
                    }
                    self._log_info(f"  {description} ({module_name}): {version}")
                except ImportError:
                    result['details'][module_name] = {'installed': False}
                    result['status'] = 'error'
                    result['errors'].append(f"缺少依賴: {module_name}")
                    self._log_error(f"缺少依賴套件: {module_name}")
            
            if result['status'] == 'ok':
                self._log_success("依賴套件檢查完成")
            
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"依賴檢查失敗: {e}")
            self._log_error(f"依賴檢查失敗: {e}")
        
        return result
    
    def run_all_checks(self) -> Dict[str, Any]:
        """執行所有健康檢查"""
        print("🏥 診所AI查詢系統 - 健康檢查")
        print("=" * 50)
        
        checks = [
            ('config', self.check_config),
            ('dependencies', self.check_dependencies),
            ('file_system', self.check_file_system),
            ('database', self.check_database),
            ('ollama_service', self.check_ollama_service)
        ]
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'ok',
            'checks': {}
        }
        
        for check_name, check_func in checks:
            print(f"\n📋 {check_name.replace('_', ' ').title()}")
            print("-" * 30)
            
            try:
                result = check_func()
                results['checks'][check_name] = result
                
                if result['status'] != 'ok':
                    results['overall_status'] = result['status']
                
            except Exception as e:
                error_result = {
                    'status': 'error',
                    'details': {},
                    'errors': [f"檢查失敗: {e}"]
                }
                results['checks'][check_name] = error_result
                results['overall_status'] = 'error'
                self._log_error(f"{check_name} 檢查失敗: {e}")
        
        # 最終狀態
        if results['overall_status'] == 'ok':
            results['overall_status'] = 'ok' if self.overall_status else 'error'
        
        print(f"\n🎯 總體狀態: {results['overall_status'].upper()}")
        
        if results['overall_status'] == 'ok':
            print("✅ 系統運行正常！")
        elif results['overall_status'] == 'warning':
            print("⚠️  系統運行但有警告，建議檢查相關問題")
        else:
            print("❌ 系統存在問題，需要修復")
        
        return results


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description="診所AI查詢系統健康檢查工具"
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='顯示詳細資訊'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='以JSON格式輸出結果'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='將結果保存到檔案'
    )
    
    args = parser.parse_args()
    
    try:
        # 執行健康檢查
        checker = HealthChecker(verbose=args.verbose)
        results = checker.run_all_checks()
        
        # 輸出結果
        if args.json:
            output = json.dumps(results, indent=2, ensure_ascii=False)
            print(output)
        
        # 保存到檔案
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n📄 結果已保存到: {args.output}")
        
        # 設置退出碼
        if results['overall_status'] == 'ok':
            sys.exit(0)
        elif results['overall_status'] == 'warning':
            sys.exit(1)
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n用戶中斷操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 健康檢查失敗: {e}")
        sys.exit(2)


if __name__ == "__main__":
    import os
    main()