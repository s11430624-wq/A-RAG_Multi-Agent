# Milestone 7-E.24 Acceptance: Gateway 429 Recovery Decision

**Status:** Completed (Decision Plan Only) / M7-E.25 Not Started / Live Rerun Blocked

## Deliverables

| Deliverable | Status |
| :--- | :--- |
| `docs/superpowers/plans/2026-06-12-m7e24-gateway-rate-limit-policy.md` | Completed |
| `docs/milestones/M7E24_acceptance.md` | Completed |
| `docs/milestones/M7_acceptance.md` status synchronization | Completed |
| Production implementation | Not started |
| Live execution or resume | Blocked |

## Acceptance Matrix

| ID | Requirement | Status |
| :--- | :--- | :---: |
| M7E24-001 | Identify that real `urllib.error.HTTPError(429)` bypasses Provider status retry classification | Completed |
| M7E24-002 | Identify fixed `0.25/0.50` retry delay as unsuitable for quota windows | Completed |
| M7E24-003 | Identify absence of a shared limiter across independent live Providers | Completed |
| M7E24-004 | Identify the contradiction between 330 logical calls and 330 physical attempts | Completed |
| M7E24-005 | Identify missing durable failed active-run attempt evidence | Completed |
| M7E24-006 | Compare halt, status-only, pacing-only, layered recovery, and resume options | Completed |
| M7E24-007 | Select live-only layered Option D without changing A/C/E strategy behavior | Completed |
| M7E24-008 | Define bounded HTTP-error body/header handling and preserve 401/403 behavior | Completed |
| M7E24-009 | Define optional retry-delay resolver while preserving M5 default behavior | Completed |
| M7E24-010 | Define strict `Retry-After` parsing, fallback, and 1..120 second clamp | Completed |
| M7E24-011 | Define one shared rate limiter across all A/C/E Provider instances | Completed |
| M7E24-012 | Define wait -> wall-clock check -> attempt reservation -> send ordering | Completed |
| M7E24-013 | Define strategy-neutral 10-second inter-run cooldown | Completed |
| M7E24-014 | Define amended physical attempt ceiling 660 and wall-clock ceiling 5400 seconds | Completed |
| M7E24-015 | Require separate operator approval for amended budgets | Completed |
| M7E24-016 | Define canonical sanitized provider-failure diagnostics | Completed |
| M7E24-017 | Preserve fail-closed behavior after final retry | Completed |
| M7E24-018 | Forbid resume of M7-E.23 and require a new experiment ID | Completed |
| M7E24-019 | Define 24 explicit offline TDD cases for M7-E.25 | Completed |
| M7E24-020 | Confirm no production code, tests, configs, schemas, or tasks changed | Completed |
| M7E24-021 | Confirm no Gateway, model, retrieval, live-run, or resume execution | Completed |
| M7E24-022 | Freeze the M7-E.23 partial raw SHA-256 | Completed |

## Frozen M7-E.23 Result

```text
results/raw/m7e_full_20260612T040000Z.jsonl
fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d
```

M7-E.24 does not authorize implementation or another live run.

