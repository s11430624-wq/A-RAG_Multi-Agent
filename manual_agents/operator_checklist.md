# 操作員檢查表

每一筆手動 run 都用這份檢查表。它的目的不是增加麻煩，而是避免 45 筆跑到一半時資料污染、漏記或策略混淆。

## 開始一筆 run 之前

- [ ] 已確認 task 正確。
- [ ] 已確認 strategy 正確：A / C / E。
- [ ] 已確認 repetition 編號正確。
- [ ] 已開啟全新 session。
- [ ] prompt 裡沒有 hidden test 資訊。
- [ ] prompt 裡沒有 reference patch。
- [ ] prompt 裡沒有其他策略或其他 repetition 的結果。
- [ ] 已列出允許修改的檔案。
- [ ] 已確認本 run 遵守 `manual_agents/workspace_policy.md`。
- [ ] 已列出 public test command。
- [ ] 如果是 E 組，已列出 allowed RAG corpus。

## run 進行中

- [ ] 不手動修改 agent 產出的 patch。
- [ ] 不摘要、不透露 hidden test 行為。
- [ ] repair prompt 只貼 public feedback。
- [ ] repair rounds 沒有超過設定上限。
- [ ] agent 沒有要求讀取 forbidden paths。
- [ ] patch 沒有修改 `files_to_modify` 之外的檔案。
- [ ] 如果是 E 組，已記錄每一次 RAG query。
- [ ] 已確認 A / C 完全沒有使用 RAG。

## final evaluation 之前

- [ ] final patch 已保存。
- [ ] public test result 已記錄。
- [ ] 如果是 E 組，RAG log 已完整記錄。
- [ ] stop_reason 已記錄。
- [ ] hidden result 沒有回饋給 Hermes。

## final evaluation 之後

- [ ] hidden result 已記錄到 run record。
- [ ] evaluator result 欄位已記錄。
- [ ] 若有任何規則違反，已明確記錄。
- [ ] run file 已用標準命名保存：

```text
manual_runs/<TASK_ID>/<TASK_ID>_<STRATEGY>_rep<NN>.md
```

範例：

```text
manual_runs/T01/T01_E_rep02.md
```
