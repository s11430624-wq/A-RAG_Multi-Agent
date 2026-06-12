# A-RAG × Multi-Agent MVP 系統設計規格書

本設計規格書描述 **A-RAG (Retrieval-Augmented Generation for APIs and Codebase)** 與 **Planner–Coder–Reviewer 多 Agent 協同架構** 整合實驗的最小可行性產品（MVP）系統設計。

---

## 1. 系統架構圖 (System Architecture)

```text
                                +---------------------------+
                                |      Coding Task          |
                                +---------------------------+
                                              |
                                              v
                                +---------------------------+
                                |      Planner Agent        | <---+
                                +---------------------------+     |
                                              |                   |
                                              v                   |
                                +---------------------------+     |
                                |   A-RAG Retrieval Layer   |     |
                                |  - keyword_search         |     |
                                |  - semantic_search        |     |
                                |  - chunk_read             |     |
                                +---------------------------+     | (自我修復迴圈)
                                              |                   | max_repair_rounds=2
                                              v                   |
                                +---------------------------+     |
                                |       Coder Agent         |     |
                                +---------------------------+     |
                                              |                   |
                                              v                   |
                                +---------------------------+     |
                                |      Reviewer Agent       |     |
                                +---------------------------+     |
                                              |                   |
                                              v                   |
                                +---------------------------+     |
                                |    Evaluator Runtime      | ----+
                                | (Pytest, Sandboxed Run)   |
                                +---------------------------+
                                              |
                                              v
                                +---------------------------+
                                |    Experiment Results     |
                                |     (Append-only JSONL)   |
                                +---------------------------+
```

---

## 2. 元件職責與合約行為 (Component Responsibilities)

### 2.1 Planner Agent
- **輸入**：任務描述（`task_description`）、可用檔案列表。
- **職責**：
  - 深度解構 Coding Task 之核心需求與隱性邊界。
  - 明確規劃出所需查核的專案文檔與現有原始碼檔案（輸出為 RAG 的候選查詢方向）。
  - 將複雜任務拆解為結構化的「逐步實作指南」（Implementation Plan）。
- **輸出**：包含「需求理解」、「預期查核清單」、「實作步驟」、「潛在風險」之 Markdown 計畫。

### 2.2 A-RAG 檢检索層 (Retrieval Layer)
提供階層式檢索機制，僅在 Strategy E (Multi-Agent + A-RAG) 中對 Agent 開放：
- **`keyword_search(query)`**：針對 API 名稱、明確函式、錯誤代碼或檔案路徑進行字串精確/模糊匹配，快速定位。
- **`semantic_search(query, top_k)`**：將自然語言需求轉換為語意向量，計算與專案文檔 chunks 之間之餘弦相似度（Cosine Similarity），找尋概念相近的既有實作或風格規範。
- **`chunk_read(file_path, chunk_id)`**：讀取指定文件之特定區塊或代碼區段，提供模型完整、高精確度之上下文，避免單純 RAG 碎片化上下文的問題。

### 2.3 Coder Agent
- **輸入**：任務描述、Planner 計畫、A-RAG 檢索所得 chunks。
- **職責**：
  - 嚴格遵循 Planner 的實作指引與 A-RAG 提供的 `API_SPEC.md` / 代碼上下文。
  - 編寫精確的程式碼，並只能使用系統中確實存在的 API，不憑空捏造。
- **輸出**：待修改檔案之 `unified diff`。

### 2.4 Reviewer Agent
- **輸入**：任務描述、A-RAG 檢索 chunks、Coder 的產出代碼。
- **職責**：
  - 比對產出代碼與 A-RAG 文檔，檢查是否使用了不合規的 API（API Correctness 與 Hallucination 審查）。
  - 對照 `STYLE_GUIDE.md` 評估代碼風格與例外處理完善度。
- **輸出**：`Pass / Fail` 狀態與細部修正建議。

### 2.5 驗算器與執行環境 (Evaluator Runtime)
- **職責**：
  - 在完全乾淨、隔離的虛擬沙盒工作區（Workspace）中解封 Starter Snapshot，套用 Coder 產出的 `unified diff`。
  - 執行 **Public Unit Tests**（反饋給自我修復迴圈）與 **Hidden Unit Tests**。
  - **靜默執行規範**：Hidden Tests 在首次產生 patch 之後與每輪修復修正之後，皆由 Evaluator Runtime 在背景靜默執行。其結果僅限於背景靜默記錄於指標（Metrics）中，絕對不影響 Agent 流程的回饋（Feedback）、修復提示词、或終止修復條件之判斷。

---

## 3. 實驗資料流設計 (Data Flow & Life Cycle)

1. **Intake**：讀取 `configs/experiment.yaml` 與 `configs/models.yaml`，載入題庫 `experiments/tasks.json`。
2. **Setup**：針對特定 Task 與 Repetition，建立乾淨的 sandbox workspace，將 `student_system` 初始化至該 workspace。
3. **Execution Loop**：
   - 根據當前策略（A、C 或 E）路由執行。
   - 策略 E 下，Planner 與 Coder 均可調用 A-RAG 工具，其調用歷程必須完整寫入符合 `retrieval-log.schema.json` 規範之記錄中。
4. **Validation & Self-Repair (最多 2 輪)**：
   - 每次產生 patch 或修正後，Evaluator 靜默執行 Hidden Tests，並捕獲 Public Tests。
   - 若沙盒內 pytest 執行 Public Tests 失敗，且當前修復輪數（`repair_rounds`）小於 2：
     - 將 Public 測試輸出（`pytest` stdout 錯誤訊息）與當前程式碼，反饋給 Coder 進行修復，`repair_rounds` 遞增。
   - 若 Public Tests 全部通過，或已達修復上限，則終止修復迴圈。
5. **Final Recording & Persistence**：
   - 最終由 Evaluator 校驗跨欄位執行期不變量（如 `passed <= total`），確保數據正確。
   - 產生符合 `result.schema.json` 規範之單次 Run 結果，追加寫入 `results/raw/results.jsonl`（append-only）。
   - 清理或封存 Workspace。
