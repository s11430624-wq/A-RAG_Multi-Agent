# Milestone 7-E.25 Acceptance: Gateway 429 Recovery Implementation

**Status:** Completed (Implementation & Verification Complete) / Green TDD Validation / Live Execution Blocked

## Deliverables

| Deliverable | Status |
| :--- | :--- |
| `experiments/live/factory.py` (fixed time import) | Completed |
| `experiments/live/smoke_executor.py` (production sleeper composition) | Completed |
| `tests/live/test_rate_limit_and_recovery.py` (TDD rate limit / diagnostic / sleeper composition tests) | Completed |
| `tests/live/test_full_run_executor.py` (explicit sleeper dependency injection) | Completed |
| `tests/live/test_smoke_executor.py` (explicit sleeper dependency injection) | Completed |
| `docs/milestones/M7E25_acceptance.md` | Completed |
| `docs/milestones/M7_acceptance.md` status synchronization | Completed |

## Acceptance Matrix

| ID | Requirement | Status |
| :--- | :--- | :---: |
| M7E25-001 | Correct `time` import reference in `experiments/live/factory.py` | Completed |
| M7E25-002 | Harden `test_final_429_aborts_without_completed_record` to use correct SHA-256 for `"# dummy"` bytes | Completed |
| M7E25-003 | Assert FaultyProvider.generate is invoked during rate-limit abort test | Completed |
| M7E25-004 | Assert res.provider_attempt_count == 1 and res.completed_run_ids has zero records | Completed |
| M7E25-005 | Read written diagnostic record and assert `final_http_status` == 429 | Completed |
| M7E25-006 | Ensure production CLI composition uses `time.sleep` as default constructor sleeper | Completed |
| M7E25-007 | Forbid no-op / mock sleeper as LiveExperimentExecutor production constructor default | Completed |
| M7E25-008 | Explicitly inject `sleeper=lambda s: None` in all executor/smoke tests to avoid sleep delays | Completed |
| M7E25-009 | Verify that diagnostics (error class, status 429, attempt records, Retry-After headers) are correctly preserved when wrapped in another exception | Completed |
| M7E25-010 | All verification test runs are fully GREEN | Completed |

## Frozen M7-E.23 Result

```text
results/raw/m7e_full_20260612T040000Z.jsonl
fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d
```

M7-E.25 does not authorize a new live execution run on staging/production.
