# Milestone 1: 專案骨架與契約 (M1 Acceptance Report)

本驗收文件詳細記錄 A-RAG × Multi-Agent 評估實驗在 Milestone 1 (M1)「專案骨架與契約」的實際產出、驗收精準修正細節、最新測試結果及後續建議。

---

## 1. 實際建立與修改之檔案清單 (Deliverables)

| 序號 | 檔案路徑 | 用途與說明 | 狀態 |
| :---: | :--- | :--- | :---: |
| **1** | `pyproject.toml` | 專案打包與依赖描述檔，宣告 Python 3.11+ 需求，定義 dev 套件與 pytest 的設定。 | 🟢 新增 |
| **2** | `README.md` | 專案快速入門與骨架導覽，提供整體專案背景、測試指令與目錄用途。 | 🟢 新增 |
| **3** | `configs/experiment.yaml` | 實驗主控參數設定，記錄策略為 A/C/E、重複 3 次、修復上限 2 輪、隨機數種子 42、及多段超時閥值。 | 🟢 新增 |
| **4** | `configs/models.yaml` | 經精簡後的模型與 API Provider 配置，僅保留未連線的本機端點 `hermes_vertex_gateway` 及其預設 `google/gemini-3.5-flash` 模型。已移除任何不符規範之其他設定。 | 🟡 已精簡 |
| **5** | `contracts/task.schema.json` | 任務合約 JSON Schema（JSON Schema Draft 2020-12）。已更新 `task_type` 支援 `api_usage`；將 `expected_behavior` 調整為非空字串陣列。在 `grading` 中，**僅保留並強制要求核心程式碼分析項目**（`required_api_symbols`、`forbidden_api_symbols`、`requirement_checks`），徹底移除靜態不合適的 weight 欄位。限制 `additionalProperties: false`。 | 🟡 已更新 |
| **6** | `contracts/result.schema.json` | 實驗結果合約 JSON Schema。已更新 `estimated_cost` 容許 `number` 或 `null`，且限制 `repair_rounds` 最大值為 2。已**移除所有非標準關鍵字**，保持完全標準的 Draft 2020-12 結構。 | 🟡 已更新 |
| **7** | `contracts/retrieval-log.schema.json` | 檢索合約 JSON Schema，記錄 Planner/Coder 調用 A-RAG 工具的精準日誌。限制 `additionalProperties: false`。 | 🟢 新增 |
| **8** | `docs/experiment-contract.md` | 實驗契約書。已依據指示修訂：隱藏測試在首次產出 patch 與每輪修復後由獨立 Evaluator 靜默執行，隱藏結果絕不流向 prompt/feedback/retrieval，以及 Prompt 範本版本化延後至 M5 實作。並增設一節明確宣告 `passed <= total` 屬於 **Runtime Invariants**（執行期不變量），由 **M3 Evaluator 程式碼層**實作與測試。 | 🟡 已更新 |
| **9** | `docs/manual-review-rubric.md` | 人工評分 Rubric，定義 `requirement_score` (0-2) 與 `quality_score` (1-5) 的盲審與分歧判定細則。 | 🟢 新增 |
| **10** | `docs/superpowers/specs/2026-06-10-arag-multi-agent-mvp-design.md` | MVP 系統設計規格書。已重構執行生命週期說明，明確寫出 Hidden tests 在首次 patch 及每輪修正後均由 evaluator 靜默執行，其結果僅限於背景靜默寫入 Metrics，完全不影響修復 feedback 與停止條件。 | 🟡 已更新 |
| **11** | `tests/contracts/test_task_schema.py` | 任務合約 Schema 的標準 Draft 2020-12 pytest 測試。新增測試：預期 `expected_behavior` 為空陣列失敗、`max_repair_rounds` 邊界失敗、以及在 `grading` 中如果寫入已移除的權重屬性會因為 `additionalProperties=false` 而驗證失敗之反例。 | 🟡 已更新 |
| **12** | `tests/contracts/test_result_schema.py` | 結果合約 Schema 的標準 Draft 2020-12 pytest 測試。**已完全移除任何非標準的 `CustomValidator` 或擴充代碼，改用標準 `Draft202012Validator`**。移除 4 個先前假裝由 JSON Schema 靜態校驗 sibling 欄位大小（`passed <= total`）的測試案例。保留了 `estimated_cost=None` (null) 的合規測試，以及 `repair_rounds > 2` 失敗等反例測試。 | 🟡 已更新 |
| **13** | `tests/contracts/test_retrieval_log_schema.py` | 檢索合約 Schema 的 pytest 測試（全正反例驗證）。 | 🟢 新增 |

---

## 2. 建立的空目錄與其狀態

為維持目錄骨架結構，並符合 M1 規範不提前實作的限制，已在以下目錄下建立 `.gitkeep` 檔案：
- `student_system/`（尚未實作學生管理系統程式庫、API、或測試）
- `evaluation/`（尚未實作評估器與 runner）
- `experiments/`（尚未實作 tasks.json 與 5 題具體實作題）
- `results/raw/`（結果日誌 raw data 目錄）
- `results/derived/`（衍生 CSV 與 Markdown 資料分析目錄）
- `results/reviews/`（人工盲審評分結果目錄）
- `workspaces/`（沙盒隔離工作區執行底層目錄）

---

## 3. 測試執行與結果 (Testing & Pass Rate)

### 3.1 測試命令
在專案根目錄下使用 Python 虛擬環境執行 pytest 命令：
```bash
python -m pytest tests/contracts -v
```

### 3.2 測試摘要
```text
============================= test session starts =============================
platform win32 -- Python 3.11.8, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\上課檔案\報告\A-RAG_Multi-Agent
configfile: pyproject.toml
collected 27 items

tests/contracts/test_result_schema.py::test_valid_result PASSED          [  3%]
tests/contracts/test_result_schema.py::test_valid_result_estimated_cost_null PASSED [  7%]
tests/contracts/test_result_schema.py::test_missing_required_fields PASSED [ 11%]
tests/contracts/test_result_schema.py::test_invalid_task_id_pattern PASSED [ 14%]
tests/contracts/test_result_schema.py::test_invalid_strategy_enum PASSED [ 18%]
tests/contracts/test_result_schema.py::test_invalid_error_type_enum PASSED [ 22%]
tests/contracts/test_result_schema.py::test_invalid_stop_reason_enum PASSED [ 25%]
tests/contracts/test_result_schema.py::test_invalid_manual_review_status_enum PASSED [ 29%]
tests/contracts/test_result_schema.py::test_requirement_score_out_of_range PASSED [ 33%]
tests/contracts/test_result_schema.py::test_quality_score_out_of_range PASSED [ 37%]
tests/contracts/test_result_schema.py::test_additional_properties_forbidden PASSED [ 40%]
tests/contracts/test_result_schema.py::test_repair_rounds_greater_than_two_fails PASSED [ 44%]
tests/contracts/test_retrieval_log_schema.py::test_valid_log PASSED      [ 48%]
tests/contracts/test_retrieval_log_schema.py::test_missing_required_fields PASSED [ 51%]
tests/contracts/test_retrieval_log_schema.py::test_invalid_task_id_pattern PASSED [ 55%]
tests/contracts/test_retrieval_log_schema.py::test_invalid_tool_name_enum PASSED [ 59%]
tests/contracts/test_retrieval_log_schema.py::test_invalid_types PASSED  [ 62%]
tests/contracts/test_retrieval_log_schema.py::test_additional_properties_forbidden PASSED [ 66%]
tests/contracts/test_task_schema.py::test_valid_task PASSED              [ 70%]
tests/contracts/test_task_schema.py::test_missing_required_fields PASSED [ 74%]
tests/contracts/test_task_schema.py::test_invalid_task_id_pattern PASSED [ 77%]
tests/contracts/test_task_schema.py::test_invalid_enums PASSED           [ 81%]
tests/contracts/test_task_schema.py::test_invalid_types PASSED           [ 85%]
tests/contracts/test_task_schema.py::test_additional_properties_forbidden PASSED [ 88%]
tests/contracts/test_task_schema.py::test_expected_behavior_empty_array_fails PASSED [ 92%]
tests/contracts/test_task_schema.py::test_limits_max_repair_rounds_out_of_bounds PASSED [ 96%]
tests/contracts/test_task_schema.py::test_grading_weights_forbidden_by_additional_properties PASSED [100%]

============================= 27 passed in 0.61s ==============================
```
**通過率為 100% (27/27 PASSED)**，證明了三個 JSON Schema 完全符合修正後的標準 Draft 2020-12 規範。

---

## 4. 本次驗收精準修正與偏離說明 (Deviations & Fixes)

- **針對非標準關鍵字之修正**：
  1. 徹底移除先前在 `result.schema.json` 中非標準的自訂關鍵字 `passed_cannot_exceed_total`，還原為完全標準的 JSON Schema。
  2. 徹底移除 `test_result_schema.py` 中的 `CustomValidator`、`validators.extend` 及對應的動態 Python 校驗程式碼。
  3. 將 `passed <= total` 一致性校驗正式宣告為 **Evaluator/Runtime Invariant**，寫入 `docs/experiment-contract.md` 契約，明確指明該不變量交由 **M3 Evaluator 程式碼層**實作與自動化測試。
  4. 刪除 4 個先前在 M1 中假裝由標準 Schema 校驗 passed <= total 的測試案例，使測試套件完全回歸標準 Draft 2020-12 規範。
- **針對 grading 結構與 additionalProperties 之修正**：
  1. 調整 `task.schema.json` 中 `grading` 結構：**只保留核心程式碼分析項目**（`required_api_symbols`、`forbidden_api_symbols`、`requirement_checks`），徹底移除靜態 weights 欄位。
  2. 藉由 `additionalProperties=false` 的嚴格特性，新增單元測試 `test_grading_weights_forbidden_by_additional_properties`：若在 `grading` 中寫入已遭移除的 weight 欄位時，必須被標準 Validator 拒絕並拋出 `ValidationError` 失敗。
- **系統規格文檔之修訂**：
  1. 調整 `docs/superpowers/specs/2026-06-10-arag-multi-agent-mvp-design.md`，說明 Hidden tests 在首次產出 patch 與每輪修復後皆會被靜默執行，其結果僅限背景 Metrics 記錄，完全不作為 feedback 回饋或修正終止判斷。
- **標準驗證器查核**：
  - 經驗證，三份 schema 在載入時，皆已嚴格執行標準驗證器之語法與格式查核：
    ```python
    Draft202012Validator.check_schema(schema_data)
    ```
- **無功能外溢**：本階段專注於契約與 Schema 的精準修正，無任何 student system 或 evaluator 執行代碼被提前實作。
- **無 Git 異動**：遵照不自行 `git init` 或 `commit` 的規定。

---

## 5. 已知限制與未來 M2-M6 邊界 (Known Limits & Boundaries)

- **無執行期模型、Provider、Strategy**：當前不支援發送模型請求，不具備 A/C/E 策略之代碼組裝。
- **無 Student System 實作**：`student_system` 目錄此時全空，無具體 API 與公開測試。
- **無網路或 Secret 金鑰存儲**：設定檔未含、亦不支援任何 Vertex AI 的 API 金鑰或網路連線。
- **Hidden Tests 未納入 Index**：已於 `docs/experiment-contract.md` 確立 hidden tests 僅在 evaluator runtime 可被讀取，完全隔離於 index 與 prompt 之外，防止資料外洩。

---

## 6. 建議 (Recommendation)

精準修正版 Milestone 1 之專案骨架、合約、模型精簡及 Schema 自動化 pytest 均已完成，並在所有層面完全回歸標準的 JSON Schema Draft 2020-12 Validator。此回報結果確認完全無功能外溢與偏離。建議准許進入 Milestone 2 (M2)。
