# 貢獻指南 (Contributing Guide)

感謝您對診所AI查詢系統的關注！我們歡迎各種形式的貢獻，包括但不限於：

- 🐛 Bug回報
- 💡 功能建議
- 📝 文檔改進
- 🧪 測試案例
- 💻 程式碼貢獻

## 📋 開始之前

請確保您已經：

1. ⭐ **Star** 這個專案
2. 📖 閱讀過 [README.md](README.md)
3. 🔍 搜尋過現有的 [Issues](https://github.com/leon80148/chat4lab/issues)
4. 📚 瀏覽過相關 [文檔](docs/)

## 🐛 回報問題

在提交Issue之前，請：

1. **搜尋現有Issues** - 確認問題未被回報過
2. **使用Issue模板** - 提供完整的問題描述
3. **提供環境資訊** - 作業系統、Python版本等
4. **包含重現步驟** - 清楚的步驟說明
5. **附上日誌和截圖** - 如果適用的話

### 問題優先級

- 🔴 **Critical**: 系統崩潰、資料遺失、安全漏洞
- 🟠 **High**: 核心功能無法使用
- 🟡 **Medium**: 功能異常但有替代方案
- 🟢 **Low**: 小型改進、文檔錯誤

## 💡 功能建議

提出新功能時，請：

1. **描述使用場景** - 為什麼需要這個功能？
2. **說明預期行為** - 功能應該如何工作？
3. **考慮替代方案** - 是否有其他解決方式？
4. **評估影響範圍** - 對現有功能的影響？

## 💻 程式碼貢獻

### 開發環境設置

```bash
# 1. Fork並克隆專案
git clone https://github.com/YOUR_USERNAME/chat4lab.git
cd chat4lab

# 2. 創建虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安裝開發依賴
pip install -r requirements.txt
pip install pre-commit

# 4. 安裝pre-commit hooks
pre-commit install

# 5. 創建功能分支
git checkout -b feature/your-feature-name
```

### 開發流程

1. **分支策略**
   - `main`: 穩定的生產版本
   - `develop`: 開發版本
   - `feature/*`: 新功能開發
   - `bugfix/*`: Bug修復
   - `hotfix/*`: 緊急修復

2. **提交訊息規範**
   ```
   type(scope): description
   
   [optional body]
   
   [optional footer]
   ```
   
   類型說明：
   - `feat`: 新功能
   - `fix`: Bug修復
   - `docs`: 文檔更新
   - `style`: 代碼格式修改
   - `refactor`: 重構代碼
   - `test`: 測試相關
   - `chore`: 建構工具或輔助工具的變動

   範例：
   ```
   feat(dbf_parser): add support for CO05M file format
   
   - Added parsing logic for CO05M DBF files
   - Updated schema configuration
   - Added corresponding tests
   
   Closes #123
   ```

### 程式碼規範

#### Python代碼風格
- 遵循 [PEP 8](https://pep8.org/) 規範
- 使用 [Black](https://black.readthedocs.io/) 進行代碼格式化
- 使用 [Flake8](https://flake8.pycqa.org/) 進行風格檢查
- 使用 [MyPy](http://mypy-lang.org/) 進行類型檢查

#### 命名規範
- **文件名**: `snake_case.py`
- **類名**: `PascalCase` 
- **函數/變數**: `snake_case`
- **常數**: `UPPER_SNAKE_CASE`
- **私有成員**: `_leading_underscore`

#### 文檔字串
使用Google風格的docstring：

```python
def parse_dbf_file(file_path: str, encoding: str = 'big5') -> pd.DataFrame:
    """解析DBF檔案並返回DataFrame。
    
    Args:
        file_path: DBF檔案路徑
        encoding: 檔案編碼，預設為big5
        
    Returns:
        解析後的DataFrame
        
    Raises:
        FileNotFoundError: 檔案不存在
        UnicodeDecodeError: 編碼錯誤
        
    Example:
        >>> df = parse_dbf_file('data/CO01M.dbf')
        >>> print(df.shape)
        (1000, 15)
    """
```

### 測試要求

1. **測試覆蓋率** - 新功能必須達到80%以上覆蓋率
2. **測試類型**:
   - 單元測試：測試個別函數/類
   - 整合測試：測試模組間互動
   - 端到端測試：測試完整流程

3. **測試命名**:
   ```python
   def test_should_parse_co01m_file_successfully():
       """測試成功解析CO01M檔案"""
       
   def test_should_raise_error_when_file_not_found():
       """測試檔案不存在時應拋出錯誤"""
   ```

4. **執行測試**:
   ```bash
   # 運行所有測試
   pytest tests/ -v
   
   # 運行測試並生成覆蓋率報告
   pytest tests/ --cov=src --cov-report=html
   
   # 運行特定測試
   pytest tests/test_dbf_parser.py -v
   ```

### Pull Request流程

1. **檢查清單**
   - [ ] 代碼通過所有測試
   - [ ] 代碼覆蓋率符合要求
   - [ ] 遵循代碼風格規範
   - [ ] 更新相關文檔
   - [ ] 添加必要的測試案例

2. **PR描述**
   - 清楚描述變更內容
   - 說明解決的問題或實現的功能
   - 列出測試方法
   - 提及相關的Issue

3. **審查過程**
   - 至少需要1位維護者審查
   - 解決所有審查意見
   - 確保CI/CD通過

## 📝 文檔貢獻

### 文檔類型
- **API文檔**: 程式碼中的docstring
- **使用手冊**: `docs/` 目錄下的Markdown文件
- **README**: 專案首頁說明
- **技術文檔**: 架構設計、部署指南等

### 文檔風格
- 使用繁體中文
- 保持簡潔明瞭
- 提供實際範例
- 包含適當的截圖

## 🏷️ 發布流程

### 版本號規則
遵循 [語義化版本 2.0.0](https://semver.org/lang/zh-TW/)：

- **MAJOR**: 不相容的API變更
- **MINOR**: 向下相容的功能性新增
- **PATCH**: 向下相容的Bug修復

範例：`1.2.3`

### 發布檢查清單
- [ ] 所有測試通過
- [ ] 文檔已更新
- [ ] CHANGELOG.md已更新
- [ ] 版本號已更新
- [ ] 創建Git標籤
- [ ] 發布到GitHub Releases

## 🤝 社群準則

### 行為準則
- 🤝 **友善尊重** - 對所有參與者保持友善和尊重
- 💭 **開放心態** - 接受建設性的批評和建議
- 🎯 **專注主題** - 保持討論與專案相關
- 📚 **學習成長** - 樂於學習和分享知識

### 溝通管道
- **Issues**: 問題回報和功能建議
- **Discussions**: 一般討論和問答
- **Pull Requests**: 程式碼審查
- **Email**: 私人或敏感問題

## 🎉 感謝貢獻者

所有貢獻者都會在專案中得到認可：

- README.md中的貢獻者名單
- Git提交歷史記錄
- GitHub Contributors頁面

## 📞 需要幫助？

如果您在貢獻過程中遇到任何問題：

1. 📖 查看 [文檔](docs/)
2. 🔍 搜尋 [現有Issues](https://github.com/leon80148/chat4lab/issues)
3. 💬 發起 [新Discussion](https://github.com/leon80148/chat4lab/discussions)
4. 📧 聯絡維護者：leon80148@gmail.com

---

再次感謝您的貢獻！每一個貢獻都讓這個專案變得更好。 🙏