# A-RAG × Autonomous AI Agents 整合實驗最終報告（草稿）

## 摘要

本專案完成一套可重現、可稽核且具安全隔離能力的多策略程式修復評估平台，用於比較：

1. Strategy A：單一模型；
2. Strategy C：Planner–Coder–Reviewer 多代理流程；
3. Strategy E：整合受控檢索的 Planner–Coder–Reviewer 流程。

系統涵蓋結果契約、隔離工作區、交易式補丁、公開與隱藏測試執行、檢索權限、Provider 抽象、策略編排、實驗排程、結果持久化、人工盲評及 live Gateway 安全閘門。最終非 hidden 回歸測試為：

```text
594 passed, 2 skipped
```

本專案成功完成工程平台與端到端 live 執行驗證，但正式 45-run 比較實驗未形成完整且可用於策略效能推論的資料集。最終執行在完成 15 筆後，因 Strategy E active run 的非正常 token 累積觸發全域 input-token 預算，系統依 fail-closed 原則中止。基於樣本不完整、任務覆蓋不足及策略執行異常，本報告不對 A、C、E 的相對效能做統計結論。

## 1. 研究問題

本專案原先希望回答：

- 多代理分工是否能提高程式修復成功率？
- 受控檢索是否能降低 API 幻覺與錯誤實作？
- A-RAG 是否能在不洩漏隱藏測試或參考答案的前提下提供有效證據？

為避免將系統錯誤誤認為模型表現，本研究先建立具備完整隔離、稽核及失敗分類能力的評估環境，再進行策略比較。

## 2. 系統架構

### 2.1 契約層

- 使用 JSON Schema 驗證 task、result 與 retrieval log。
- Pending manual review 狀態下，人工評分欄位必須為 `null`。
- Reviewed/disputed 狀態必須具備完整且符合範圍的評分。

### 2.2 Runtime 與安全隔離

- 每次 run 建立獨立暫存 workspace。
- 以 SHA-256 驗證輸入 snapshot。
- 阻擋 absolute path、`..`、symlink/junction escape 與 sibling-prefix escape。
- 執行後驗證僅允許指定檔案發生變更。
- 測試逾時時僅終止目標 process tree。

### 2.3 Patch Engine

- 嚴格解析 unified diff。
- 拒絕 rename、binary diff、`/dev/null`、重複 section、錯誤 hunk count 與 context mismatch。
- 多檔案補丁採交易式寫入；任一檔案失敗則完整 rollback。

### 2.4 Retrieval Layer

- 只有 Strategy E 可建立 retrieval session。
- Planner、Coder、Reviewer 使用 role-bound session。
- Corpus 由 snapshot allowlist 建立，拒絕 hidden tests、reference patches、results 與 cache。
- 支援 keyword search、deterministic semantic search 與 chunk read。
- Retrieval log 採 append-only、canonical JSONL 與角色 provenance。

### 2.5 Provider 與 Strategies

- OpenAI-compatible Provider 使用 injected transport。
- Provider attempts、usage、latency、finish reason 與 request ID 均可稽核。
- Strategy A、C、E 使用固定且可測試的角色流程。
- Evidence 依 run、task、role、phase 隔離。
- Artifact bundle 採 write-once manifest 與完整 SHA-256。

### 2.6 Experiment Runner

- 建立 deterministic 45-run scheduler。
- Raw result JSONL 採 append-only、schema validation、fsync 與 duplicate run guard。
- 支援 resume validation，但禁止混合不同實驗契約。
- Derived CSV/summary 僅能由完整且有效的 raw results 產生。

### 2.7 Live Safety

- 僅允許 `http://127.0.0.1:8787/v1` no-auth loopback Gateway。
- 禁止 Authorization header、環境代理、redirect 與跨 origin request。
- Live probe 驗證 model、usage、request ID、finish reason 與 seed。
- 支援 Gemini reasoning-token normalization。
- Full run 必須綁定 frozen smoke report hash 與人工批准。
- 429 使用 bounded Retry-After、共享 request pacing 與全域 attempt budget。

## 3. 驗證結果

### 3.1 自動化測試

```text
Non-hidden regression:
594 passed, 2 skipped
```

兩項 skip 為預設不執行的真實 live 測試。離線測試不讀取 credential、不建立 socket，並以 injected fake transport 驗證 live boundaries。

### 3.2 Smoke 驗證

M7-D 執行 T01 × A/C/E 共 3 runs：

```text
records=3
valid_run=3
infra_error=0
automated_gate_passed=true
provider_calls=16
input_tokens=28782
output_tokens=22390
```

Strategy A/C 無 retrieval log；Strategy E 產生合法 retrieval log。Smoke report、raw JSONL、artifact manifest set 與 retrieval log set 均已雜湊凍結。

### 3.3 正式執行狀態

最終實驗 ID：

```text
m7e_full_20260612T050000Z
```

執行結果：

```text
completed records=15/45
schema-valid records=15
infra_error records=0
completed input tokens=112868
completed output tokens=103045
finalized provider attempts=62
artifact manifests=15
artifact hash errors=0
```

執行在 `T02 / Strategy E / repetition 1` 中止：

```text
BudgetExceededError: Input token budget exceeded
```

失敗 run 未寫入 completed record，亦未產生 derived CSV 或 summary。

## 4. 為何不使用目前資料比較 A/C/E

現有正式資料不符合有效策略比較的最低條件：

1. 僅完成 15/45 runs。
2. 只涵蓋完整 T01 與部分 T02，未涵蓋 T03–T05。
3. Strategy 樣本數不平衡：A=6、C=6、E=3。
4. Strategy E 的 active run 出現非正常 token 累積。
5. 失敗 active run 的 call records 在 rollback 後不可用，無法完整重建其 token 軌跡。
6. 多次歷史 partial run 使用不同階段的策略與預算政策，不可合併為同一資料集。

因此，現有 pass count 僅作內部診斷，不作研究成效：

```text
A: 2/6
C: 0/6
E: 0/3
```

上述數值不得解讀為 Strategy A 優於 C/E，也不得用於統計推論。

## 5. 重要發現

### 5.1 評估平台能可靠拒絕無效結果

系統在 patch、retrieval、Provider、budget、artifact 與 result-writing 邊界均採 fail-closed。未完成 run 不會被偽裝為成功資料，這使失敗原因能被辨識，而不會污染最終結果。

### 5.2 多代理流程目前未達 live 比較穩定度

正式執行暴露出：

- 大量模型 diff 無法通過 strict patch application；
- C/E 的額外角色呼叫未轉化為較高測試通過率；
- Strategy E 對重複 cached retrieval request 缺乏明確 role-turn 上限；
- active run 失敗時，durable diagnostic 未保存完整 usage/call records。

### 5.3 正常 completed runs 並未接近 token 上限

15 筆 completed runs 平均約為：

```text
input tokens/run ≈ 7525
```

依此規模，45 筆約需 339k input tokens，低於 1M 上限。預算中止較可能來自單一 Strategy E active run 的異常循環，而非正常 45-run 成本。

## 6. 限制與效度威脅

- 正式樣本不完整，無法回答原始效能研究問題。
- 只有單一模型、單一 seed 與單一本地 Gateway。
- Token normalization 依賴 Vertex/Gemini 特定 usage 格式。
- Strict unified diff 能提高可稽核性，但也可能放大模型格式錯誤。
- Hidden tests 雖與策略隔離，但 evaluator integration 未包含在最終 non-hidden regression 指令中。
- Live active-run rollback 會移除未 finalized call artifacts，降低失敗根因可觀測性。

## 7. 可交付成果

本專案可交付並可驗證的成果為：

1. 完整的多策略程式修復評估平台。
2. 具交易性與路徑隔離的 patch/runtime engine。
3. 具 role/phase provenance 的受控 retrieval layer。
4. Provider-neutral agent strategy 與 artifact audit。
5. 可重現 scheduler、raw result writer 與 approval-gated live runner。
6. Frozen smoke dataset 與多份 controlled-abort audit。
7. 594 個通過的 non-hidden 自動化測試。

## 8. 結論

本研究完成了安全、可重現且可稽核的 A-RAG 多代理評估基礎設施，並證明該系統能在模型輸出、Gateway、retrieval loop 或 budget 發生異常時保護資料完整性。

然而，現階段 live strategies 尚未達到可進行公平 A/C/E 比較的穩定度，正式 45-run 資料集亦未完成。因此，本研究的有效結論限於工程平台與失敗分析；不宣稱 A-RAG 已改善程式修復成功率，也不以目前 partial pass count 評定策略優劣。

後續若重新進行效能實驗，應先加入 role-turn/cached-request 上限、保存 failed-run usage audit，並以小型 canary 證明 patch apply rate 與 token 行為穩定後，再使用全新實驗 ID 執行完整比較。
