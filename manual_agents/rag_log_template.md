# RAG 紀錄模板

這份模板只給 Strategy E 使用。

A 和 C 不允許使用 RAG；如果是 A 或 C，請在 run record 裡寫：

```text
RAG not allowed; no RAG used.
```

## RAG 摘要

- rag_enabled: true
- roles_with_rag_access: E_Planner_RAG, E_Coder_RAG
- roles_without_rag_access: E_Reviewer
- total_queries:
- retrieved_files:
- retrieved_tokens_or_estimate:
- rag_used_in_final_patch: true / false

## Query 紀錄

### Query 1

- role:
- phase: initial / repair_1 / repair_2
- query:
- reason:
- result_files:
- excerpts:
- evidence_id:
- used_in_final_patch: true / false

### Query 2

- role:
- phase:
- query:
- reason:
- result_files:
- excerpts:
- evidence_id:
- used_in_final_patch: true / false

## 禁止來源檢查

確認以下來源都沒有被使用：

- hidden tests: yes / no
- reference patches: yes / no
- previous results: yes / no
- previous runs: yes / no
- web search: yes / no

如果任何一項是 `yes`，這筆 run 應標記為 invalid，並在 notes 說明原因。

