# Milestone 7-E.7 Controlled Abort Audit Report

## 1. Experiment Overview & Execution Status

- **Experiment ID:** `m7e_full_20260611T230000Z`
- **Execution Status:** **Controlled Abort**
- **Failed Run ID:** `m7e_full_20260611T230000Z__T01__E__rep02__seed42`
- **Abort Reason:** `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted`
- **Final 45-run Completeness Statement:** **Explicit Statement: The final 45-run dataset is NOT complete.**

---

## 2. Raw JSONL & Artifact Metadata

- **Raw JSONL Path:** `results/raw/m7e_full_20260611T230000Z.jsonl`
- **Raw SHA-256 Hash:** `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7`
- **Completed Records Count:** `7`
- **Completed Records Distribution:** `A=3, C=3, E=1`
- **Task Distribution:** `T01=7`
- **Run Status Summary:** `valid_run=7`, `infra_error=0`
- **Resource Usage:**
  - `input_tokens=51674`
  - `output_tokens=52522`
  - `tool_calls: A=0, C=0, E=2`
  - `retrieved_tokens: A=0, C=0, E=34`
- **Stop Reason:** `repair_limit=7`
- **Patch Apply Failures Total:** `7`

---

## 3. Corrected Call & Attempt Metrics

Following critical corrections of previous misreported values, the official metrics are updated and validated as follows:

- **Finalized Manifest Count:** `7`
- **Finalized provider_attempt_count sum:** `31`
- **Finalized call_records sum:** `31`
- **Failed Run Attempts:** `unknown` (failed E rep02 attempts are not finalized in the manifest and cannot be accurately summed unless a separate durable runner log exists)
- **Retrieval Logs:**
  - **E rep01 completed log:** 2 lines / 34 tokens (aligns perfectly with completed raw record)
  - **E rep02 partial log:** 2 lines / 34 tokens, with no completed raw record (partial audit artifact)

---

## 4. Diagnostics, Outputs & Hashes Consistency

- **Diagnostics Count:** `0`
  - *Reason:* No diagnostics folder was generated for this experiment.
- **Derived Outputs:** **Absent** (no derived output files exist for this experiment run).
- **Frozen Smoke Hashes:** **Unchanged** (M7-D smoke outputs remain completely frozen and untampered).
- **Old Partial Results Hash:** **Unchanged** (the historical `m7e_full_20260611T210000Z` partial results hash remains unchanged and fully preserved).

---

## 5. Read-Only Consistency Validation (唯讀一致性驗證)

A strict read-only audit of the physical environment has verified the following invariants:

1. **Raw JSONL Integrity:** Every line of `results/raw/m7e_full_20260611T230000Z.jsonl` is strictly schema-valid.
2. **Artifact Directories:** All `7` artifact_path directories physically exist.
3. **Manifest Files:** All manifest artifact_files exist and their actual file hashes match the manifest records.
4. **Retrieval Logs Isolation:** Retrieval logs for strategies A and C are entirely absent.
5. **E rep01 Match:** The retrieval log for E rep01 matches and aligns perfectly with the completed raw record.
6. **E rep02 Partial Status:** The retrieval log for E rep02 is confirmed as a partial audit artifact.
7. **No Diagnostics Residue:** No diagnostics folder or files exist for this experiment.
8. **No Derived Outputs:** Verified that no derived output files were written.
9. **Clean Workspace:** No temporary `workspace/`, `cache/`, or `temp/` residue remains in the repository.
