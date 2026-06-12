# Milestone 2 Acceptance Report (M2 驗收報告)

本報告用作 Milestone 2「Student System 與任務集」完成後的正式驗收文件，詳細記錄了實際測試執行結果、沙盒隔離優化以及專案偏離修正歷程。

---

## 一、 實際建立之檔案與目錄清單 (M2 Deliverables)

| 序號 | 檔案路徑 | 實際用途與說明 | 狀態 |
| :---: | :--- | :--- | :---: |
| **1** | `student_system/README.md` | 學生資訊管理系統基礎架構與指引 | 🟢 已完成 |
| **2** | `student_system/API_SPEC.md` | A-RAG 唯一核准的 API 真實文檔 | 🟢 已完成 |
| **3** | `student_system/STYLE_GUIDE.md` | 編碼標準與例外捕獲規範 | 🟢 已完成 |
| **4** | `student_system/ISSUES.md` | 當前系統已知缺陷（T03, T04, T05 之依據） | 🟢 已完成 |
| **5** | `student_system/src/student.py` | 學生模組與 Mock DB 起點 | 🟢 已完成 |
| **6** | `student_system/src/course.py` | 課程模組起點 | 🟢 已完成 |
| **7** | `student_system/src/grade.py` | 成績模組起點（含刻意 GPA 漏洞） | 🟢 已完成 |
| **8** | `student_system/src/utils.py` | 工具模組起點（含刻意邊界判定漏洞） | 🟢 已完成 |
| **9** | `student_system/tests/public/test_t01.py` | T01 公開測試例：及格率基礎判定 | 🟢 已完成 |
| **10** | `student_system/tests/public/test_t02.py` | T02 公開測試例：修課摘要基礎判定 | 🟢 已完成 |
| **11** | `student_system/tests/public/test_t03.py` | T03 公開測試例：GPA 修正陽性行為（驗證 85 映射為 3.5 失敗） | 🟢 已完成 |
| **12** | `student_system/tests/public/test_t04.py` | T04 公開測試例：分數邊界陽性行為（驗證 0 與 100 為 True 失敗） | 🟢 已完成 |
| **13** | `student_system/tests/public/test_t05.py` | T05 公開測試例：重構功能無損性（確認 validate_score 存在與呼叫失敗） | 🟢 已完成 |
| **14** | `evaluation/hidden_tests/test_t01.py` | T01 隱藏測試：異常處理與無效課程判定 | 🟢 已完成 |
| **15** | `evaluation/hidden_tests/test_t02.py` | T02 隱藏測試：API 外部干擾與私有全域字典排除 | 🟢 已完成 |
| **16** | `evaluation/hidden_tests/test_t03.py` | T03 隱藏測試：臨界 GPA 邊界分數與 ValueError 例外 | 🟢 已完成 |
| **17** | `evaluation/hidden_tests/test_t04.py` | T04 隱藏測試：0、100 與非數值、Boolean 型別過濾 | 🟢 已完成 |
| **18** | `evaluation/hidden_tests/test_t05.py` | T05 隱藏測試：AST 靜態分析，判定 Call 節點並排除 Compare 硬編碼 | 🟢 已完成 |
| **19** | `evaluation/reference_patches/T01.diff` | T01 參考修正 patch：僅供驗收，不進入 tasks.json 與檢索 | 🟢 已完成 |
| **20** | `evaluation/reference_patches/T02.diff` | T02 參考修正 patch：僅供驗收，不進入 tasks.json 與檢索 | 🟢 已完成 |
| **21** | `evaluation/reference_patches/T03.diff` | T03 參考修正 patch：僅供驗收，不進入 tasks.json 與檢索 | 🟢 已完成 |
| **22** | `evaluation/reference_patches/T04.diff` | T04 參考修正 patch：僅供驗收，不進入 tasks.json 與檢索 | 🟢 已完成 |
| **23** | `evaluation/reference_patches/T05.diff` | T05 參考修正 patch：僅供驗收，不進入 tasks.json | 🟢 已完成 |
| **24** | `experiments/tasks.json` | 完整合規之五題題庫配置檔 | 🟢 已完成 |
| **25** | `student_system/SNAPSHOT.json` | 包含起始原始碼與 allowed_corpus SHA-256 之 Snapshot 檔 | 🟢 已完成 |

---

## 二、 實際驗收檢查點與不變量校驗 (Acceptance Checklist)

### 2.1 JSON Schema 語法與格式驗證
* [x] 1. **任務集語法查核**：
  使用標準之 `Draft202012Validator.check_schema(...)` 校驗 `contracts/task.schema.json`；並以該 schema 驗證 `experiments/tasks.json` 的每題配置。
* [x] 2. **子集一致性校驗**：
  對於 `experiments/tasks.json` 中的每題配置，校驗其 `required_evidence` 的所有路徑，**必須完全屬於 `allowed_corpus` 之子集**。
* [x] 3. **路徑一致性校驗**：
  驗證 `experiments/tasks.json` 與 `student_system/SNAPSHOT.json` 中所有的路徑均為 repo-root-relative（以 `student_system/` 開頭），不得出現裸檔名。
* [x] 4. **資料隔離與防洩漏校驗**：
  驗證 `experiments/tasks.json` 與 `student_system/SNAPSHOT.json` 的任何欄位內容中，**絕對不包含** `evaluation/hidden_tests` 與 `evaluation/reference_patches` 之路徑。

### 2.2 逐題隔離之陰性校驗 (Starter Negative Verification)
為確保任務的有效性，在乾淨的 Starter 狀態下，關閉位元碼編譯（`PYTHONDONTWRITEBYTECODE=1`）逐題執行對應的公開測試，全數預期失敗：
* [x] 1. 執行 `pytest student_system/tests/public/test_t01.py` -> 實際：**FAILED** (及格率函式不存在，Exit Code = 1)
* [x] 2. 執行 `pytest student_system/tests/public/test_t02.py` -> 實際：**FAILED** (修課摘要函式不存在，Exit Code = 1)
* [x] 3. 執行 `pytest student_system/tests/public/test_t03.py` -> 實際：**FAILED** (臨界分數 85 的 GPA 映射錯誤：Starter 誤對照為 3.0，實際斷言為 3.5 導致失敗，Exit Code = 1)
* [x] 4. 執行 `pytest student_system/tests/public/test_t04.py` -> 實際：**FAILED** (分數邊界 0 與 100 判定錯誤：Starter 對 0 與 100 回傳 False，實際斷言為 True 導致失敗，Exit Code = 1)
* [x] 5. 執行 `pytest student_system/tests/public/test_t05.py` -> 實際：**FAILED** (validate_score 函式不存在，Exit Code = 1)

### 2.3 逐題隔離之陽性校驗 (Reference Positive Verification)
為確保測試案例與參考解法的正確性，自乾淨 Starter 狀態中套用其專屬之 reference patch，該題的 public 與 hidden 測試全數通過（在獨立沙盒中運行）：
* [x] 1. **T01 驗收**：套用 `T01.diff` -> 執行 `pytest student_system/tests/public/test_t01.py evaluation/hidden_tests/test_t01.py` -> 實際：**PASSED**。
* [x] 2. **T02 驗收**：套用 `T02.diff` -> 執行 `pytest student_system/tests/public/test_t02.py evaluation/hidden_tests/test_t02.py` -> 實際：**PASSED**。
* [x] 3. **T03 驗收**：套用 `T03.diff` -> 執行 `pytest student_system/tests/public/test_t03.py evaluation/hidden_tests/test_t03.py` -> 實際：**PASSED**。
* [x] 4. **T04 驗收**：套用 `T04.diff` -> 執行 `pytest student_system/tests/public/test_t04.py evaluation/hidden_tests/test_t04.py` -> 實際：**PASSED**。
* [x] 5. **T05 驗收**：套用 `T05.diff` -> 執行 `pytest student_system/tests/public/test_t05.py evaluation/hidden_tests/test_t05.py` -> 實際：**PASSED**。

---

## 三、 真實偏離歷程與修正說明 (Deviations and Corrections)

### 3.1 首次測試執行的偏離 (34 Passed, 1 Failed)
* **偏離事實**：在 Milestone 2 沙盒清理代碼的首版實作中，測試會於專案根目錄手動拼接並建立名為 `temp_sandbox_TXX` 的工作目錄。在 Windows 10 環境下，當 pytest 透過 subprocess 執行測試後，Python 直譯器鎖定了目錄下的編譯位元碼（`.pyc` 與 `__pycache__` 檔案），導致測試套件在 `finally` 區塊中試圖刪除目錄時觸發了 `PermissionError`。
* **失敗後果**：由於當時使用了具有靜默容錯特性的清理邏輯（`ignore_errors=True`），雖然在終端機中未顯式阻斷其他代碼，但在其中一個測試場景中，因為殘留的實體目錄被後續的不變量洩漏檢測器捕捉，導致最終產生了 **34 Passed, 1 Failed** 的斷言偏離。

### 3.2 已部署之優化與防禦性修正
為了徹底解決此一系統平台（Windows）特有的檔案鎖定偏離，我們實施了以下修正：
1. **重構沙盒位置**：在 `tests/m2/test_reference_patches.py` 中，徹底捨棄於專案根目錄手動建立沙盒，改用標準庫之 `tempfile.TemporaryDirectory` 在作業系統的標準暫存區（`TEMP`）建立沙盒，退出上下文時強制系統級清理。
2. **禁止位元碼編譯**：在沙盒內執行子進程 `subprocess` 時，顯式傳入環境變數 `PYTHONDONTWRITEBYTECODE=1`，防止子環境生成 `__pycache__` 與 `.pyc` 檔案，根除了 Windows 下控制代碼被鎖死的物理因素。
3. **主控端快取禁用 (pyproject.toml)**：在專案根目錄的 `pyproject.toml` 中配置了 `addopts = ["-p", "no:cacheprovider"]`，關閉 pytest 的本地快取記錄，防止在專案目錄下自動生成 `.pytest_cache`。
4. **拷貝過濾**：使用自訂拷貝過濾規則，徹底避免在複製學員系統到暫存沙盒時，把既有的快取資料夾複製進去。
5. **擴大 Cache 洩漏掃描**：在 `tests/m2/test_no_leakage.py` 中，將 cache 掃描檢測範圍由原本僅 `student_system` 擴大至 `student_system`、`evaluation`、`tests/m2`、`tests/contracts` 四大核心區塊，徹底防堵快取垃圾。

---

## 四、 修正後的最新連續兩次測試結果

在上述環境變數與套件配置優化部署完畢後，在 `PYTHONDONTWRITEBYTECODE=1` 的環境下，連續執行了兩次完整合約與 M2 自動化套件驗收：

### 4.1 第一次連續執行結果
* **執行命令**：`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/contracts tests/m2 -v`
* **測試摘要**：**35 PASSED**，0 FAILED。
* **耗時**：3.75s。

### 4.2 第二次連續執行結果
* **執行命令**：`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/contracts tests/m2 -v`
* **測試摘要**：**35 PASSED**，0 FAILED。
* **耗時**：4.17s。

---

## 五、 最終掃描驗證結果

第二次測試結束後，執行了專屬的最終物理快照與快取洩漏掃描：
1. **Repo Root 殘留掃描**：`temp_sandbox_T*` 目錄存在數：**0（無任何殘留）**。
2. **Bytecode 與 Cache 殘留掃描**：
   在 `student_system`、`evaluation`、`tests/m2`、`tests/contracts` 中：
   * `__pycache__` 目錄數：**0**。
   * `.pytest_cache` 目錄數：**0**。
   * `*.pyc` 檔案數：**0**。
3. **SNAPSHOT 哈希完整性**：
   `student_system/SNAPSHOT.json` 中登記的 13 個檔案，其實體 SHA-256 哈希值與登錄檔 **100% 精確吻合**，無任何哈希偏移。

本階段（Milestone 2）已達到 100% 穩定之防禦、零快取、零殘留狀態，建議批准進入後續開發階段。
