# Hermes 最小上傳包

這個資料夾是給 Hermes 使用的最小可見範圍版本。

請不要把整個 repo 丟給 Hermes。請只上傳當前 run 對應的單一資料夾。

## 使用方式

跑 `T01_A_rep01` 時，只上傳：

```text
manual_hermes_upload/T01/A/
```

跑 `T01_C_rep01` 時，只上傳：

```text
manual_hermes_upload/T01/C/
```

跑 `T01_E_rep01` 時，只上傳：

```text
manual_hermes_upload/T01/E/
```

其他題目同理：

```text
manual_hermes_upload/T02/A/
manual_hermes_upload/T02/C/
manual_hermes_upload/T02/E/
manual_hermes_upload/T03/A/
manual_hermes_upload/T03/C/
manual_hermes_upload/T03/E/
manual_hermes_upload/T04/A/
manual_hermes_upload/T04/C/
manual_hermes_upload/T04/E/
manual_hermes_upload/T05/A/
manual_hermes_upload/T05/C/
manual_hermes_upload/T05/E/
```

## 每種包裡有什麼

### A 包

- A_SoloCoder persona
- shared experiment protocol
- workspace policy
- task packet

沒有 RAG corpus。

### C 包

- C_Planner persona
- C_Coder persona
- C_Reviewer persona
- shared experiment protocol
- workspace policy
- task packet

沒有 RAG corpus。

### E 包

- E_Planner_RAG persona
- E_Coder_RAG persona
- E_Reviewer persona
- shared experiment protocol
- workspace policy
- task packet
- same-task `rag_corpus/`

只包含該題允許的 RAG corpus。

## 安全規則

- 不要上傳 `C:/上課檔案/報告/A-RAG_Multi-Agent` 整個資料夾。
- 不要上傳 `student_system/` 整包。
- 不要上傳 `evaluation/`。
- 不要上傳 `results/`。
- 不要上傳 `workspaces/`。
- 不要把 hidden test 結果貼回 Hermes。

## 重要限制

這個資料夾提供的是「物理上最小化可見資料」。

如果你只上傳單一 run 對應的資料夾，Hermes 就只能看到這包裡的檔案。

如果你把整個 repo 掛給 Hermes，文字規則不能保證它完全看不到 repo 內其他檔案。

