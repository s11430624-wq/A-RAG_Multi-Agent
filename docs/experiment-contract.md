# A-RAG × Multi-Agent 實驗契約 (Experiment Contract)

本文件定義 A-RAG Multi-Agent 評估實驗之核心控制契約，旨在確保 **Strategy A (Single LLM)**、**Strategy C (Multi-Agent)**、以及 **Strategy E (Multi-Agent + A-RAG)** 三組實驗之公平性、不可外洩性（No Leakage）、可重現性（Reproducibility）與資料完整性（Data Integrity）。

---

## 一、 控制變因與一致性原則 (Control Variables)

1. **模型與參數一致性**：
   - 實驗中所有策略（A, C, E）在相同任務上必須使用完全相同的底層大語言模型（預設為 `google/gemini-3.5-flash`）。
   - 模型推論之溫度參數（Temperature）統一固定為 `0.0`，`top_p` 統一固定為 `0.95`，以最大程度消除隨機性對生成品質的影響。
2. **任務與程式庫起點一致**：
   - 每一題 Task 均使用相同的需求描述、限定修改檔案與起點程式庫（Starter Snapshot）。
3. **測試與修正上限一致**：
   - 所有組別皆使用同一套公開單元測試（Public Unit Tests）作為修復依據。
   - 所有組別之最大自我修復輪數（`max_repair_rounds`）皆統一限制為最多 **2 輪**（即最多執行兩次修復）。

---

## 二、 比較策略定義 (Strategy Definition)

- **Strategy A (Single LLM)**:
  - 單一模型基準線。直接將任務描述與 `starter_files` 內容提供給 LLM，模型不具備多 Agent 角色拆解、亦不具備任何專案檢索（No Retrieval）能力。
- **Strategy C (Multi-Agent)**:
  - 多 Agent 基準線。採用 **Planner–Coder–Reviewer** 協同流程：
    - **Planner**：分析需求並輸出實作步驟。
    - **Coder**：根據 Planner 步驟實作並產生程式碼變更。
    - **Reviewer**：檢查 Coder 輸出是否滿足需求與編碼規範。
  - 此策略**不具備任何檢索機制**，所有決策僅依賴任務給定資訊與模型內建知識。
- **Strategy E (Multi-Agent + A-RAG)**:
  - 本實驗之整合方法。採用與 Strategy C 完全相同之 Planner–Coder–Reviewer 協作流程。
  - **唯一差異**：Agent 流程在規劃或實作時，可調用 A-RAG 檢索層（`keyword_search`、`semantic_search`、`chunk_read`）自 `allowed_corpus`（限定語料庫）中檢索專案規範、API 設計與現有實作。

---

## 三、 測試隔離與防外洩原則 (No Leakage)

1. **隱藏測試 (Hidden Tests) 隔離**：
   - 隱藏測試之內容、測試名稱、預期輸出等任何資訊，**絕對禁止**以任何形式流向以下位置：
     - Prompt 內容
     - RAG 檢索索引（Index/Embedding）
     - 模型快取（Cache）
     - 實驗中間摘要或最終產出物（Artifacts/Summaries）
   - 隱藏測試結果（如具體失敗原因、斷言詳情等）僅作為評估指標（Metrics）靜默記錄，**絕對禁止**回流（Feedback）給 Agent 流程或用於任何修復決策。
2. **無跨 Run 回流**：
   - 每一次 Run 均為獨立事件，先前 Run 的結果、產生的程式碼、或修正歷程，**絕對禁止**作為後續 Run 或其他 Repetition 的 Context。

---

## 四、 執行環境隔離 (Sandbox Isolation)

1. **獨立工作區 (Workspace)**：
   - 每次實驗 Run 啟動時，必須從乾淨的 Starter Repository Snapshot 建立一個完全隔離、獨立的實體 Workspace 目錄。
   - 所有檔案修改、測試執行、錯誤訊息收集，皆限制在該獨立 Workspace 中進行。執行完畢後，Workspace 應被封存或於重新實驗時重建，避免殘留狀態污染其他 Run。

---

## 五、 自我修復與反饋策略 (Self-Repair Policy)

1. **反饋訊號與修復限制**：
   - 僅允許 **Public Unit Test** 的執行反饋（如失敗的測試名稱、Assertion Error 訊息）用於觸發修復流程。
   - 隱藏測試（Hidden Tests）在首次產生 patch 之後與每輪修正之後，由獨立的驗算器（Evaluator Runtime）在背景**靜默執行**。
   - 隱藏測試的細節對 Agent 策略而言是**完全不可見**的，且隱藏測試的成功與否絕不可用於判斷是否需要繼續修復，其結果僅限於背景評估計分與寫入 Metrics。
2. **終止修正條件**：
   - 當 **Public Unit Tests 全部通過** 時，系統必須立即**停止修正**並結束執行。
   - 最多允許 **2 輪** 的自我修復（即 `Pass@1 -> 測試失敗 -> 修復第1輪 -> 測試失敗 -> 修復第2輪 -> 結束`）。

---

## 六、 輸出格式與資料保存規範 (Artifact Standards)

1. **統一 Diff 格式**：
   - 所有三組策略在修改程式碼時，必須統一輸出 `unified diff` 格式，以確保程式碼修改的精確度、可讀性，並便於 Reviewer Agent 與本機 Diff 工具解析。
2. **append-only 原始日誌**：
   - 實驗的原始記錄（Run-by-Run）必須以 **append-only JSONL** 格式（即每行一筆符合 `result.schema.json` 規範的 JSON）寫入 `results/raw/` 目錄。
   - 任何彙整表格（如 CSV、Markdown Summary）皆必須由該原始 JSONL 檔案自動化衍生，禁止人工手動修改 CSV 內容，以確保實驗數據可審計性。
3. **Prompt 範本版本化**：
   - 所有 Agent（Planner, Coder, Reviewer）之 Prompt 範本於 **M5** 實作後必須進行版本管理，並於實驗記錄中記錄其 `SHA-256` 雜湊值（Hash），確保提示詞工程（Prompt Engineering）的可追溯性。

---

## 七、 執行期不變量約束 (Runtime Invariants)

由於標準 JSON Schema Draft 2020-12 規格並不支援在 sibling 欄位之間進行數值大小比較（例如：無法在 schema 靜態定義中校驗 `passed <= total`），因此此類實驗數據的一致性校驗被明確定義為 **Evaluator/Runtime Invariants**：
- **一致性不變量**：`public_tests_passed <= public_tests_total` 且 `hidden_tests_passed <= hidden_tests_total`；且 `pass1` 階段的對應通過數亦不得大於總數。
- **實作與測試歸屬**：此不變量校驗在 **Milestone 3 (M3) Evaluator** 中實作。在寫入原始 `result.schema.json` 日誌或在儲存前，由 M3 評估器程式進行動態斷言與測試，確保落庫資料的一致性與品質。
