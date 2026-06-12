# Milestone 7 Acceptance Plan: Live Provider & Experiment Execution

**Status:** M7-A through M7-E.26 Completed; M7-E.27 Real Full Rerun Executed Once and Controlled-Aborted on Input Token Budget; 15/45 Results Preserved; No Further Automatic Rerun Authorized; Final Dataset Not Complete

This document defines the acceptance criteria and verification plan for Milestone 7 (M7).
M7 connects the offline pipeline to the Hermes Vertex Gateway, runs validation probes and smoke runs, enforces budget limits, executes the full 45-run experiment, and handles blind manual grading.

---

## 1. Planned Deliverables

| Area | Planned files | Status |
| :--- | :--- | :--- |
| M7 Plan | `docs/superpowers/plans/2026-06-11-m7-live-experiment.md` | Completed |
| M7-D Smoke Execution Plan | `docs/superpowers/plans/2026-06-11-m7d-smoke-run-plan.md` | Completed |
| M7 Acceptance | `docs/milestones/M7_acceptance.md` | Completed |
| M7-D Acceptance | `docs/milestones/M7D_acceptance.md` | Completed |
| M7-E.0 Acceptance | `docs/milestones/M7E0_acceptance.md` | Completed |
| M7-E.1 Plan | `docs/superpowers/plans/2026-06-11-m7e-full-run-execution-plan.md` | Completed |
| M7-E.1 Acceptance | `docs/milestones/M7E1_acceptance.md` | Completed |
| M7-E.2 Acceptance | `docs/milestones/M7E2_acceptance.md` | Completed (Dry Activation Completed) |
| M7-E Approval Package | `docs/milestones/M7E_full_run_approval_package.md` | Completed (Hardening Done) |
| M7-E.3 Abort Audit | `docs/milestones/M7E3_abort_audit.md` | Controlled Abort / Partial Results Preserved / Resume Decision Pending |
| M7-E.4 Hardening Plan | `docs/superpowers/plans/2026-06-11-m7e4-reviewer-envelope-hardening.md` | Completed |
| M7-E.4 Acceptance | `docs/milestones/M7E4_acceptance.md` | Completed |
| M7-E.5 Implementation | `docs/milestones/M7E5_acceptance.md` | Completed |
| M7-E.6 Preflight | `docs/milestones/M7E6_preflight.md` | Completed |
| M7-E.7 Final Full Rerun Execution | `docs/milestones/M7E7_abort_audit.md` | Controlled Abort / Partial Results Preserved / Final Dataset Not Complete |
| M7-E.8 Retrieval Budget Policy | `docs/superpowers/plans/2026-06-11-m7e8-retrieval-budget-policy.md` | Completed |
| M7-E.8 Acceptance | `docs/milestones/M7E8_acceptance.md` | Completed |
| M7-E.9 Acceptance | `docs/milestones/M7E9_acceptance.md` | Completed |
| M7-E.10 Acceptance | `docs/milestones/M7E10_preflight.md` | Completed |
| M7-E.11 Final Rerun | `docs/milestones/M7E11_abort_audit.md` | Controlled Abort / Partial Results Preserved / Final Dataset Not Complete |
| M7-E.12 Decision | `docs/milestones/M7E12_acceptance.md` | Completed |
| M7-E.13 Hardening | `docs/milestones/M7E13_acceptance.md` | Completed (Retrieval Loop Hardening TDD Implementation Completed) |
| M7-E.14 Preflight | `docs/milestones/M7E14_preflight.md` | Completed (Final Rerun Preflight after Retrieval Loop Hardening) |
| M7-E.15 Final Full Rerun Execution | `docs/milestones/M7E15_abort_audit.md` | Controlled Abort / Partial Results Preserved / Final Dataset Not Complete |
| M7-E.16 Retrieval Budget Option F Decision | `docs/superpowers/plans/2026-06-12-m7e16-retrieval-budget-option-f.md`, `docs/milestones/M7E16_acceptance.md` | Completed (Plan Only; No Implementation) |
| M7-E.17 Retrieval Budget Option F Implementation | `docs/milestones/M7E17_acceptance.md` | Completed (TDD Implementation; Offline Only) |
| M7-E.18 Final Rerun Preflight | `docs/milestones/M7E18_preflight.md`, `docs/milestones/M7E18_acceptance.md` | Completed (Preflight Only; Awaiting Explicit Approval) |
| M7-E.19 Real Full Rerun Execution | `docs/milestones/M7E19_abort_audit.md` | Controlled Abort / Partial Results Preserved / Final Dataset Not Complete |
| M7-E.20 Coder Retrieval Policy Decision | `docs/superpowers/plans/2026-06-12-m7e20-coder-retrieval-policy.md`, `docs/milestones/M7E20_acceptance.md` | Completed (Plan Only; No Implementation) |
| M7-E.21 Coder Evidence Inheritance + Retrieval Budget TDD Implementation | `docs/milestones/M7E21_acceptance.md` | Completed (Offline TDD; No Live Execution) |
| M7-E.22 Final Rerun Preflight after Coder Evidence Inheritance | `docs/milestones/M7E22_preflight.md` | Completed; One-Time Approval Consumed by M7-E.23 |
| M7-E.23 Real Full Rerun Execution | `docs/milestones/M7E23_abort_audit.md` | Controlled Abort (Gateway HTTP 429); Partial Results Preserved; Final Dataset Not Complete |
| M7-E.24 Gateway 429 Recovery and Batch Throttling Decision | `docs/superpowers/plans/2026-06-12-m7e24-gateway-rate-limit-policy.md`, `docs/milestones/M7E24_acceptance.md` | Completed (Decision Only) |
| M7-E.25 Gateway 429 Recovery Implementation & Verification | `docs/milestones/M7E25_acceptance.md` | Completed |
| M7-E.26 Final Rerun Preflight after Gateway 429 Recovery | `docs/milestones/M7E26_preflight.md`, `docs/milestones/M7E26_acceptance.md` | Completed (Offline Preflight Only) |
| M7-E.27 Real Full Rerun after Gateway 429 Recovery | `docs/milestones/M7E27_execution_audit.md` | Controlled Abort (Input Token Budget); 15/45 Partial Results Preserved; No Resume |
| HTTP Transport | `experiments/live/http_transport.py` | Completed |
| Live Provider Factory | `experiments/live/factory.py` | Completed |
| Budget controls | `experiments/live/budget.py` | Completed |
| Connection Probe | `experiments/live/probe.py` | Completed |
| Smoke scheduler | `experiments/live/smoke_scheduler.py` | Completed |
| Offline smoke executor | `experiments/live/smoke_executor.py` | Completed (fake/scripted provider only) |
| Smoke gate report | `experiments/live/smoke_gate.py` | Completed |
| Manual Review Queue | `experiments/live/reviews.py` | Completed |
| Live CLI updates | `experiments/cli.py` additions | Completed |
| M7 Tests | `tests/live/` and `tests/leakage/` new modules | Completed |
| M7-E.0 Gate Tests | `tests/live/test_full_run_gate.py` | Completed |
| M7 Leakage Tests | `tests/leakage/test_m7_live_leakage.py` | Completed |

---

## 2. Acceptance Matrix

### M7.0 Readiness
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-001 | Planning | M7 plan exists with detailed TDD tasks and architecture | Review `docs/superpowers/plans/2026-06-11-m7-live-experiment.md` | Completed |
| M7-002 | Planning | Acceptance matrix exists with all items initially Planned | Review this file | Completed |
| M7-003 | Baseline | Baseline starts from a green M1-M6 baseline (338 passed, 1 expected live skip) | Run `python -B -m pytest -q` | Completed |
| M7-004 | Static Guard | M7 plan does not modify existing config schemas or YAML files | Run `git diff` on configs and contracts | Completed |
| M7-005 | Phase Gates | Milestone execution follows gates M7-A (Offline Infra) -> M7-B (Adapter Approval) -> M7-C (Probe) -> M7-D (Smoke) -> M7-E (Full) | Review CLI run block logic in unit tests | Completed |

### M7.1 Transport
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-101 | Credentials | Credentials must only load immediately before sending requests | Verify in `tests/live/test_credentials.py` | Completed |
| M7-102 | Repr Safety | Authorization headers must never appear in `dataclass` repr, logs, stdout, or artifacts | Run string scan in test cases | Completed |
| M7-103 | Import Safety | Importing `experiments/live/http_transport.py` must not read env variables or open connections | Verify in `tests/live/test_credentials.py` | Completed |
| M7-104 | Protocols | Only HTTPS or explicitly approved localhost Gateway connections are permitted | Verify transport initialization assertions | Completed |
| M7-105 | Redirects | HTTP transport must reject redirects | Run mock server redirect tests | Completed |
| M7-106 | Payload Limits | Response body size is strictly limited (maximum 10 MB) | Verify behavior with a large body mock response | Completed |
| M7-107 | Timeouts | Strict socket connect and read timeouts must be enforced | Verify connection timeout triggers correct error | Completed |
| M7-108 | TLS Validation | TLS verification cannot be disabled | Verify no `verify=False` or similar options exist | Completed |
| M7-109 | Error Mapping | Network socket/HTTP errors must map to existing `ProviderTransportError` or related exceptions | Verify error classification tests | Completed |
| M7-110 | Credential Source | If credential source is unresolved, transport layer fails closed | Verify unresolved config throws error in `test_credentials.py` | Completed |
| M7-111 | Service Account | Service Account JSON structures must never be directly placed in the Authorization header | Verify parser rejects structured JSON tokens | Completed |
| M7-112 | Proxy Disabled | Environmental proxies (HTTP_PROXY, etc.) are bypassed in live transport | Verify `ProxyHandler({})` is explicitly defined and tested | Completed |
| M7-113 | Host Validation | URL Host is validated on initialization and send. Host segments, ports, fragments, and userinfo must match approved profiles | Run malformed URL input tests | Completed |

### M7.2 Gateway Probe
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-201 | Probe request | Execute a single minimal probe request to verify Gateway status before any experiment run | Run `experiments.cli live-probe` | Completed |
| M7-202 | Probe verification | Probe must verify connection, model identity, finish reason stop, request ID, and usage completeness (finish/model/request id OK, but usage accounting mismatch blocks smoke) | Check assertions in `GatewayProbe` unit tests and CLI output | Completed (Blocker Detected) |
| M7-203 | Usage fail-closed | If `usage` is missing or inconsistent in probe response, fail closed and block further runs | Verify probe raises `GatewayProbeError` or CLI returns error 2 and blocks smoke | Completed (Fail-Closed Verified) |
| M7-207 | Normalization TDD | Implement reasoning token normalization with strict provider isolation and raw audit metadata stored in ArtifactManifest call_records | Run `pytest tests/providers tests/strategies` | Completed (Tests Green) |
| M7-208 | Probe Integration | Fix `live-probe` CLI to leverage normalized provider parser and GatewayProbe contract without direct raw logic (ensuring exactly one generator call and one transport call) | Run `pytest tests/live/test_probe.py` | Completed (Tests Green) |
| M7-204 | Tokenizer restriction | The system must never guess token usage using a local tokenizer if usage is missing | Code audit of the response parser | Completed |
| M7-205 | Capability Aware | Verify request ID, seed, and model identity check respect capability and alias maps | Verify probe assertions under varying capabilities | Completed |
| M7-206 | M5 Preserved | M5 `openai_compatible.py` provider must not be modified. All probe logic resides in `GatewayProbe` | Run M5 provider regression unit tests | Completed |

*註記：M7-C.3 重新探針驗證（Live Re-Probe Confirmation）已通過。M7-D.2 one-shot 3-run live smoke completed and verified. M7-D outputs are frozen and bound by hashes. M7-E.23 real full rerun execution aborts on Gateway 429 and preserves partial dataset. M7-E.25 Gateway 429 recovery implemented and verified via TDD. Existing smoke files and previous partial full-run files must not be mutated.*

### M7.3 Smoke Runs
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-300 | Planning/gate | Exact command, canonical smoke ID, exact-root path containment, fixed 22-call budget derived from A(3)+C(5)+E(14), acceptance, rollback, fail-closed rules, and explicit approval gate are documented and tested without execution | Review M7-D plan and run CLI gate tests | Completed |
| M7-300A | Offline integration | Fake transport drives production scheduler, A/C/E sessions, orchestrator, evaluator, retrieval facade, artifact writer, and result writer under pytest tmp paths; finalized manifests include provider provenance in their original hashed bytes, the 22-attempt ceiling intentionally has no retry headroom, and production CLI remains disabled | Run offline executor integration tests | Completed |
| M7-300B | Live composition | Production Local Vertex Proxy provider composition creates three independent no-auth loopback providers with per-send attempt reservation, validates readiness without network or execution, and leaves CLI at code 2 pending M7-D.2 | Run live composition and CLI boundary tests | Completed |
| M7-301 | Runs restriction | Smoke runs are restricted to exactly 3 runs (T01 x A/C/E) with shared seed/model | Run `experiments.cli live-smoke` | Completed |
| M7-302 | Retrieval check | Verify Strategy A and C use zero retrieval, while Strategy E retrieval logs are valid | Check output JSONL for retrieval fields | Completed |
| M7-303 | Integrity | Result JSONL for smoke must be schema-valid and written with fsync | Run schema validation checks on smoke JSONL | Completed |
| M7-304 | Manifests | Verify that three workspace artifacts and correct manifests are generated | Run directory file-hash checks | Completed |
| M7-305 | Suffix separation | Smoke run results must use a separate experiment ID and JSONL path | Verify smoke file is isolated from main file | Completed |
| M7-306 | Resume behavior | Resume must avoid re-running completed smoke runs | Run smoke command twice and verify second runs are skipped | Completed |

### M7.4 Smoke Gate
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-401 | Report structure | Produce a typed `SmokeGateReport` summarizing validation metrics | Verify fields match the designed dataclass | Completed |
| M7-402 | Gate strictness | `automated_gate_passed` is True only if 3 runs succeed, usage is complete, schema/artifacts are valid, and tokens are within budget | Verify gate audit logic against negative test inputs | Completed |
| M7-403 | Non-automation | Full 45-run experiment cannot start automatically even if smoke gate passes | Verify CLI `live-run` blocks unless human approval is given | Completed |
| M7-404 | Canonical Report | SmokeGateReport must be exported in canonical UTF-8 JSON format with exclusive create | Verify report bytes format | Completed |
| M7-405 | Report tamper | CLI must reject execution if the smoke report has been modified by even one byte | Verify CLI aborts when report bytes are tampered | Completed |
| M7-406 | Hash binding | Full-run execution requires binding the SHA-256 hash of the smoke report | Verify CLI matches report SHA-256 against input arguments | Completed |
| M7-407 | Unknown cost gate | unknown cost 不影響 automated_gate_passed；但未提供 allow_unknown_cost 人工批准時阻擋 Full Run | Verify CLI checks for cost allowance | Completed |
| M7-408 | Risk flags | Report flags unknown cost as risk flag without setting automated_gate_passed to false | Check risk flags inside the generated report | Completed |
| M7-409 | JSONL revalidation | CLI must verify original raw JSONL bytes match `source_jsonl_sha256` before full-run | Verify CLI detects altered raw JSONL bytes | Completed |
| M7-410 | Manifest revalidation | CLI must recalculate and verify the manifest set hash `artifact_manifest_set_sha256` | Verify CLI rejects altered run workspaces | Completed |
| M7-411 | Retrieval log check | CLI must recalculate and verify the retrieval log set hash `retrieval_log_set_sha256` | Verify CLI aborts on modified retrieval log | Completed |

### M7.5 Budget / Circuit Breaker
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-501 | Live Budgeting | Enforce limits for total cost, run cost, input/output tokens, and wall clock seconds | Verify `LiveBudgetTracker` triggers exception when limit is hit | Completed |
| M7-502 | Pricing Fallback | If gateway pricing is unavailable, budget checks fallback to checking token count limits only | Verify cost estimated is null and tokens are tracked | Completed |
| M7-503 | Circuit breaker | Halt immediately on auth failure, missing usage, leakage sentinel, malformed response, or consecutive infra failures | Run mock budget tests triggering limits | Completed |
| M7-504 | State saving | On abort, save completed schema-valid runs for future resume | Verify incomplete run is discarded but prior JSONL is preserved | Completed |
| M7-505 | Cost unknown budget | When pricing is unknown, cost limits are null and token/wall-clock/call limits are used | Verify budget initializes with null cost fields | Completed |

### M7.6 Full 45 Runs
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-601 | Run scheduler | Run order is deterministic and scheduled exactly as 45 runs | Check scheduler output ordering | Planned |
| M7-602 | Process model | Run as single-process, single-writer with fsync on completion | Code audit of orchestrator loop | Planned |
| M7-603 | State isolation | Each run uses clean, isolated strategy/provider state and starts from starter snapshot | Verify workspace directories before run start | Planned |
| M7-604 | Leakage guard | Do not feed output or artifacts of previous runs into subsequent runs | Code inspection and mock test validation | Planned |
| M7-605 | Parallelism | No concurrent or parallel execution is supported | Code inspection of orchestrator execution | Planned |

### M7.7 Resume / Recovery
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-701 | ID matching | Resume matches completed runs by exact `run_id` in raw JSONL | Run CLI with partially completed JSONL | Planned |
| M7-702 | Resume behavior | Resume must never re-run completed runs | Verify scheduler filters out existing completed run IDs | Planned |
| M7-703 | No state reuse | Resume must not load prompts/responses/artifacts of completed runs as strategy inputs | Verify workspace is clean | Planned |

### M7.8 Leakage / Audit
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-801 | Leakage check | Verify hidden tests, grading info, or reference patches are not leaked to model | Run leakage scan test on output JSONL/logs | Planned |
| M7-802 | Credential scan | Verify no credentials, API keys, or bearer tokens appear in stdout, logs, results, or artifacts | Run regex scanner over raw files | Planned |
| M7-803 | Denylist check | Verify results and derived outputs remain in directories blocked by retrieval denylist | Run retrieval spec tests | Planned |
| M7-804 | Typed Provenance | Leakage checks must use typed structural/provenance tests. Keyword scan is only supplementary | Verify audit parser checks structure of prompts/requests | Planned |

### M7.9 Manual Review
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-901 | Blind review package | Generate randomized review package with `strategy` labels hidden | Verify output CSV/JSON has no strategy columns | Completed |
| M7-902 | Scoring storage | Ratings are appended to a separate review file (`results/reviews/review_results.jsonl`) without modifying raw results | Verify scoring appends to review file and matches schema | Completed |
| M7-903 | Anonymization | Reviewer package must omit all metadata (run_id, artifact paths, tool calls, logs, latency, tokens) | Check exported review fields in `test_blind_reviews.py` | Completed |
| M7-904 | Mapping Isolation | Evaluator-only mapping file is stored exclusively and not exposed to reviewers or models | Verify map file location and permissions | Completed |
| M7-905 | Mapping strictness | Unknown blind IDs or duplicate review scores must trigger immediate fail-closed | Verify review recorder raises errors on duplicates | Completed |

### M7.10 Final Results
| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7-1001 | Derived CSV | Derived CSV is generated only from the raw result JSONL | Verify CSV parsing from raw JSONL | Planned |
| M7-1002 | Summary Markdown | Summary Markdown aggregates runs without reading workspaces or prompts | Verify summary details match raw JSONL content | Planned |

---

## 3. Verification Commands

These commands will be implemented and executed in M7 implementation phase:

```powershell
# Run all unit and integration tests
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/live -v
python -B -m pytest tests/leakage -v
python -B -m pytest -q

# Run static scans
rg -n "Authorization|api_key|secret" results/raw/
```
