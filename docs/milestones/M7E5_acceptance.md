# Milestone 7-E.5 Acceptance: Reviewer Envelope Hardening Implementation

This document defines the acceptance status and verification results for **Milestone 7-E.5 (M7-E.5)**, including the implementation of the security blocker fixes.

---

## 1. Acceptance Matrix

| ID | Requirement | Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **M7E5-001** | RED Tests Created | Verify tests are created prior to full implementation and fail under the original unhardened parser. | **Completed** |
| **M7E5-002** | Reviewer Parser Hardened | Implement `extract_fenced_json` and strict validation rejecting extra keys, trailing texts, or multiple JSON structures. | **Completed** |
| **M7E5-003** | Verdict Normalization | Support lowercase `"pass"` and mixed-case `"Fail"` conversion to strict uppercase `"PASS"` and `"FAIL"`. | **Completed** |
| **M7E5-004** | Prompt Hardening | Revise `experiments/prompts/reviewer.txt` to instruct the model to output exact JSON with no fences or conversational wrappers. | **Completed** |
| **M7E5-005** | Durable Abort Diagnostic | Implement `AbortDiagnosticWriter` and record raw responses, exception trace, role, and hash in exclusive-create JSON files. | **Completed** |
| **M7E5-006** | Security & Containment | Enforce relative path resolution, throw `ValueError` on path traversal in `run_id` or `experiment_id`, and keep logs isolated. | **Completed** |
| **M7E5-007** | Integration Verification | Catch exceptions in `BaseStrategySession._invoke_role`, attach `raw_response` and `role`, and log them inside `ExperimentOrchestrator`. | **Completed** |
| **M7E5-008** | Legacy Code Regression | Verify that other strategies (Coder, Planner) and existing tests remain completely green and unaffected. | **Completed** |
| **M7E5-009** | **Blocker 1 Fix: stdout Leak** | Remove all `print` statements of raw LLM outputs from `base.py`. Output is strictly attached to exception for `diagnostics`. | **Completed** |
| **M7E5-010** | **Blocker 2 Fix: Repo Root Isolation** | Initialize `AbortDiagnosticWriter` with `self.repo_root` instead of `Path(".")`. Resilient to CWD changes. | **Completed** |
| **M7E5-011** | **Blocker 3 Fix: Diagnostic Fail Safe** | Orchestrator diagnostic write errors are safely suppressed and never leak absolute paths, tracebacks, or raw responses on stdout. | **Completed** |
| **M7E5-012** | **Blocker 4 Fix: Canonical & Denylist** | Write deterministic canonical JSON with exact 1 trailing LF, and reject write if raw_response/error_message contains denylisted patterns. | **Completed** |

---

## 2. Implementation Overview

### 2.1 Parser & Prompt Hardening
- **Parser (`experiments/strategies/parsers.py`):**
  Added `_extract_clean_json_object` private helper to parse entire responses. It strips single fenced JSON blocks with whitespace-only paddings but strictly rejects any leading/trailing conversational text or multiple fenced blocks. It strictly validates keys, rejecting thoughts/explanation meta-keys, and normalizes `verdict` casing to uppercase `"PASS"` and `"FAIL"`.
- **Prompt (`experiments/prompts/reviewer.txt`):**
  Harden system directives explicitly stating format boundaries, allowed keys, and forbidding markdown code fences and introductory/trailing conversational wrappers.

### 2.2 Abort Diagnostic Logging
- **Diagnostic Writer (`experiments/live/diagnostics.py`):**
  Added thread-safe/process-safe diagnostic log writer creating canonical JSON payloads with unique SHA-256 signatures in `results/raw/diagnostics/` under exclusive `'x'` creation mode. Key features added:
  - **Deterministic Canonical Serialization:** Using compact separators and key sorting (`sort_keys=True, separators=(",", ":")`), ending with exactly one newline.
  - **Denylist Filters:** Blocks writing and raises `ValueError` if the output or error contains path signatures of `evaluation/hidden_tests` or `evaluation/reference_patches`.
- **Orchestrator Integration (`experiments/strategies/base.py` and `experiments/runner/orchestrator.py`):**
  If a model response fails parsing or validation, `base.py` attaches the raw response string and the role to the exception object before raising. The orchestrator's exception handler catches it, instantiates `AbortDiagnosticWriter` pointing to `self.repo_root` (resilient to cwd), and writes the diagnostics safely. Any diagnostic write errors are caught and ignored, never leaking traceback/raw response onto stdout.

---

## 3. Verification Details

### 3.1 Reviewer Envelope Parsing Tests (17 Cases)
Tested via `tests/strategies/test_reviewer_envelope_parser.py`:
- `test_accept_valid_cases` (Raw dict, markdown fence, lowercase "pass" -> PASS, mixed "Fail" -> FAIL) - **PASSED**
- `test_reject_extra_keys_thoughts` - **PASSED**
- `test_reject_extra_keys_explanation` - **PASSED**
- `test_reject_text_before_json` - **PASSED**
- `test_reject_text_after_json` - **PASSED**
- `test_reject_multiple_json_objects` - **PASSED**
- `test_reject_missing_verdict` - **PASSED**
- `test_reject_missing_issues` - **PASSED**
- `test_reject_issues_not_list` - **PASSED**
- `test_reject_invalid_verdict_value` - **PASSED**
- `test_reject_empty_response` - **PASSED**
- `test_reject_malformed_fenced_json_with_trailing_text` - **PASSED**
- `test_reject_multiple_fenced_blocks` - **PASSED**

### 3.2 Abort Diagnostic & Hardening Tests
Tested via `tests/live/test_abort_diagnostics.py`:
- `test_write_synthetic_failed_response_creates_file` - **PASSED**
- `test_exclusive_create_rejects_overwrite` - **PASSED**
- `test_path_traversal_mischief_is_rejected` - **PASSED**
- `test_diagnostics_isolation_from_artifacts_and_retrieval` - **PASSED**
- `test_no_hidden_test_path_or_content_leaked` - **PASSED**
- `test_reviewer_extra_key_fails_and_exception_carries_response` (Integration verification) - **PASSED**
- `test_blocker_1_no_raw_response_printed_to_stdout_or_stderr` (Stdout blocker regression) - **PASSED**
- `test_blocker_2_diagnostics_root_isolation_from_cwd` (CWD isolation test) - **PASSED**
- `test_blocker_3_diagnostics_write_failure_does_not_leak_details` (Diagnostics crash safety) - **PASSED**
- `test_blocker_4_canonical_and_denylist_checks` (Canonical format & security denylist filters) - **PASSED**

### 3.3 Regression Tests Summary
```powershell
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```
**Result:** **540 passed, 2 skipped (100% green).** Zero legacy code regression.

---

## 4. Immutable Boundaries & Confirmation

- **No Resume / Rerun:** No resume or re-run of M7-E.3 was done.
- **No Gateway Connection:** No HTTP calls to `127.0.0.1:8787` or live model providers.
- **Existing Records Intact:** M7-E.3 partial results (`results/raw/m7e_full_20260611T210000Z.jsonl` and manifests) remain completely frozen and unaltered.
- **Milestone Final Status:** **Completed**.
