# Hermes 手動 Agent 套件

這個資料夾定義手動 workflow-level evaluation 要使用的 7 個固定 agent 模板。

本實驗目前比較三種受控 Hermes 工作流程：

| 策略 | Agent 數 | RAG 權限 | 主要差異 |
|---|---:|---|---|
| A | 1 | 無 | 單一 agent 直接寫 patch |
| C | 3 | 無 | Planner / Coder / Reviewer 分工 |
| E | 3 | Planner 與 Coder 可用 | 多代理流程加上受控 RAG |

> B / D 暫時保留給未來消融實驗，不在目前手動主流程中使用。

## Agent 模板

1. [A_SoloCoder](01_A_SoloCoder.md)
2. [C_Planner](02_C_Planner.md)
3. [C_Coder](03_C_Coder.md)
4. [C_Reviewer](04_C_Reviewer.md)
5. [E_Planner_RAG](05_E_Planner_RAG.md)
6. [E_Coder_RAG](06_E_Coder_RAG.md)
7. [E_Reviewer](07_E_Reviewer.md)

## 共用文件

- [共同實驗規則](00_shared_experiment_protocol.md)
- [工作路徑與檔案權限規則](workspace_policy.md)
- [操作員檢查表](operator_checklist.md)
- [單筆 run 紀錄模板](run_record_template.md)
- [RAG 紀錄模板](rag_log_template.md)

## 建議收集資料夾結構

```text
manual_runs/
  T01/
    T01_A_rep01.md
    T01_A_rep02.md
    T01_A_rep03.md
    T01_C_rep01.md
    T01_C_rep02.md
    T01_C_rep03.md
    T01_E_rep01.md
    T01_E_rep02.md
    T01_E_rep03.md
  T02/
  T03/
  T04/
  T05/
```

## 不可違反的規則

- 不可以把 hidden test 結果貼給 Hermes。
- 不可以使用 reference patches。
- 不可以讀取或修改工作區規則禁止的路徑。
- 不可以在 Hermes 輸出 patch 後，由操作員手動幫它改好。
- 每一次 repetition 都要開新 session。
- A 和 C 不可以使用 RAG。
- E 只能使用該 task 批准的 corpus。
- 每一筆 run 都要保留足夠紀錄，之後才能整理統計與報告。
