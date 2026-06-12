# Milestone 7-E.11 Abort Audit: Real Final Full Rerun Controlled Abort Report

**Status:** Controlled Abort / Partial Results Preserved / Final Dataset Not Complete

---

## 1. Execution Status & Overview

- **Milestone Target:** M7-E.11 Real Final Full Rerun Execution
- **Execution Status:** **Controlled Abort** (Fail-Closed triggered)
- **Status Statement:** **M7-E.11 final 45-run is not complete.** The execution was intentionally aborted mid-way by the retrieval budget controls. No completed records were lost; exactly 15 completed, schema-valid, and tested runs were safely preserved.
- **Full Experiment ID:** `m7e_full_20260612T010000Z`
- **Failed Run ID:** `m7e_full_20260612T010000Z__T02__E__rep01__seed42`
- **Abort Reason:** `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted` (Planner attempted a 4th retrieval query during initial phase, exceeding Option B's budget threshold of 3).
- **Raw JSONL Path:** `results/raw/m7e_full_20260612T010000Z.jsonl`
- **Raw JSONL SHA-256:** `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a`
- **Completed Record Count:** 15

---

## 2. Corrected Metrics & Distribution

### Finalized Records Metrics (15 Runs Completed)
- **Strategy Distribution:** Strategy A = 6, Strategy C = 6, Strategy E = 3
- **Task Distribution:** 
  - Task T01 = 9 (Strategy A = 3, Strategy C = 3, Strategy E = 3)
  - Task T02 = 6 (Strategy A = 3, Strategy C = 3, Strategy E = 0)
- **Success Metrics:**
  - `valid_run` = 15
  - `infra_error` = 0 (only finalized, clean runs are recorded in JSONL; the aborted run is safely discarded)
- **Public/Hidden Pass Summary:**
  - Run `m7e_full_20260612T010000Z__T02__A__rep02__seed42` successfully passed all public and hidden test cases (2/2 public and 2/2 hidden).
  - All other 14 runs reached the repair limit (or stopped otherwise) and did not pass.
- **Resource Usage (Finalized 15 Runs):**
  - **Completed Input Tokens:** 123,715 tokens
  - **Completed Output Tokens:** 105,385 tokens

### Call Records & Provider Attempts
- **Finalized Artifact Manifests Count:** 15
- **Finalized `provider_attempt_count` Sum:** 68 (summed over the 15 finalized manifests)
- **Finalized `call_records` Count Sum:** 68 (summed over the 15 finalized manifests)
- **Failed Run Attempts:** **unknown / not finalized** (Since the failed run aborted before writing its finalized manifest to disk, its exact provider attempt count is not recorded in the durable finalized artifact bundle).

### Retrieval Logs Status
- **Strategy A / C:** No retrieval logs generated (as per strategy specifications, retrieval is 0).
- **Strategy E:** 
  - `m7e_full_20260612T010000Z__T01__E__rep01__seed42.jsonl`: Completed (3 lines / 51 tokens).
  - `m7e_full_20260612T010000Z__T01__E__rep02__seed42.jsonl`: Completed (2 lines / 34 tokens).
  - `m7e_full_20260612T010000Z__T01__E__rep03__seed42.jsonl`: Completed (2 lines / 34 tokens).
  - `m7e_full_20260612T010000Z__T02__E__rep01__seed42.jsonl`: **Partial / In-Progress Audit Artifact** (3 lines, 0 tokens, no completed raw record). Exists on disk, but has no corresponding completed raw JSONL record. This represents the captured evidence of the aborted run.

---

## 3. Read-Only Consistency Validation

An automated validation check was performed over the workspace, confirming 100% data integrity and correctness:

| Verification Item | Check Description | Result |
| :--- | :--- | :--- |
| **Raw JSONL Schema Validity** | Every line of the raw JSONL file matches `contracts/result.schema.json`. | **PASSED** (Validated via jsonschema) |
| **Artifact Paths Existence** | All 15 `artifact_path` pointers listed in the JSONL exist physically. | **PASSED** |
| **Finalized Manifest Integrity** | Every `artifact_files` listed in all 15 `manifest.json` exists with matching SHA-256 hash. | **PASSED** (100% hash consistency verified) |
| **A/C Retrieval Logs** | No retrieval logs exist for Strategy A or Strategy C. | **PASSED** (Retrieval matches spec) |
| **Diagnostics Folder** | No diagnostics folder matching `results/raw/diagnostics/m7e_full_20260612T010000Z` exists. | **PASSED** (Count is 0, keeping directory structure clean) |
| **Derived Outputs Absent** | No CSV or Markdown summary exists in `results/derived/` under the new ID. | **PASSED** (Correctly prevented mid-abort data pollution) |
| **Workspace Residue Cleanliness** | Transient workspace is empty. | **PASSED** (No dirty workspaces left) |

---

## 4. Root Cause Evidence & Analysis

During the execution of run `m7e_full_20260612T010000Z__T02__E__rep01__seed42`, the Planner agent of Strategy E requested retrieval.

- **Limit Settings:** Following M7-E.9, `_BUDGETS = {("Planner", "initial"): 3, ...}`.
- **Observed Behavior:** The Planner successfully initiated 3 retrieval requests (captured in `results/raw/retrieval/m7e_full_20260612T010000Z/m7e_full_20260612T010000Z__T02__E__rep01__seed42.jsonl`). However, because of the complex nature of Task T02, the Planner required further context and issued a 4th query (`get_student_course_summary`).
- **Safety Intercept:** The system's budget check caught the 4th query: `retrieval_count >= budget` (`3 >= 3` holds true). This triggered the fail-closed defense, raising `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted`, and safely halting the experiment run.

---

## 5. Frozen Historical Hashes Verification

We recalculated and verified the SHA-256 hashes of all prior, frozen experimental artifacts. They remain 100% unchanged and untouched:

| File Path | SHA-256 Hash | Status |
| :--- | :--- | :--- |
| `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | Unchanged |
| `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | Unchanged |
| `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | Unchanged |
| `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` | Unchanged |

---

## 6. Execution Safety Declarations

- **No Resume of Old IDs:** No resume operations were performed on `m7e_full_20260611T210000Z` or `m7e_full_20260611T230000Z`.
- **No FAKE Full Run Provider:** The fake provider flag `ARAG_USE_FAKE_FULL_RUN_PROVIDER` was NOT set. The experiment was executed against the real Gateway port on localhost.
- **No Derived Outputs:** No derived output files (CSV or summary MD) were generated because the 45-run dataset did not fully complete. This protects statistics analysis from incomplete data pollution.

---

## 7. Local Verification & Residue Scan

- **Offline gate verification:** `python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q`
- **Result:** `40 passed`
- **Residue policy:** No derived outputs, diagnostics folder, or transient workspace remain for `m7e_full_20260612T010000Z`. Bytecode/cache/temp residue must remain at zero after cleanup.
