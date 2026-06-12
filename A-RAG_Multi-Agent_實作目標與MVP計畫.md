# A-RAG × Autonomous AI Agents 整合實驗實作計畫

## 0. 一句話目標

建立一個小型學生資訊管理系統，設計 5 題 coding tasks，分別用 **Single LLM**、**Multi-Agent**、**Multi-Agent + A-RAG** 三種方法解題，並比較 A-RAG 是否能降低 API 幻覺、提升測試通過率與需求符合度。

---

## 1. 實驗主題

**Retrieval-Augmented Multi-Agent Coding System**

本研究目標是將 **A-RAG 的階層式檢索能力** 整合進 **Planner–Coder–Reviewer 多 Agent 程式開發流程**，驗證其是否能比單一 LLM 或未整合檢索的多 Agent 架構產生更正確、更符合專案規範且更容易維護的程式碼。

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
| 主要指標 | Pass@1、Final Pass、API Correctness、Hallucinated API Rate、Code Quality、Latency |

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
  - 檢查 API 是否存在
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
| `API_SPEC.md` | 既有函式名稱、參數、回傳值與使用限制 | 避免 Coder 捏造 API |
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
| T02 | Code Generation / API Usage | 新增學生修課查詢功能，不可直接讀 raw data | `API_SPEC.md`、`student.py`、`course.py` |
| T03 | Bug Fix | 修正 GPA 計算錯誤 | `ISSUES.md`、`grade.py`、`tests/test_grade.py` |
| T04 | Bug Fix | 修正分數邊界處理錯誤，例如 0、100、負數、大於 100 | `ISSUES.md`、`utils.py`、`tests/test_grade.py` |
| T05 | Refactoring | 將重複的成績驗證邏輯抽成 `validate_score()` | `student.py`、`grade.py`、`STYLE_GUIDE.md` |

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
  "grading_notes": "不可捏造 API；必須符合 STYLE_GUIDE 的錯誤處理規範。"
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

---

## 9. A-RAG 第一版工具設計

### 9.1 `keyword_search(query)`

用途：查明確 API 名稱、函式名稱、錯誤訊息、檔名。

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
| 題目提到明確 API 名稱或函式名稱 | 先 `keyword_search`，再 `chunk_read` |
| 題目是語意需求，例如「新增及格率統計」 | 先 `semantic_search` 找相關 API 與舊程式碼 |
| 題目需要修改多個檔案 | `semantic_search` 找候選檔案，`chunk_read` 讀完整片段 |
| 檢索不到明確依據 | 要求模型說明不確定，不可捏造 API |

---

## 11. Agent 職責設計

### 11.1 Planner Agent

職責：

- 分析 coding task
- 拆解實作步驟
- 判斷需要查哪些文件、API 或既有程式碼
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
- 可能誤用 API
- 需要確認回傳格式
```

### 11.2 Coder Agent

職責：

- 根據 Planner 的步驟與 retrieved evidence 實作程式碼
- 優先使用專案中已存在的 API
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
- 檢查是否使用不存在 API
- 檢查是否符合 STYLE_GUIDE
- 檢查可讀性、重複程式碼與潛在 bug

輸出格式：

```markdown
## Reviewer Output

### Requirement Check
Pass / Fail

### API Correctness
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
- 如果不確定專案中是否存在某個 API，請明確說明不確定，不要捏造。
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
- 只能使用 evidence 中存在的 API。
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
2. 是否使用不存在的 API
3. 是否符合 STYLE_GUIDE
4. 是否有重複程式碼或潛在 bug
5. 是否需要修正

請輸出 Pass / Fail 與具體修正建議。
```

---

## 13. 評估指標

第一版先記錄以下 6 個核心指標：

| 指標 | 定義 | 計算方式 |
|---|---|---|
| Pass@1 | 第一次產生的程式是否通過 unit tests | 通過 = 1，失敗 = 0 |
| Final Pass | 允許修正 2 輪後是否通過 unit tests | 通過 = 1，失敗 = 0 |
| API Correctness | 是否正確使用專案中存在的 API | 正確 = 1，錯誤 = 0 |
| Hallucinated API | 是否捏造不存在的函式、參數或模組 | 有捏造 = 1，無捏造 = 0 |
| Code Quality | 命名、結構、重複程式碼、錯誤處理 | 人工評 1–5 |
| Latency | 每題執行時間 | 秒數 |

第二版可再加入：

- Requirement Coverage
- Maintainability
- Iteration Count
- Tool Calls
- Token Cost

---

## 14. 結果表格式

建議建立 `results/results.csv`：

| task_id | method | pass1 | final_pass | api_correct | hallucinated_api | quality_score | latency | tool_calls | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| T01 | Single LLM |  |  |  |  |  |  |  |  |
| T01 | Multi-Agent |  |  |  |  |  |  |  |  |
| T01 | Multi-Agent + A-RAG |  |  |  |  |  |  |  |  |
| T02 | Single LLM |  |  |  |  |  |  |  |  |
| T02 | Multi-Agent |  |  |  |  |  |  |  |  |
| T02 | Multi-Agent + A-RAG |  |  |  |  |  |  |  |  |

---

## 15. 預期結果

| 方法 | 預期優勢 | 可能限制 |
|---|---|---|
| Single LLM | 速度最快、系統最簡單 | 容易漏需求、捏造 API、不了解專案規範 |
| Multi-Agent | Planner 可改善需求拆解，Reviewer 可提升可讀性 | 若沒有專案文件，仍可能用錯 API |
| Multi-Agent + A-RAG | 可查 API、舊程式碼、style 與 tests，預期 API 正確率與需求符合度較高 | tool calls、延遲與 token cost 較高 |

分析時不要只看哪個方法分數最高，也要說明成本取捨：

> Multi-Agent + A-RAG 可能最可靠，但不一定最省時間。因此它適合複雜、需要專案脈絡的任務；簡單 function generation 可能 Single LLM 已足夠。

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

---

## 17. 第一週實作目標

### Day 1：建立 codebase

完成：

- `README.md`
- `API_SPEC.md`
- `STYLE_GUIDE.md`
- `ISSUES.md`
- `src/student.py`
- `src/course.py`
- `src/grade.py`
- `src/utils.py`

### Day 2：建立 tasks 與 tests

完成：

- 5 題 coding tasks
- 每題對應 pytest
- 確認原始專案可以跑測試

### Day 3：完成檢索工具

完成：

- `keyword_search`
- `semantic_search`
- `chunk_read`
- retrieved evidence log

### Day 4：完成三組方法流程

完成：

- Single LLM
- Multi-Agent
- Multi-Agent + A-RAG

### Day 5：跑實驗與整理結果

完成：

- `results.csv`
- 1 個成功案例
- 1 個失敗案例
- 初步分析

---

## 18. 第一版完成標準

完成以下條件即可算 MVP 成功：

- [ ] 有一個可執行的小型 `student_system`
- [ ] 有 5 題 coding tasks
- [ ] 每題都有 pytest
- [ ] 三組方法都能產生程式碼
- [ ] A-RAG 能記錄 retrieved evidence
- [ ] 有 `results.csv`
- [ ] 有至少 1 個成功案例與 1 個失敗案例
- [ ] 能說明 A-RAG 是否降低 API hallucination

---

## 19. 最終報告可以回答的問題

完成 MVP 後，你的報告可以回答：

1. A-RAG 是否降低 coding agent 捏造不存在 API 的情況？
2. Multi-Agent 是否比 Single LLM 更能拆解需求與修正錯誤？
3. Multi-Agent + A-RAG 是否比未檢索的 Multi-Agent 更容易通過 unit tests？
4. A-RAG 帶來的代價是什麼？例如 latency、tool calls、token cost 是否增加？
5. 對於簡單任務與複雜任務，哪一種方法比較適合？

---

## 20. 現階段不做的事情

為了避免實作範圍失控，第一版先不做：

- 不重新訓練 Transformer
- 不重新訓練 TinyLlama
- 不做 LoRA fine-tuning
- 不做大型公開 code benchmark
- 不做完整 Agile sprint simulation
- 不做完整 LLM 自主 tool-calling
- 不做 10 題以上大型任務集

這些可以放在未來工作或延伸討論。
