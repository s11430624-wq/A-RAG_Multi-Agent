# Workspace Policy

這份文件規定 Hermes agent 在手動實驗中可以讀哪裡、可以改哪裡、不能碰哪裡。

## Repository Root

所有 run 都以這個專案根目錄為工作根目錄：

```text
C:/上課檔案/報告/A-RAG_Multi-Agent
```

Agent 不應該要求讀取或修改此目錄外的任何檔案。

## 可讀取範圍

所有策略都可以讀：

- 當題 `manual_task_packets/Txx/task_packet.md` 內提供的 task 內容。
- 當題 starter code 內容。
- 操作員貼上的 public test feedback。
- 該 agent 自己的 persona。
- `manual_agents/00_shared_experiment_protocol.md`
- `manual_agents/workspace_policy.md`

只有 Strategy E 可以額外讀：

- 當題對應的 `manual_rag_corpus/Txx/`

例如：

```text
T01_E 只能讀 manual_rag_corpus/T01/
T02_E 只能讀 manual_rag_corpus/T02/
```

## 可修改範圍

Agent 只能輸出 patch 修改 task packet 中 `Files To Modify` 列出的檔案。

目前五題的可修改檔案如下：

| Task | 可修改檔案 |
|---|---|
| T01 | `student_system/src/grade.py` |
| T02 | `student_system/src/student.py` |
| T03 | `student_system/src/grade.py` |
| T04 | `student_system/src/utils.py` |
| T05 | `student_system/src/utils.py`, `student_system/src/student.py`, `student_system/src/grade.py` |

如果 patch 修改了表格外的檔案，該 run 應標記為 invalid，除非操作員明確判定那是格式誤差且未實際採用。

## 禁止讀取或引用的路徑

所有策略都禁止讀取、引用、推測或要求操作員貼出以下路徑：

```text
evaluation/hidden_tests/
evaluation/reference_patches/
results/
workspaces/
.git/
__pycache__/
.pytest_cache/
```

也禁止讀：

- 其他 strategy 的 run record。
- 其他 repetition 的 run record。
- 舊的 live-run / smoke-run outputs。
- hidden test output。
- reference solution 或 reference patch。
- 任意 repo 外部檔案。

## Strategy 專屬限制

### Strategy A

- 只能使用 `manual_task_packets/Txx/task_packet.md`。
- 不可以使用 `manual_rag_corpus/`。
- 不可以詢問 C/E 組 agent。

### Strategy C

- 只能使用 `manual_task_packets/Txx/task_packet.md`。
- 不可以使用 `manual_rag_corpus/`。
- C 組只包含 C_Planner、C_Coder、C_Reviewer。
- 不可以詢問 A/E 組 agent。

### Strategy E

- 可以使用 `manual_task_packets/Txx/task_packet.md`。
- 可以使用同題的 `manual_rag_corpus/Txx/`。
- 不可以使用其他題目的 `manual_rag_corpus/`。
- E 組只包含 E_Planner_RAG、E_Coder_RAG、E_Reviewer。
- 不可以詢問 A/C 組 agent。

## Public Test 與 Hidden Test

操作員可以執行 public tests，並把 public feedback 貼回 agent。

操作員只能在 final patch 產生後執行 hidden tests。hidden result 只能寫入 run record，不可以貼回 Hermes。

## Patch 要求

Patch 必須符合：

- 只修改允許檔案。
- 優先使用 unified diff。
- 不新增測試檔。
- 不新增 hidden/reference/result/workspace 相關檔案。
- 不硬編碼 public test 的答案。
- 不讀取 raw private database，除非 task 明確允許。

