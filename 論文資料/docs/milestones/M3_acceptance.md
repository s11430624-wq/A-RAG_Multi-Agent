# Milestone 3 Acceptance Report (M3 驗收報告)

本報告用作 Milestone 3「安全隔離、Runtime 與 Evaluator」完成後的驗收標準。此時已實作完成 **M3.0: Result Schema Amendment**、**M3.1: Runtime、安全隔離與 Patch Engine** 與 **M3.2: Evaluator 與多輪修復流程**。

---

## 一、 核心檔案與目錄清單 (M3 Deliverables)

| 序號 | 檔案路徑 | 用途與說明 | 狀態 |
| :---: | :--- | :--- | :---: |
| **1** | `contracts/result.schema.json` | 更新 JSON Schema 契約，以 if-then-else 控制不同評審狀態下之人工評分格式限制 | 🟢 已完成 (M3.0) |
| **2** | `tests/contracts/test_result_schema.py` | 新增合約測試案例，涵蓋 pending (全 null)、reviewed/disputed (合法 integer) 及各種邊界錯誤與 regression | 🟢 已完成 (M3.0) |
| **3** | `experiments/runtime/workspace.py` | 拋棄式沙盒生命週期管理器，校驗三階段 SNAPSHOT 哈希與乾淨複製 | 🟢 已完成 (M3.1) |
| **4** | `experiments/runtime/patching.py` | 自製 Unified Diff 原生補丁安全檢查（禁止絕對路徑、traversal、dev/null、shell 調用）與 strict line/offset 匹配 | 🟢 已完成 (M3.1) |
| **5** | `experiments/runtime/test_runner.py` | 在隔離子進程執行測試，清空 PYTHONPATH，隱藏測試反饋去敏與精準樹超時殺除 | 🟢 已完成 (M3.1) |
| **6** | `experiments/runtime/guards.py` | 靜態與執行期路徑安全防禦，支援 Windows 正規化及 Junction/Symlink 逃逸阻斷，以 `Path.is_relative_to` 防堵同級目錄 escape | 🟢 已完成 (M3.1) |
| **7** | `experiments/runtime/__init__.py` | 包匯出介面宣告，曝露 WorkspaceManager, SecurityGuards, PatchEngine 與 SecureTestRunner | 🟢 已完成 (M3.1) |
| **8** | `experiments/evaluation/evaluator.py` | 連接沙盒與執行器的評估核心，定義重新運作之 Pass 1 與 Pass 2 多輪修復流程，移除內部 Starter Red | 🟢 已完成 (M3.2) |
| **9** | `experiments/evaluation/metrics.py` | 統計與指標記錄，精密分類 `infra_error=False`（大腦代碼錯誤）與 `infra_error=True`（基礎設施掛死） | 🟢 已完成 (M3.2) |
| **10** | `tests/runtime/test_workspace_isolation.py` | TDD 測項 1：驗證暫存區沙盒、無 sys.path、哈希三階段防範、與 tmp_path 測試隔離 | 🟢 已完成 (M3.1) |
| **11** | `tests/runtime/test_patch_engine.py` | TDD 測項 2：驗證 Unified Diff 各類非法補丁（traversal, dev/null等）原生拒絕 | 🟢 已完成 (M3.1) |
| **12** | `tests/leakage/test_leakage_prevent.py` | TDD 測項 3：驗證隱藏測試 Traceback 過濾、__file__ 沙盒實體檢驗、精準 tree 殺除與 symlink 備用 skip 檢測 | 🟢 已完成 (M3.1) |
| **13** | `tests/runtime/test_evaluator_integration.py` | TDD 測項 4：端到端整合，使用參考補丁（一輪過）與 incomplete 補丁（修復流）驗證 | 🟢 已完成 (M3.2) |

---

## 二、 驗收檢查點與不變量校驗 (Acceptance Checklist)

### 2.1 基礎合約與回歸校驗 (Contracts & M2 Regressions)
* [x] 1. **M1 合約測試無損與擴充**：
  在啟用 `PYTHONDONTWRITEBYTECODE=1` 的環境下，執行 `pytest tests/contracts -v` -> 實際：**35 PASSED** (包含 8 個新增之 M3.0 合約測試)。
* [x] 2. **M2 洩漏與快照測試無損**：
  執行 `pytest tests/m2 -v` -> 實際：**8 PASSED**。
* [x] 3. **學員系統 Starter Red 狀態保留**：
  逐題執行學員系統公開測試，確認均為 **FAILED (Exit Code = 1)**：
  - `pytest student_system/tests/public/test_t01.py`
  - `pytest student_system/tests/public/test_t02.py`
  - `pytest student_system/tests/public/test_t03.py`
  - `pytest student_system/tests/public/test_t04.py`
  - `pytest student_system/tests/public/test_t05.py`

### 2.2 M3.0 Result Schema Amendment 核心校驗
* [x] 1. **pending + 四個 null (None)**：通過驗證。
* [x] 2. **pending + 任一 integer (整數)**：驗證失敗。
* [x] 3. **reviewed + 合法 integers**：通過驗證。
* [x] 4. **disputed + 合法 integers**：通過驗證。
* [x] 5. **reviewed/disputed + 任一 null**：驗證失敗。
* [x] 6. **任人工欄位缺失**：驗證失敗。
* [x] 7. **數值超出原定義範圍**：驗證失敗。
* [x] 8. **原有 result schema 正例與反例無退化**：通過驗證。

### 2.3 M3.1 安全隔離與 Runtime 核心校驗
* [x] 1. **沙盒實體與多階段 Integrity 隔離 (WorkspaceManager)**：
  - 證實沙盒建立於 `TEMP` 暫存區，複製時完全不包含 `hidden_tests` 等敏感路徑。
  - 證實 `sys.path` 絕無污染。
  - 證實沙盒在建立前、複製後、Patch 後均有完整性校驗（不允許增刪檔案與越權變更）。
  - 證實 Snapshot 驗證測試全部在 `tmp_path` 中操作學員複本，絕對不修改正式的學員目錄。
* [x] 2. **原生 Unified Diff 審查與拒絕 (PatchEngine)**：
  - 證實所有非法 Unified Diff 屬性（絕對路徑、`..`、`/dev/null` 增刪、rename、binary、重複 section、mismatched hunk）被原生解析器 100% 拒絕。
  - 證實全程不呼叫任何 shell 指令（不呼叫 `patch` 或 `git apply`）。
  - 證實套用失敗時具備原子事務性，不會在磁碟留下部分修改痕跡。
  - 證實使用完整匹配驗證 hunk header，完美拒絕 `@@ ... @@ garbage` 與 `@@ ... @@ garbage with spaces`。
  - 證實當 hunk 宣告 count 已滿時，下一行只能是下一個 @@、下一個 --- section、合法的 \ No newline marker 或 EOF，任何額外 +、-、context 或其他文字皆報錯拒絕。
  - 證實完全不靜默忽略 patch 中任何非 diff 或非法內容。
* [x] 3. **資訊安全與隱私防洩漏（洩漏測試）(SecureTestRunner & SecurityGuards)**：
  - 證實 pytest 執行時清空 `PYTHONPATH`，且被載入學員模組之 `__file__` 實體絕對位於沙盒內。
  - 證實 `HiddenTestSummary` 僅包含 passed_count, total_count, duration_seconds 與 timeout_occurred，以及 runner_error 狀態，絕不洩漏任何 stdout、stderr、traceback 或敏感測試路徑。
  - 證實 JUnit XML 檔案在被 evaluator 解析後，於 evaluator-owned temp dir 中立即被物理刪除。
  - 證實超時程序清理僅精確終止被捕獲的特定子進程 PID 進程樹，不影響無關 Python 程序。
  - 證實 Windows 下 Symlink 權限不足時自動 skip，且不依賴權限的實體 resolved path 逃逸比對順利通過，防止 `sibling-prefix` 逃逸（如 `C:\base2` 阻斷）。
* [x] 4. **測試執行期健全性與精確統計 (SecureTestRunner & parse_junit_xml)**：
  - 證實 `parse_junit_xml` 深度提取 tests, failures, errors, skipped, time 等計數屬性。
  - 證實 skipped 測試不列入 passed/failed 測試清單，且 skipped > 0 時 `passed` 判定必然為 False。
  - 證實 collection error、tests=0、pytest exit code 4/5 或 XML 缺失/損毀均會正確判定並標記為 `runner_error=True`，且 Public 測試會記錄對應的 `collection_error` 訊息。

### 2.4 M3.2 整合與 Evaluator 確定性測試
* [x] 1. **重新定義的 Pass 1 與 Pass 2 運作流**：
  - 證實 Evaluator 成功載入 `tasks.json` 並以 `task.schema.json` 校驗。
  - 證實 Pass 1 對 `initial_patch` 的安全套用、只修改 `files_to_modify` 的變更驗證與 Pass 1 測試執行。
  - 證實當 Pass 1 公開測試失敗時，能執行 Pass 2 多輪修復（最多 `max_repair_rounds`），且在公開測試首次全數通過時，能立即中斷（Early Stopping）。
  - 證實 Pass 1 公開測試通過、但隱藏測試失敗時，絕不觸發 any 修復補丁套用（無多餘修復運作）。
  - 證實所有大腦錯誤（`EmptyResponseError`, `InvalidPatchError`, `PatchApplyError`）被 metrics 分類為 `infra_error=False`、`stop_reason="repair_limit"`、且標記為 `valid_run=True`；所有系統錯誤（`TestTimeoutError`, `RunnerError`）被 metrics 分類為 `infra_error=True`、`stop_reason="infra_error"`、且標記為 `valid_run=False`。
  - 證實產出的報告 100% 符合 `result.schema.json` 契約並通過其條件約束檢驗。
* [x] 2. **Evaluator 資料隔離與邊界修正**：
  - 證實完全移除了公開的 `repair_records` 屬性。
  - 證實策略可見介面僅提供 `public_feedback_history`，其結構與欄位完全不包含任何隱藏測試 (hidden) 的 passed/total 指標、路徑、名稱或輸出。
  - 證實每輪隱藏測試的 metrics 均被安全存放至 `_private_audit_records` 這個僅 Evaluator 可見之私有審計結構中，實現物理隔離。
  - 證實針對 `None`、空白或完全沒有統一補丁標頭對 (`---` / `+++` file header pair) 的純說明文字，Evaluator 正確在 Evaluator 層分類為 `empty_response`；而對於具有 diff 意圖但格式錯誤者，依然維持為 `invalid_patch` 錯誤。
  - 證實所有測試均已同步重構，不透過任何公開屬性讀取隱藏指標。

---

## 三、 本階段 Blockers 說明

* **Blocker (已解決)**：
  人工評分欄位（`requirement_score`, `quality_score`, `api_correct`, `hallucinated_api`）在原 Schema 中為必填項目且不接受 null。當剛完成自動化評估、評估狀態仍為 `pending` 時，由於 schema 限制，系統若填入 `null` 將直接導致驗證失敗。
* **解決方式**：
  在 M3.0 中修改 `contracts/result.schema.json`。人工評分欄位在 properties 宣告中允許 `["integer", "null"]`。
  同時新增了 `if-then-else` 狀態條件約束：
  - 若 `manual_review_status` 為 `"pending"`，則四個人工評分欄位必須為 `"null"` 型別。
  - 若 `manual_review_status` 為 `"reviewed"` 或 `"disputed"`，則四個人工評分欄位必須為 `"integer"` 型別，且仍須滿足原有的 minimum/maximum 限制。
  該機制已通過全部新增的單元測試，無任何 regression。

---

## 四、 驗收連續執行兩次最新結果

### 4.1 第一輪驗收執行結果 (全專案 102 測項全綠)

#### Command
`$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

#### Output
```text
tests/contracts/test_result_schema.py::test_valid_result PASSED          [  0%]
... (略) ...
tests/m2/test_reference_patches.py::test_task_reference_patch_passes[T01] PASSED [ 49%]
... (略) ...
tests/runtime/test_evaluator_integration.py::test_all_reference_patches_success[T01] PASSED [ 57%]
... (略) ...
tests/runtime/test_patch_engine.py::test_legitimate_patch_success PASSED [ 72%]
... (略) ...
tests/runtime/test_patch_engine.py::test_hunk_header_legal_optional_heading PASSED [ 99%]
tests/runtime/test_workspace_isolation.py::test_cleanup_raises_cleanup_error PASSED [100%]

============================= 102 passed in 41.53s =============================
```

### 4.2 第二輪驗收執行結果 (全專案 102 測項全綠)

#### Command
`$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

#### Output
```text
tests/contracts/test_result_schema.py::test_valid_result PASSED          [  0%]
... (略) ...
tests/m2/test_reference_patches.py::test_task_reference_patch_passes[T01] PASSED [ 49%]
... (略) ...
tests/runtime/test_evaluator_integration.py::test_all_reference_patches_success[T01] PASSED [ 57%]
... (略) ...
tests/runtime/test_patch_engine.py::test_legitimate_patch_success PASSED [ 72%]
... (略) ...
tests/runtime/test_patch_engine.py::test_hunk_header_legal_optional_heading PASSED [ 99%]
tests/runtime/test_workspace_isolation.py::test_cleanup_raises_cleanup_error PASSED [100%]

============================= 102 passed in 24.04s =============================
```

---

## 五、 最終物理與洩漏掃描結果

* [x] **Repo root** 不存在任何 `temp_sandbox_*` 開頭目錄。
* [x] **student_system**, **evaluation**, **tests/m2**, **tests/contracts**, **tests/runtime**, **tests/leakage**, **experiments** 不存在任何 `__pycache__`、`*.pyc` 與 `.pytest_cache`。
* [x] **SNAPSHOT** 登記之 13 個起點檔案，其實體 SHA-256 哈希值與登錄檔記錄 100% 吻合，無任何污染與偏移。
