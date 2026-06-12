# Milestone 7-E.6 Acceptance: Final Full Rerun Preflight

This document defines the preflight validation, collision checks, gateway readiness, and the frozen command draft for the upcoming final full 45-run rerun under **Milestone 7-E.6 (M7-E.6)**.

---

## 1. Selected New Experiment ID

- **Selected Canonical ID:** `m7e_full_20260611T230000Z`
- **Rationale for New ID (No Resume of M7-E.3):**
  - M7-E.3 partial results (`m7e_full_20260611T210000Z`) were aborted at run 7 due to an unhardened reviewer envelope parse failure.
  - To maintain absolute data integrity, consistency, and a clean baseline, the final 45-run scientific dataset must be executed fresh from start with the newly hardened parser, without mixing unhardened and hardened execution records.
  - The M7-E.3 partial results (7/45) are completely frozen for audit purposes and will not be mutated or overwritten.

---

## 2. Preflight Checklist

| Target Item | Path / Key | Required Status | Verified Value | Status |
| :--- | :--- | :--- | :--- | :--- |
| Config Model | `configs/models.yaml` -> `default_model` | `google/gemini-3.5-flash` | `google/gemini-3.5-flash` | **PASSED** |
| Config Provider | `configs/models.yaml` -> `default_provider` | `hermes_vertex_gateway` | `hermes_vertex_gateway` | **PASSED** |
| Config API Base | `configs/models.yaml` -> `api_base` | `http://127.0.0.1:8787/v1` | `http://127.0.0.1:8787/v1` | **PASSED** |
| M7-D Smoke Report Path | `results/raw/gates/m7d_smoke_20260611T123000Z.json` | Must Exist | Yes | **PASSED** |
| M7-D Smoke Report SHA | — | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | **PASSED** |
| M7-D Smoke Gate Status | — | `automated_gate_passed == true` | `true` | **PASSED** |
| M7-D Smoke Risk Flags | — | Contains `unknown_cost` | `["unknown_cost"]` | **PASSED** |
| M7-D Smoke JSONL Path | `results/raw/m7d_smoke_20260611T123000Z.jsonl` | Must Exist | Yes | **PASSED** |
| M7-D Smoke JSONL SHA | — | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | **PASSED** |
| M7-E.3 Partial JSONL Path | `results/raw/m7e_full_20260611T210000Z.jsonl` | Must Exist | Yes | **PASSED** |
| M7-E.3 Partial JSONL SHA | — | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | **PASSED** |
| M7-E.3 Partial Line Count | — | `7` | `7` | **PASSED** |
| M7-E.5 Hardening Status | `docs/milestones/M7E5_acceptance.md` | Completed | Implementation Completed & Verified | **PASSED** |

---

## 3. Collision Check for New ID

The following destination paths have been rigorously checked and confirmed to be completely clear of any prior artifacts or leftover test files (none exist on disk):

- 🟩 `results/raw/m7e_full_20260611T230000Z.jsonl` (None)
- 🟩 `results/raw/artifacts/m7e_full_20260611T230000Z` (None)
- 🟩 `results/raw/retrieval/m7e_full_20260611T230000Z` (None)
- 🟩 `results/raw/diagnostics/m7e_full_20260611T230000Z` (None)
- 🟩 `results/derived/m7e_full_20260611T230000Z.csv` (None)
- 🟩 `results/derived/m7e_full_20260611T230000Z_summary.md` (None)
- 🟩 `results/reviews/m7e_full_20260611T230000Z_review_package.jsonl` (None)
- 🟩 `results/reviews/m7e_full_20260611T230000Z_review_mapping.jsonl` (None)

*Status:* **Collision Check Passed (All Clear).**

---

## 4. Gateway Readiness

- **Loopback Port Check:** `127.0.0.1:8787` is confirmed to be **listening** and ready to receive traffic.
- **Security Constraint Enforcement:**
  - No model API requests were sent.
  - No connection credentials or service account files were inspected.
  - Zero mock-run or live-run state was initiated during preflight.

---

## 5. Hardening Status Audit

The Reviewer parser and diagnostics subsystems are verified to be fully hardened following M7-E.5 specifications:
1. **Fenced JSON Support:** The parser safely extracts fenced blocks and normalizes the verdict string to uppercase `"PASS"` and `"FAIL"`.
2. **Strict Metadata Rejection:** Extra fields (like `thoughts` and `explanation`) are rigorously rejected.
3. **Prompt Boundaries:** The reviewer prompt is explicitly hardened to instruct the model to output exact JSON with no fences.
4. **Durable & Secure Diagnostics:**
  - Pointed directly to `repo_root` to isolate from working directory changes.
  - Formatted to compact canonical JSON.
  - Restricted via a denylist filter that blocks writing if `evaluation/hidden_tests` or `evaluation/reference_patches` paths appear.
  - Exclusive-create mode is strictly enforced.

---

## 6. Frozen Command Draft for Final Full Rerun

The following command has been generated and frozen, ready for execution immediately upon receiving operator approval:

```powershell
# PowerShell Command Draft
$env:ARAG_RUN_LIVE_GATEWAY='1'
$env:ARAG_EXECUTE_FULL_RUN_ONCE='1'
Remove-Item Env:ARAG_USE_FAKE_FULL_RUN_PROVIDER -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'

python -B experiments/cli.py live-run `
  --repo-root . `
  --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json `
  --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a `
  --full-experiment-id m7e_full_20260611T230000Z `
  --human-approval FULL_RUN `
  --approved-input-token-budget 1000000 `
  --approved-output-token-budget 500000 `
  --approved-wall-clock-seconds 3600 `
  --allow-unknown-cost
```

---

## 7. Stop Point & Action Required

- 🔴 **Zero Runs Executed:** No model invocations, no database writes, and no full rerun execution steps were taken during this preflight turn.
- 🚦 **Operator Approval Pending:** The system has successfully completed all preflight checks and is now safely halted, awaiting explicit human operator approval to execute the frozen command draft.
