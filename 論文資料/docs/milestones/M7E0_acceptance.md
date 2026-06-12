# Milestone 7-E.0 Acceptance: Full-Run Approval Gate Only

**Status:** Completed and Verified

This document defines the acceptance status and verification results for Milestone 7-E.0 (M7-E.0).
M7-E.0 establishes the M7-E full 45-run approval gate model, validator, and CLI boundary checks to verify approval parameters, ensure absolute file integrity of frozen smoke outputs, perform preflight path checks, and enforce credential scanning prior to any live runs.

---

## 1. Acceptance Checklist

| ID | Area | Requirement | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7E0-001 | Parameter Check | Parse and validate approval parameters (45 runs, T01-T05, A/C/E, GPT5.4, openai_compatible_gateway, repetitions=3, seed=42) | Review `FullRunApproval` schema and `FullRunApprovalValidator` checks | Completed |
| M7E0-002 | Integrity Gate | Perform fail-closed revalidation of the frozen smoke report, source JSONL, manifest set, and retrieval log set hashes from physical filesystem | Recalculate SHA-256 and assert strict equality to frozen hashes | Completed |
| M7E0-003 | Budget Check | Verify input/output token budgets and wall clock limit against hard caps (1M input, 500k output, 3600s wall clock) | Verify validation raises error on exceedance or negative value | Completed |
| M7E0-004 | Preflight Checks | Preflight checks on future paths: reject if any output JSONL, artifact dir, retrieval log dir, derived CSV, or derived summary exists | Path existence validation checks | Completed |
| M7E0-005 | CLI Boundary | `live-run` parser verifies all gate parameters, returns code 2 on verification success or failure, and prints verification message without any code execution | Run `experiments.cli live-run` | Completed |
| M7E0-006 | Credential Scan | Scan CLI command-line arguments and approval fields for plaintext credentials (e.g. `bearer`, `api_key=`, `secret=`) | Regex scanning of args before parsing and fields during validation | Completed |

---

## 2. Verification Results

### Automated Tests
The dedicated test suite [test_full_run_gate.py](file:///c:/上課檔案/報告/A-RAG_Multi-Agent/tests/live/test_full_run_gate.py) verifies all boundaries, fail-closed conditions, and preflight checks:
- **Total Test Cases:** 18
- **Results:** 18 Passed, 0 Failed

To run the dedicated tests:
```powershell
python -B -m pytest tests/live/test_full_run_gate.py -v
```

All 497 tests in the workspace are green:
```powershell
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```
- **Results:** 497 passed, 2 skipped

### Manual Verification
Running the `live-run` CLI with valid gate arguments correctly performs all validation checks, outputs the M7-E.0 completion status, and exits with code 2 without starting any scheduler or orchestrator:
```powershell
python -B experiments/cli.py live-run --repo-root . --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a --full-experiment-id m7e_full_20260611T180000Z --human-approval FULL_RUN --approved-input-token-budget 1000000 --approved-output-token-budget 500000 --approved-wall-clock-seconds 3600 --allow-unknown-cost
```
Output:
```
full-run approval validated, execution requires M7-E.1 approval.
```
Exit code: `2`
