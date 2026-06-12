# Milestone 7-E.2 Acceptance: Full-Run Execution Gate & Dry Activation Tests

**Status:** Completed and Verified

This document defines the acceptance status and verification results for Milestone 7-E.2 (M7-E.2).
M7-E.2 implements the CLI execution gate and a generalized `LiveExperimentExecutor` to run a 45-run dry activation pipeline using simulated/scripted model providers.

---

## 1. Acceptance Checklist

| ID | Area | Requirement | Verification Method / Artifact | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7E2-001 | Executor | Generalized `LiveExperimentExecutor` from Smoke Executor | `experiments/live/smoke_executor.py` | Completed |
| M7E2-002 | CLI Gate | Full-run execution gate on CLI (`live-run`) | `experiments/cli.py` | Completed |
| M7E2-003 | Preflight Checks | Double-gate revalidation of frozen smoke reports (SHA, JSONL, manifest set, retrieval log set) | `test_full_run_gate.py` & `test_full_run_executor.py` | Completed |
| M7E2-004 | Dry Activation | Complete 45-run dry pipeline using deterministic fake provider | `test_full_run_executor.py::test_full_run_dry_activation_pipeline` | Completed |
| M7E2-005 | Budget Control | Enforce 330 provider attempts, 1M input tokens, 500k output tokens, and abort on exceed | `test_budget_enforcement_and_block_attempt_331` | Completed |
| M7E2-006 | Abort & Fail-closed | Exit immediately on first error; preserve valid completed records; no partial writes | `test_abort_on_infra_error_and_preserves_completed` | Completed |
| M7E2-007 | Resume & Recovery | Resume skips valid completed run IDs; fails closed on malformed existing JSONL or duplicate IDs | `test_resume_valid_completed_records` & `test_resume_fails_closed_on_invalid_jsonl` | Completed |
| M7E2-008 | Leakage Controls | No hidden leakages, credentials, or workspaces overlap; offline testing is strictly isolated | Checked via unit and integration tests | Completed |
| M7E2-009 | Verification | Focused and regression tests are 100% green; zero live executions made | `pytest` output | Completed |
| M7E2-010 | M7-E.3 Blocked | Phase 3 (M7-E.3 Live execution) remains Planned/Blocked | Explicitly stated in docs | Completed |

---

## 2. Dry Activation Verification Results

A suite of 37 focused test cases has been successfully run to verify the 45-run full-run execution path and safety gates in a simulated environment:
- **`test_full_run_dry_activation_pipeline`**: Verifies that under authorized dry run mode, the generalized executor completes 45 runs successfully, writes correct raw JSONL, artifacts, and retrieval logs, and produces derived CSV/markdown summaries post-run.
- **`test_budget_enforcement_and_block_attempt_331`**: Verifies that when max calls is reached, the system throws `BudgetExceededError`, halts execution, discards the current run's partial data, and keeps previously written valid records intact.
- **`test_abort_on_infra_error_and_preserves_completed`**: Verifies that a ProviderError/infra error immediately stops the pipeline, raises the correct root cause error, and protects completed records on disk.
- **`test_resume_valid_completed_records`**: Verifies that the resume capability correctly detects existing valid JSONL runs, skips them, and only plans execution for the remaining pending runs.
- **`test_resume_fails_closed_on_invalid_jsonl`**: Verifies that any malformed JSONL or duplicate run IDs aborts resume during preflight check.

All focused tests passed with **100% green status**.

---

## 3. Dry Activation Execution Metrics

* **Simulated Runs Planned:** 45 (5 Tasks $\times$ 3 Strategies $\times$ 3 Repetitions)
* **Simulated Runs Completed:** 45
* **Simulated Provider Calls Checked:** 330 (Worst-case logic limit applied and enforced)
* **Simulated Tokens Checked:** 1,000,000 input / 500,000 output tokens
* **Output Path Collisions Checked:** Verified preflight collision rejection of target outputs.
* **Residue Cleanliness:** Verified that no `m7e_full_*` files or directories remain in the production codebase. All outputs generated during the tests were written and cleaned up automatically inside `pytest`'s temporary virtual folders.

---

## 4. No Live Execution Confirmation

* **Model Calls Made:** 0
* **Gateway Connections:** None (Offline sockets strictly blocked/mocked)
* **Credentials Accessed:** None (Zero live keys accessed or loaded)
* **Status of M7-E.3 (Live Execution):** **Planned / Blocked** (Blocked until explicit operator override)
