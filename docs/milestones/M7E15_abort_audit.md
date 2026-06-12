# Milestone 7-E.15 Controlled Abort Audit Report

## 1. 執行狀態與生命週期 (Execution Status & Lifecycle)
- **最終狀態 (Execution Status):** Controlled Abort (受控中斷)
- **最終 45-run 狀態 (Final 45-run Complete):** **否 (NOT Complete)**。本實驗於完成 15 個 Run 後，在第 16 個 Run 觸發檢索預算超限而受控中斷，保留 15 個已完成的完整紀錄，不進行自動 resume、不重跑。

## 2. 失敗 Run 資訊與中斷原因 (Failed Run & Abort Reason)
- **失敗 Run ID (Failed Run ID):** `m7e_full_20260612T020000Z__T02__E__rep01__seed42`
- **中斷原因 (Abort Reason):** `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted`
- **詳細事證 (Evidence):**
  - 本次實驗中已實施 Milestone 7-E.13 的 **Retrieval Loop Hardening** (檢索硬化政策)。
  - 於 `T02__E__rep01` 中，Planner 發起並執行了 **3 次相異檢索**：
    1. `keyword_search("get_student_course_summary")` 成功 (52 tokens)
    2. `keyword_search("get_grades_by_student")` 成功 (28 tokens)
    3. `keyword_search("get_student_by_id")` 成功 (37 tokens)
  - 由於策略 E 的 Planner 初始檢索預算已由 2 放寬至 3，前 3 次檢索成功扣減預算，此時剩餘檢索預算為 0。
  - 當 Planner 企圖發起 **第 4 次相異檢索** 時，即刻觸發 `RetrievalBudgetExceededError` 預算超額阻斷，系統依據 A-RAG 政策執行 **Controlled Abort** 安全停機。
  - 該失敗的 Run 被拒絕並標記為 `infra_error`，不寫入最終 raw JSONL，不產生任何不完整的 `manifest.json` 與成果檔，確保產物無污染 (Fail-Closed Invariant)。

## 3. 實體產物審計與雜湊 (Raw JSONL Audit & Hashes)
- **Raw JSONL 路徑:** `results/raw/m7e_full_20260612T020000Z.jsonl`
- **Raw JSONL SHA-256 雜湊值:** `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456`
- **完成紀錄筆數 (Total Completed Records Count):** **15 筆**
- **已完成紀錄分布 (Completed Records Distribution):**
  - **策略分布 (Strategy Distribution):** `A=6`, `C=6`, `E=3`
  - **題目分布 (Task Distribution):** `T01=9` (A=3, C=3, E=3), `T02=6` (A=3, C=3, E=0)
  - **細項表列:**
    1. `T01__A__rep01` (valid_run=true, stop_reason=repair_limit)
    2. `T01__A__rep02` (valid_run=true, stop_reason=repair_limit)
    3. `T01__A__rep03` (valid_run=true, stop_reason=repair_limit)
    4. `T01__C__rep01` (valid_run=true, stop_reason=repair_limit)
    5. `T01__C__rep02` (valid_run=true, stop_reason=repair_limit)
    6. `T01__C__rep03` (valid_run=true, stop_reason=repair_limit)
    7. `T01__E__rep01` (valid_run=true, stop_reason=repair_limit, retrieved_tokens=34)
    8. `T01__E__rep02` (valid_run=true, stop_reason=repair_limit, retrieved_tokens=34)
    9. `T01__E__rep03` (valid_run=true, stop_reason=repair_limit, retrieved_tokens=34)
    10. `T02__A__rep01` (valid_run=true, stop_reason=repair_limit)
    11. `T02__A__rep02` (valid_run=true, stop_reason=public_pass, public_tests=2/2, hidden_tests=2/2)
    12. `T02__A__rep03` (valid_run=true, stop_reason=repair_limit)
    13. `T02__C__rep01` (valid_run=true, stop_reason=repair_limit)
    14. `T02__C__rep02` (valid_run=true, stop_reason=repair_limit)
    15. `T02__C__rep03` (valid_run=true, stop_reason=repair_limit)

- **物理執行指標匯總:**
  - `valid_run` = 15
  - `infra_error` = 0 (在 JSONL 檔案中)
  - `Total input_tokens` = 124,742 tokens
  - `Total output_tokens` = 113,844 tokens
  - `Total retrieved_tokens` = 102 tokens (於 JSONL 中)
  - `Total tool_calls` = 6 calls (於 JSONL 中)

## 4. Finalized 產物與 Provider Attempts 統計
- **Finalized Manifest Count:** **15** (對應 15 筆已寫入 JSONL 且成功保存的 Completed runs)
- **Finalized provider_attempt_count sum (總 Provider 嘗試次數):** **68**
- **Finalized call_records sum (總呼叫紀錄數):** **68**
- **Failed Run (T02 E rep01) Attempts:** 未確認且未 Finalize (由於 `T02__E__rep01` 執行失敗，其 manifest 並未寫入，attempts 次數屬於未 finalize 狀態)

## 5. 檢索日誌審計 (Retrieval Logs Audit)
檢索日誌共 **4 個**，具備完美的策略 E 隔離性 (A/C組無檢索日誌)：
1. **E completed logs (對應已完成的 JSONL 紀錄):**
   - `m7e_full_20260612T020000Z__T01__E__rep01__seed42.jsonl` (2 lines / 34 tokens)
   - `m7e_full_20260612T020000Z__T01__E__rep02__seed42.jsonl` (2 lines / 34 tokens)
   - `m7e_full_20260612T020000Z__T01__E__rep03__seed42.jsonl` (2 lines / 34 tokens)
2. **E partial log (失敗 Run 的殘留審計產物，無對應 Completed raw record):**
   - `m7e_full_20260612T020000Z__T02__E__rep01__seed42.jsonl` (3 lines / 117 tokens)

## 6. 診斷與衍生分析產物 (Diagnostics & Derived Outputs)
- **Diagnostics Count:** **0**
  - *原因:* 本次為典型的 Controlled Abort，執行器並未為本次實驗生成診斷資料夾 (No diagnostics folder for this experiment)。
- **Derived Outputs:** **無 (Absent)**
  - *原因:* 根據安全原則，在發生 Controlled Abort 且 45-run 尚未完全完成時，嚴禁生成任何 Derived Outputs (如 `.csv` 檔案或 `_summary.md` 摘要)。

## 7. 殘留與唯讀一致性驗證 (Residue & Read-Only Consistency Validation)
- **Workspace Residue Scan:** 100% 乾淨。整個 `workspaces/m7e_full_20260612T020000Z` 目錄在執行完成後已完全清除，未留任何暫存殘留物。
- **唯讀一致性驗證:**
  - 所有 15 個 `artifact_path` 資料夾皆確實存在。
  - 所有 `manifest.json` 聲明的檔案皆確實存在，且雜湊值 100% 一致。
  - 策略 A/C 的檢索日誌確實皆不存在，檢索日誌僅在 E 組生成，隔離性完整。

## 8. Frozen Historical Hashes Recheck (已凍結歷史檔案雜湊核對)
重新計算實體檔案的 SHA-256 雜湊值，確認 100% 毫無變更、未受任何干涉：
1. `results/raw/gates/m7d_smoke_20260611T123000Z.json`
   - 雜湊值: `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` (與凍結宣告一致)
2. `results/raw/m7d_smoke_20260611T123000Z.jsonl`
   - 雜湊值: `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` (與凍結宣告一致)
3. `results/raw/m7e_full_20260611T210000Z.jsonl`
   - 雜湊值: `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` (與凍結宣告一致)
4. `results/raw/m7e_full_20260611T230000Z.jsonl`
   - 雜湊值: `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` (與凍結宣告一致)
5. `results/raw/m7e_full_20260612T010000Z.jsonl`
   - 雜湊值: `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` (與凍結宣告一致)

## 9. 政策執行合規確認 (Compliance Confirmation)
- **No Resume of Old IDs:** 本次執行確實沒有 resume 任何舊的實驗 ID (如 `20260611T210000Z`、`20260611T230000Z`、`20260612T010000Z`)。
- **No Fake/Scripted Provider:** 本次執行確實使用了真實的 Gateway API，未啟用 fake/scripted 模擬提供者，且沒有讀取/洩漏任何 plaintext 憑證。
- **No Mutation of Frozen Outputs:** 未修改、未覆寫、未更動任何已凍結之歷史實驗與門禁檔案。
- **Derived Outputs Absent:** 確實沒有產生衍生 `.csv` 與摘要報告。
