# M7-D Acceptance: Smoke Planning and Approval Gate

**Status:** M7-D.0 Completed; M7-D.1A Offline Integration Completed; M7-D.1B Live Composition Wiring Completed; M7-D.2 execution Completed

## Scope

M7-D.0 delivers only the smoke execution plan, explicit approval gate, gate tests, and acceptance documentation. It does not execute smoke, full run, strategies, retrieval, or model calls, and it creates no execution outputs.

M7-D.1A adds an offline smoke execution pipeline callable only through direct test injection of a fake/scripted provider transport. The executor uses the production scheduler, A/C/E strategy sessions, orchestrator, evaluator, retrieval facade, artifact writer, and result writer. Synthetic JSONL, workspaces, artifacts, retrieval logs, and the canonical report are restricted to pytest `tmp_path`. The production CLI remains disabled.

M7-D.1B composes the production Local OpenAI-Compatible Proxy provider and no-auth loopback transport for each A/C/E run, validates readiness, and reserves every transport attempt. It does not execute `SmokeExecutor`, send HTTP, probe the gateway, call models, or create execution outputs.

## Acceptance Matrix

| ID | Requirement | Verification | Status |
| :--- | :--- | :--- | :--- |
| M7D-001 | Plan fixes scope to exactly T01 x A/C/E, repetition 1, seed 42 | Review `2026-06-11-m7d-smoke-run-plan.md` | Completed |
| M7D-002 | Plan fixes model, provider, and localhost API base | Plan review | Completed |
| M7D-003 | Smoke ID exactly matches `^m7d_smoke_[0-9]{8}T[0-9]{6}Z$`; traversal, separators, drive paths, URL encoding, and noncanonical names are rejected | Canonical ID gate tests | Completed |
| M7D-004 | Live approval requires both env gates and `--human-approval SMOKE_RUN` | `test_live_smoke_requires_env_and_human_approval` | Completed |
| M7D-005 | Environment-only opt-in cannot start smoke | `test_live_smoke_does_not_start_from_env_only` | Completed |
| M7D-006 | Non-smoke experiment IDs are rejected | `test_live_smoke_rejects_without_smoke_experiment_id` | Completed |
| M7D-007 | Full-run-only flags are rejected by `live-smoke` | `test_live_smoke_rejects_full_run_flags` | Completed |
| M7D-008 | Resolved raw, artifact, retrieval, and report paths pass `Path.relative_to()` against their exact approved roots and match the smoke ID | Path containment gate tests | Completed |
| M7D-009 | Budget is the exact approved tuple: calls 22, input 120000, output 48000, wall clock 1800, consecutive infra threshold 2 | Above/below/exact budget tests | Completed |
| M7D-009A | Provider-call budget matches worst-case schedule A(3) + C(5) + E(14) = 22 | `test_smoke_provider_call_budget_matches_a_c_e_maximum_schedule` | Completed |
| M7D-010 | Unknown pricing is only the `unknown_cost` risk flag | Plan and smoke gate contract review | Completed |
| M7D-011 | Expected 3-record, schema, usage, manifest, retrieval, and leakage checks are defined | Plan review | Completed |
| M7D-012 | Canonical report and three SHA-256 bindings are defined | Plan review | Completed |
| M7D-013 | Fail-closed and rollback conditions prohibit automatic full run | Plan review | Completed |
| M7D-014 | Passing all M7-D.0 CLI gates still cannot execute smoke | CLI returns code 2 with execution-disabled message | Completed |
| M7D-015 | No execution residue is created during M7-D.0 | Residue scan: only pre-existing `.gitkeep` files remain | Completed |
| M7D-101 | Frozen `SmokeExecutionRequest` binds experiment, synthetic output roots, budgets, and injected provider factory | Executor integration tests | Completed |
| M7D-102 | Executor plans exactly T01 x A/C/E, repetition 1, seed 42, sequential single-process execution | Three-run/order tests | Completed |
| M7D-103 | Every run receives an independent injected provider and the production A/C/E session from `StrategyFactory` | Provider identity and real-session type assertions | Completed |
| M7D-104 | Every transport attempt is reserved before transport; success, failure, timeout, and retry consume the 22-attempt limit, while token recording never double-counts calls | Failed/retry/attempt-23 budget tests | Completed |
| M7D-104A | The 22-attempt ceiling deliberately provides no retry headroom for the 22-call A/C/E schedule; attempt 23 fails closed, and any higher retry budget requires a separate M7-D.0 amendment | Budget tests and plan review | Completed |
| M7D-105 | Abort writes no incomplete run record, preserves prior valid records, quarantines execution, and creates no report | Infra/token abort tests | Completed |
| M7D-106 | Production sessions generate A(3), C(5), and E(14) logical model-call schedules from parser-valid scripted responses | Session call-record assertions | Completed |
| M7D-107 | Manifest call records preserve provider-normalized usage audit metadata and token invariants | Manifest/auditor tests | Completed |
| M7D-108 | SmokeGateAuditor hashes and validates physical synthetic JSONL, manifests, and retrieval log | Canonical report and tamper tests | Completed |
| M7D-109 | Unknown pricing remains `estimated_cost=null`, `cost_known=false`, and `risk_flags=["unknown_cost"]` | Report assertions | Completed |
| M7D-110 | Socket/network and credential environment access fail tests immediately | Offline isolation test | Completed |
| M7D-111 | M7-D.1A established that production `live-smoke` remains non-executable and returns code 2; M7-D.1B preserves that boundary with the composition-validated message | CLI boundary tests | Completed |
| M7D-112 | `ExperimentOrchestrator` invokes the `Evaluator` interface for all 9 initial/repair rounds and hidden results never enter provider prompts; M7-D.1A artifact regression uses a deterministic evaluator fixture and does not execute hidden tests | Evaluator invocation/provider-request assertions | Completed |
| M7D-113 | E builds one production `FrozenStore`, opens role-bound `RetrievalFacade` sessions, and writes 9 real retrieval records; A/C have no retrieval session | Retrieval facade/session/log assertions | Completed |
| M7D-114 | `ArtifactBundleWriter`, production result builder, and `ResultJsonlWriter` create all manifests and result records; the executor contains no manual synthetic output builders | Writer spies and source guard | Completed |
| M7D-115 | `StrategyFactory` passes validated `ProviderConfig.provider_id` into `ArtifactBundleWriter`; provider ID is present in the original canonical finalized bytes and covered by `StrategyFinalization.manifest_sha256` | Artifact/factory SHA assertions | Completed |
| M7D-116 | `manifest.json` is the final exclusive-created artifact; orchestrator return and gate audit do not mutate it, and a second finalization against the same path fails closed | Byte-stability and exclusive-create tests | Completed |
| M7D-201 | Public composition callables build a canonical `SmokeExecutionRequest` and three independent A/C/E `OpenAICompatibleProvider` instances through `LiveProviderFactory` | Composition tests | Completed |
| M7D-202 | Provider/model/seed/API base exactly match validated YAML and the approved Local OpenAI-Compatible Proxy tuple | Config mismatch tests | Completed |
| M7D-203 | Every provider uses no-auth loopback, has no credential provider, and emits no Authorization header | Transport composition tests | Completed |
| M7D-204 | `AttemptReservingTransport` reserves immediately before every sender call, including retries; attempt 23 is blocked before send | Scripted sender budget tests | Completed |
| M7D-205 | CLI validates composition without calling `SmokeExecutor.execute()`, transport send, socket, urlopen, strategy, evaluator, or retrieval | No-execution/no-network CLI tests | Completed |
| M7D-206 | Missing gates, non-live mode, path/budget mismatch, provider drift, localhost/8788/Cloudflare endpoints, and credential-like config fail closed without outputs | Validation failure tests | Completed |
| M7D-207 | Valid CLI returns code 2 with `live-smoke composition validated, execution requires M7-D.2 approval.` | CLI boundary test | Completed |
| M7D-208 | BaseException from composition/transport is not swallowed | BaseException propagation tests | Completed |

## Approval State

- Planning/gate approval: completed.
- Offline fake execution integration: completed.
- Live provider composition wiring (M7-D.1B): completed.
- Real smoke execution (M7-D.2): Completed and Verified (Exactly 3 runs: T01 x A / C / E).
- Full-run approval: not granted.
- Next state: `M7-D.2 one-shot 3-run live smoke completed and verified. M7-D outputs are frozen and bound by hashes. M7-E full 45-run remains Planned/Blocked pending explicit approval. Existing smoke files must not be mutated.`

## Verification Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest tests/live tests/leakage -q
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```
