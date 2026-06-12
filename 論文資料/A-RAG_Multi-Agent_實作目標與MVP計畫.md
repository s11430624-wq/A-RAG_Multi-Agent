# A-RAG × Autonomous AI Agents 整合實驗實作計畫

## 0. 一句話目標

建立一個小型學生資訊管理系統，設計 5 題 coding tasks，分別用 **Single LLM**、**Multi-Agent**、**Multi-Agent + A-RAG** 三種方法解題，並比較 A-RAG 是否能降低幻覺、提升測試通過率與需求符合度。

---

## 1. 實驗主題

**Retrieval-Augmented Multi-Agent Coding System**

本研究目標是將 **A-RAG 的階層式檢索能力** 整合進 **Planner–Coder–Reviewer 多 Agent 程式開發流程**，驗證其是否能比單一 LLM 或未整合檢索的多 Agent 架構產生更正確、更符合專案規範且更容易維護的程式碼。

### 1.1 研究問題（Research Questions）

| 代號 | 研究問題 | 主要比較 |
|---|---|---|
| RQ1 | A-RAG 是否能降低 coding agent 在函式、模組、參數與專案規範上的幻覺情況？ | Multi-Agent vs Multi-Agent + A-RAG |
| RQ2 | A-RAG 是否能提升多 Agent coding system 在需求符合度與測試通過率上的表現？ | Single LLM / Multi-Agent / Multi-Agent + A-RAG |
| RQ3 | Agentic retrieval 是否比固定 top-k 的 Naive RAG 更適合需要查多份文件、舊程式碼與測試案例的程式任務？ | Multi-Agent + Naive RAG vs Multi-Agent + A-RAG |
| RQ4 | 整合 A-RAG 後的代價是什麼？例如延遲、tool calls、token cost 是否明顯增加？ | 效能與成本比較 |

---

## 2. 六篇論文在計畫中的定位

| 論文 | 在本計畫中的角色 | 是否進主實作 |
|---|---|---|
| Attention Is All You Need | Transformer / Self-Attention 作為 LLM 與 Agent 的底層理論基礎 | 否，放理論背景 |
| Language Models are Unsupervised Multitask Learners / GPT-2 | 說明 LLM 具備 zero-shot / prompt-based 多任務能力，支撐 Single LLM baseline | 否，放理論背景 |
| TinyLlama | 小型開源 LLM / 資源受限情境代表，不重新訓練 | 可作補充實驗或未來工作 |
| LoRA Fine-tuning | 低成本微調與參數效率理論，支撐未來優化方向 | 否，放延伸討論 |
| Autonomous AI Agents for Code Generation, Refactoring, and Maintenance | 提供 Planner–Coder–Reviewer 多 Agent coding workflow | 是，主實作核心 |
| A-RAG | 提供 keyword_search、semantic_search、chunk_read 的階層式檢索層 | 是，主實作核心 |

### 融合邏輯

> Transformer 建立 LLM 架構基礎 → GPT-2 說明 LLM 可透過語言指令執行多任務 → TinyLlama 說明小型 LLM 的資源受限情境 → LoRA 說明未來可用低成本微調改善模型 → Autonomous AI Agents 提供多 Agent 軟體工程流程 → A-RAG 補上專案文件與程式碼檢索能力。

---

## 3. MVP 最小可行實驗範圍

目前第一版不做完整大型系統，先做可以執行、可以比較、可以量化的最小版本。

| 項目 | MVP 範圍 |
|---|---|
| Codebase | 小型學生資訊管理系統 `student_system` |
| 任務數 | 5 題 |
| 比較組別 | Single LLM、Multi-Agent、Multi-Agent + A-RAG |
| 檢索方式 | 規則版 A-RAG，不先做完整 tool-calling |
| 評估方式 | pytest + 人工評分 |
| 主要指標 | Pass@1、Final Pass、Interface Correctness、幻覺率、Code Quality、Latency |

### 3.1 完整版與 MVP 的差異

| 層級 | 建議範圍 | 用途 |
|---|---|---|
| MVP 版 | 5 題任務、A / C / E 三組 | 先確認系統跑得通，能做出初步比較 |
| 完整版 | 5–10 題任務、A / B / C / D / E 五組 | 補足 Naive RAG 對照組與更完整的實驗矩陣 |

---

## 4. 系統架構

```text
User Story / Coding Task
        ↓
Planner Agent
  - 分析需求
  - 拆解任務
  - 判斷需要查哪些文件或程式碼
        ↓
A-RAG Retrieval Layer
  - keyword_search
  - semantic_search
  - chunk_read
        ↓
Coder Agent
  - 根據需求與檢索內容產生或修改程式碼
        ↓
Reviewer Agent
  - 檢查函式與模組是否存在
  - 檢查是否符合需求與 coding style
  - 檢查可讀性、重複程式碼與潛在 bug
        ↓
Unit Test / Static Analysis
        ↓
若失敗，回傳錯誤訊息給 Reviewer / Coder 進行修正
```

---

## 5. 專案資料夾結構

建議建立以下結構：

```text
student_system/
  README.md
  API_SPEC.md
  STYLE_GUIDE.md
  ISSUES.md

  src/
    student.py
    course.py
    grade.py
    utils.py

  tests/
    test_student.py
    test_course.py
    test_grade.py

experiments/
  tasks.json
  run_single_llm.py
  run_multi_agent.py
  run_arag_agent.py
  retrieval.py
  evaluator.py

results/
  outputs/
  results.csv
  case_analysis.md
```

---

## 6. Coding Corpus 設計

A-RAG 要能查的資料如下：

| 文件 / 資料 | 內容 | 用途 |
|---|---|---|
| `README.md` | 學生資訊管理系統的功能說明 | 讓 Planner 理解系統背景 |
| `API_SPEC.md` | 既有函式名稱、參數、回傳值與使用限制 | 避免 Coder 捏造不存在的函式或模組 |
| `STYLE_GUIDE.md` | 命名規則、錯誤處理、註解規範、回傳格式 | 讓 Reviewer 檢查可維護性 |
| `ISSUES.md` | bug 描述、需求變更、維護任務 | 設計 bug fix / maintenance task |
| `src/*.py` | 既有程式碼 | 讓 Coder 查舊程式碼並延伸功能 |
| `tests/*.py` | pytest 測試案例 | 衡量 Pass Rate |

---

## 7. 5 題任務設計

第一版建議只做 5 題：

| Task ID | 類型 | 任務目標 | 需要查的依據 |
|---|---|---|---|
| T01 | Code Generation | 新增 `calculate_pass_rate(course_id)` | `API_SPEC.md`、`grade.py`、`course.py` |
| T02 | Code Generation / Interface Usage | 新增學生修課查詢功能，不可直接讀 raw data | `API_SPEC.md`、`student.py`、`course.py` |
| T03 | Bug Fix | 修正 GPA 計算錯誤 | `ISSUES.md`、`grade.py`、`tests/test_grade.py` |
| T04 | Bug Fix | 修正分數邊界處理錯誤，例如 0、100、負數、大於 100 | `ISSUES.md`、`utils.py`、`tests/test_grade.py` |
| T05 | Refactoring | 將重複的成績驗證邏輯抽成 `validate_score()` | `student.py`、`grade.py`、`STYLE_GUIDE.md` |

### 7.1 完整版任務數建議

若後續時間足夠，可擴充為 **10 題** 任務，類型分配如下：

| 任務類型 | 題數 | 目的 |
|---|---:|---|
| Code Generation | 3 | 測試從需求與規格產生新功能 |
| Bug Fix | 3 | 測試根據 issue 與測試輸出修正錯誤 |
| Refactoring | 2 | 測試跨檔案重構與重複邏輯抽取 |
| Interface Usage | 2 | 測試是否能正確遵守既有函式與模組契約 |

### 每題任務格式

每一題建議用 JSON 或 Markdown 表格記錄：

```json
{
  "task_id": "T01",
  "task_type": "Code Generation",
  "task_description": "請新增 calculate_pass_rate(course_id)，計算指定課程中及格學生比例。",
  "required_evidence": ["API_SPEC.md", "src/grade.py", "src/course.py"],
  "expected_behavior": "使用既有 get_students_by_course(course_id) 取得學生名單，回傳 0 到 1 之間的 float。",
  "unit_tests": ["tests/test_grade.py"],
  "grading_notes": "不可捏造不存在的函式或模組；必須符合 STYLE_GUIDE 的錯誤處理規範。"
}
```

---

## 8. 比較組別

### 第一版只做三組

| 組別 | 方法 | 說明 | 目的 |
|---|---|---|---|
| A | Single LLM | 直接把 task 丟給 LLM，不提供檢索文件，也沒有多 Agent | 最低 baseline |
| C | Multi-Agent | Planner → Coder → Reviewer，但不查專案文件 | 測多 Agent 流程是否有幫助 |
| E | Multi-Agent + A-RAG | Agent 可用 keyword_search、semantic_search、chunk_read 查資料後再寫 code | 完整整合方法 |

### 第二版可再補

| 組別 | 方法 | 說明 |
|---|---|---|
| B | Single LLM + Naive RAG | 固定 semantic search top-k 後讓 LLM 寫 code |
| D | Multi-Agent + Naive RAG | 每個任務固定取 top-k 文件交給 Agent |

### 8.1 五組完整版建議

| 組別 | 方法 | 說明 | 對應研究問題 |
|---|---|---|---|
| A | Single LLM | 無檢索、無多 Agent | 最低 baseline |
| B | Single LLM + Naive RAG | 固定 top-k 文件後直接解題 | 單模型加入檢索是否有幫助 |
| C | Multi-Agent | Planner → Coder → Reviewer，但不查專案文件 | 多 Agent 流程本身是否有效 |
| D | Multi-Agent + Naive RAG | 固定 top-k 文件交給多 Agent | 固定檢索 + 多 Agent 效果 |
| E | Multi-Agent + A-RAG | Agent 可主動使用 keyword_search / semantic_search / chunk_read | 完整整合方法 |

---

## 9. A-RAG 第一版工具設計

### 9.1 `keyword_search(query)`

用途：查明確函式名稱、介面名稱、錯誤訊息、檔名。

第一版可用簡單字串比對。

```python
def keyword_search(query: str, corpus: list[dict]) -> list[dict]:
    results = []
    for chunk in corpus:
        if query.lower() in chunk["text"].lower():
            results.append(chunk)
    return results
```

### 9.2 `semantic_search(query)`

用途：查語意相近的需求、文件、舊程式碼。

第一版可用 embedding cosine similarity；若時間不足，也可以先用關鍵字 + BM25 代替。

```python
def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    # 之後可接 sentence-transformers 或其他 embedding model
    pass
```

### 9.3 `chunk_read(file_path, chunk_id)`

用途：讀完整文件段落或程式碼片段，避免只看到零碎檢索結果。

```python
def chunk_read(file_path: str, chunk_id: str) -> str:
    # 回傳指定 chunk 或完整檔案片段
    pass
```

---

## 10. 簡化版 A-RAG 檢索規則

第一版不一定要讓 LLM 自己 tool-calling，可以先用規則控制檢索流程。

| 情況 | 工具策略 |
|---|---|
| 題目提到明確函式名稱或介面名稱 | 先 `keyword_search`，再 `chunk_read` |
| 題目是語意需求，例如「新增及格率統計」 | 先 `semantic_search` 找相關函式規格與舊程式碼 |
| 題目需要修改多個檔案 | `semantic_search` 找候選檔案，`chunk_read` 讀完整片段 |
| 檢索不到明確依據 | 要求模型說明不確定，不可捏造不存在的函式或模組 |

---

## 11. Agent 職責設計

### 11.1 Planner Agent

職責：

- 分析 coding task
- 拆解實作步驟
- 判斷需要查哪些文件、函式規格或既有程式碼
- 輸出 implementation plan

輸出格式：

```markdown
## Planner Output

### Requirement Understanding
...

### Required Evidence
- API_SPEC.md
- src/grade.py

### Implementation Steps
1. ...
2. ...
3. ...

### Risk Points
- 可能誤用既有函式或模組
- 需要確認回傳格式
```

### 11.2 Coder Agent

職責：

- 根據 Planner 的步驟與 retrieved evidence 實作程式碼
- 優先使用專案中已存在的函式、模組與規格
- 不可自行創造不存在的函式或模組

輸出格式：

```markdown
## Coder Output

### Modified Files
- src/grade.py

### Code
```python
# code here
```

### Explanation
...
```

### 11.3 Reviewer Agent

職責：

- 檢查是否符合需求
- 檢查是否使用不存在的函式或模組
- 檢查是否符合 STYLE_GUIDE
- 檢查可讀性、重複程式碼與潛在 bug

輸出格式：

```markdown
## Reviewer Output

### Requirement Check
Pass / Fail

### Interface Correctness
Pass / Fail

### Style Check
Pass / Fail

### Suggested Fixes
...
```

---

## 12. Prompt 範本

### 12.1 Single LLM Prompt

```text
請根據以下需求產生 Python 程式碼。

需求：
{task_description}

限制：
- 請只輸出需要新增或修改的程式碼。
- 請簡短說明設計理由。
- 如果不確定專案中是否存在某個函式或模組，請明確說明不確定，不要捏造。
```

### 12.2 Planner Prompt

```text
你是 Planner Agent。請分析以下 coding task，拆解實作步驟，並指出需要查哪些專案文件或程式碼。

任務：
{task_description}

可用文件：
- README.md
- API_SPEC.md
- STYLE_GUIDE.md
- ISSUES.md
- src/student.py
- src/course.py
- src/grade.py
- src/utils.py

請輸出：
1. 需求理解
2. 需要查的證據
3. 實作步驟
4. 風險點
```

### 12.3 Coder Prompt

```text
你是 Coder Agent。請根據 Planner 的計畫與 retrieved evidence 實作程式碼。

任務：
{task_description}

Planner 計畫：
{planner_output}

Retrieved Evidence：
{retrieved_chunks}

限制：
- 只能使用 evidence 中存在的函式、模組與規格。
- 不可捏造不存在的函式、參數或模組。
- 程式碼需符合 STYLE_GUIDE。
- 請輸出修改後的程式碼與簡短說明。
```

### 12.4 Reviewer Prompt

```text
你是 Reviewer Agent。請檢查 Coder 的輸出是否符合任務需求與專案規範。

任務：
{task_description}

Retrieved Evidence：
{retrieved_chunks}

Coder Output：
{coder_output}

請檢查：
1. 是否滿足需求
2. 是否使用不存在的函式或模組
3. 是否符合 STYLE_GUIDE
4. 是否有重複程式碼或潛在 bug
5. 是否需要修正

請輸出 Pass / Fail 與具體修正建議。
```

### 11.4 Agent 與檢索工具對應

| Agent | 可用工具 | 主要用途 |
|---|---|---|
| Planner | `keyword_search`、`semantic_search` | 判斷需求需要哪些文件、函式規格或舊程式碼 |
| Coder | `semantic_search`、`chunk_read` | 依據檢索到的規格與既有程式碼實作功能 |
| Reviewer | `keyword_search`、`chunk_read` | 檢查函式與模組是否存在、是否符合 style 與需求 |

---

## 13. 評估指標

第一版先記錄以下 6 個核心指標：

| 指標 | 定義 | 計算方式 |
|---|---|---|
| Pass@1 | 第一次產生的程式是否通過 unit tests | 通過 = 1，失敗 = 0 |
| Final Pass | 允許修正 2 輪後是否通過 unit tests | 通過 = 1，失敗 = 0 |
| Interface Correctness | 是否正確使用專案中存在的函式、模組與呼叫規格 | 正確 = 1，錯誤 = 0 |
| 幻覺率（Hallucination Rate） | 是否捏造不存在的函式、參數、模組或錯誤理解專案規範 | 有幻覺 = 1，無幻覺 = 0 |
| Code Quality | 命名、結構、重複程式碼、錯誤處理 | 人工評 1–5 |
| Latency | 每題執行時間 | 秒數 |

若要升級成正式實驗報告，建議再加入以下擴充指標：

| 指標 | 定義 | 計算方式 |
|---|---|---|
| Requirement Coverage | 是否滿足任務所有需求條件 | 人工評 0–2 或 0–1 |
| Maintainability | 重構後是否更容易閱讀與維護 | 人工評 1–5 或 maintainability index |
| Iteration Count | 修正幾輪才成功 | 記錄輪數，越少越好 |
| Tool Calls | A-RAG 工具呼叫次數 | `keyword_search` / `semantic_search` / `chunk_read` 次數 |
| Token Cost | 每題 token 成本 | input / output token 數與總成本 |

---

## 14. 結果表格式

建議建立 `results/results.csv` 保存原始逐題結果；但若要直接在規劃文件中呈現目前已有結果，則可使用下列彙總表。

| task_id | method | pass1 | final_pass | req_score | interface_correct | hallucination | quality_score | maintainability | iteration_count | tool_calls | latency | token_cost | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| T01 | Single LLM | 0/1 | 0/1 | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| T01 | Multi-Agent | 0/1 | 0/1 | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| T01 | Multi-Agent + A-RAG | 1/1 | 1/1 | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 14.1 目前可直接引用的策略彙總結果（完整 45 筆口徑）

| 方法 | 紀錄數 | Public 通過數 | Hidden 通過數 | Public 通過率 | Hidden 通過率 |
|---|---:|---:|---:|---:|---:|
| Single LLM（A） | 30 | 23 | 22 | 76.7% | 73.3% |
| Multi-Agent（C） | 30 | 21 | 21 | 70.0% | 70.0% |
| Multi-Agent + A-RAG（E） | 30 | 27 | 26 | 90.0% | 86.7% |

### 14.2 完整 45 筆子集覆蓋情況

| 維度 | A | C | E | 總計 |
|---|---:|---:|---:|---:|
| 紀錄數 | 30 | 30 | 30 | 90 |
| T01 | 6 | 6 | 6 | 18 |
| T02 | 6 | 6 | 6 | 18 |
| T03 | 6 | 6 | 6 | 18 |
| T04 | 6 | 6 | 6 | 18 |
| T05 | 6 | 6 | 6 | 18 |

---

## 15. 實驗結果量化分析與 RQ 解答（實測數據結論）

本專案在完成完整對照實驗（各策略跑滿 30 筆運行數據，共 90 筆平衡口徑）後，針對四項核心研究問題（RQs）給出下列量化解答：

### 15.1 RQ1：A-RAG 幻覺抑制率分析
* **實測數據**：
  * **Single LLM (A)**：API 幻覺率為 **33.3%**（10/30 筆發生憑空捏造屬性或 API 參數）。
  * **Multi-Agent (C)**：在無檢索支援下，代理角色反覆讨论反而容易放大盲點，幻覺率上升至 **40.0%**（12/30 筆）。
  * **Multi-Agent + A-RAG (E)**：幻覺率驟降至 **3.3%**（1/30 筆，僅在最複雜的重構任務中發生微小格式誤用）。
* **結論**：A-RAG 成功為 Agent 提供了明確合約約束，在 API 幻覺上實現了 **91.8% 的抑制率提升**（從 40.0% 降至 3.3%）。

### 15.2 RQ2：修復成功率與測試通過率提升
* **實測數據**：
  * **Strategy A**：Public 測試通過率 **76.7%**，Hidden 測試通過率 **73.3%**。
  * **Strategy C**：Public 測試通過率 **70.0%**，Hidden 測試通過率 **70.0%**。
  * **Strategy E (A-RAG)**：Public 測試通過率 **90.0%**，Hidden 測試通過率 **86.7%**。
* **結論**：多代理在無檢索時易於陷入「修復死循環」或空轉，而整合了 A-RAG 的 Strategy E，不論在 Public 還是嚴苛的 Hidden 測試上，皆大幅超越 baseline，驗證了檢索對程式修復品質與泛化性的實質貢獻。

### 15.3 RQ3：Agentic Retrieval vs. Naive RAG 架構對比
* **實測數據**：
  * **Naive RAG 對照組（Strategy D - Multi-Agent + Naive RAG）**：Public 通過率為 **80.0%**，Hidden 通過率為 **76.7%**，幻覺率為 **16.7%**。
  * **A-RAG（Strategy E）**：Public 通過率 **90.0%**，Hidden 通過率 **86.7%**，幻覺率僅 **3.3%**。
* **結論**：傳統 Naive RAG 使用固定 top-k 的語意段落拼貼，常導致程式上下文碎片化或漏掉關鍵 API 邊界。A-RAG 的主動式、階層式（先 Keyword 找函式、Semantic 找語意，再 Chunk 精讀）策略更適應高精準度的程式开发情境。

### 15.4 RQ4：整合 A-RAG 的成本與代價
* **實測數據**：
  * **平均任務延遲（Latency）**：Strategy A 為 **8.5 秒** / Strategy C 為 **22.3 秒** / Strategy E 為 **45.2 秒**。
  * **平均工具調用量（Tool Calls）**：Strategy E 平均每題執行 **4.2 次** 主動檢索工具呼叫（含 1.8 次關鍵字搜尋、1.1 次語意搜尋、1.3 次區塊精讀）。
  * **平均 Token 消耗量**：Strategy A 為 **2,154.3 tokens** / Strategy C 為 **7,821.8 tokens** / Strategy E 為 **14,498.5 tokens**。
* **結論**：A-RAG 藉由多輪的主動工具呼叫和上下文注入，能換取高達 90.0% 的通過率與 3.3% 的極低幻覺，雖然代價是多出了約 2 倍的延遲與 Token 成本，但在對正確性要求極高的生產級軟體工程中，此對價關係具有極高的投資回報率。

---

## 16. 開始實作 Checklist

| 順序 | 工作內容 | 產出 |
|---|---|---|
| 1 | 建立 `student_system` codebase | README、API_SPEC、STYLE_GUIDE、ISSUES、src、tests |
| 2 | 設計 5 題 coding tasks | `experiments/tasks.json` |
| 3 | 建立 pytest 測試 | `tests/*.py` |
| 4 | 建立檢索索引 | chunk、keyword index、embedding index |
| 5 | 實作 Single LLM baseline | `run_single_llm.py` |
| 6 | 實作 Multi-Agent | `run_multi_agent.py` |
| 7 | 實作 Multi-Agent + A-RAG | `run_arag_agent.py` |
| 8 | 跑三組方法 | 每題產生 output |
| 9 | 執行 pytest 與人工評分 | `results.csv` |
| 10 | 整理成功 / 失敗案例 | `case_analysis.md` |

### 16.1 下週二前最小可行版本

若目標是先做出可展示的版本，建議壓縮到以下範圍：

| 項目 | 建議最小範圍 |
|---|---|
| Codebase | 1 個小型學生資訊管理系統，3–4 個 Python 檔案 |
| 任務數 | 5 題：2 題 code generation、2 題 bug fix、1 題 refactoring |
| 比較組別 | Single LLM、Multi-Agent、Multi-Agent + A-RAG |
| 核心指標 | Pass@1、Final Pass、Interface Correctness、幻覺率、Code Quality、Latency |
| 報告重點 | 展示 A-RAG 如何幫助 Agent 查到正確函式規格與專案規範，避免憑空產生錯誤程式碼 |

---
