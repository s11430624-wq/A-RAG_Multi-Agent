# Milestone 6 Acceptance Plan: Experiment Runner, CLI, Results, Resume, and Derived Outputs

**Status:** Completed

This matrix records the verified M6 implementation state. No live model call is claimed; live boundaries were verified without constructing live transport.

## 1. Planned Deliverables

| Area | Planned files | Status |
| :--- | :--- | :--- |
| Runner package | `experiments/runner/` modules defined by the M6 plan | Completed |
| CLI | `experiments/cli.py` | Completed |
| Runner tests | `tests/runner/` | Completed |
| Leakage tests | `tests/leakage/test_runner_leakage.py` | Completed |
| Optional live boundary tests | `tests/live/test_m6_live_boundary.py` | Completed |
| Raw results | `results/raw/{experiment_id}.jsonl`, implementation-time output only | Completed |
| Derived outputs | `results/derived/{experiment_id}.csv` and summary Markdown, implementation-time output only | Completed |
| Existing contracts/config/tasks/M1-M5 | Unchanged unless a future approved blocker revision permits otherwise | Verified unchanged |

## 2. Acceptance Matrix

| ID | Area | Requirement | Verification method | Status |
| :--- | :--- | :--- | :--- | :--- |
| M6-001 | M6.0 planning/readiness | M6 plan exists and uses task-by-task TDD execution format | Review `docs/superpowers/plans/2026-06-11-m6-experiment-runner.md` | Completed |
| M6-002 | M6.0 planning/readiness | Acceptance matrix exists with all items initially Planned | Review this file | Completed |
| M6-003 | M6.0 planning/readiness | Implementation starts from a green M1-M5 baseline | `python -B -m pytest -q` before M6 code | Completed |
| M6-004 | M6.0 planning/readiness | No M6 code or tests exist before implementation begins | `rg --files experiments/runner tests/runner experiments/cli.py` should fail before Task 1 | Completed |
| M6-005 | M6.0 planning/readiness | Required files from M1-M5 are present | Preflight existence test | Completed |
| M6-006 | M6.0 planning/readiness | M6 does not modify contracts, configs, tasks, student system, hidden tests, reference patches, M3-M5 behavior | File diff/static guard | Completed |
| M6-007 | M6.0 planning/readiness | All M6 implementation tests are written RED before production code | Per-task RED evidence log | Completed |
| M6-008 | M6.0 planning/readiness | Ordinary tests do not require network or credentials | Network denial monkeypatch/static scan | Completed |
| M6-009 | M6.1 config + scheduler | Existing experiment/model YAML loads into frozen `ExperimentConfig` | `tests/runner/test_config.py` | Completed |
| M6-010 | M6.1 config + scheduler | Strategies validate as exactly A/C/E unless an explicit subset is supplied | Invalid strategy fixtures | Completed |
| M6-011 | M6.1 config + scheduler | Repetitions must be positive integer and not bool | Config validation matrix | Completed |
| M6-012 | M6.1 config + scheduler | `max_repair_rounds` must be integer 0..2 and compatible with task limits | Config/task validation tests | Completed |
| M6-013 | M6.1 config + scheduler | Seed must be a real integer and shared across A/C/E | Config validation and request capture | Completed |
| M6-014 | M6.1 config + scheduler | Model profile must exist in `configs/models.yaml` | Missing model fixture | Completed |
| M6-015 | M6.1 config + scheduler | Config and provider objects contain no credential-like keys | Recursive config scan | Completed |
| M6-016 | M6.1 config + scheduler | Result roots resolve under repo and reject traversal/sibling-prefix/symlink escape | Path attack tests | Completed |
| M6-017 | M6.1 config + scheduler | Live mode fails closed without explicit env opt-in | Live config negative test | Completed |
| M6-018 | M6.1 config + scheduler | Scheduler produces 45 runs for 5 tasks x 3 strategies x 3 repetitions | Scheduler count test | Completed |
| M6-019 | M6.1 config + scheduler | Scheduler ordering is deterministic | Repeated scheduler equality test | Completed |
| M6-020 | M6.1 config + scheduler | `experiment_id` is deterministic and Windows-safe | ID regex test | Completed |
| M6-021 | M6.1 config + scheduler | `run_id` includes experiment/task/strategy/repetition/seed and is Windows-safe | ID shape test | Completed |
| M6-022 | M6.1 config + scheduler | All run IDs are unique | Set cardinality test | Completed |
| M6-023 | M6.1 config + scheduler | Scheduler dry-run creates no result, workspace, artifact, or retrieval log files | Filesystem assertion | Completed |
| M6-024 | M6.1 config + scheduler | Task records are schema-valid before scheduling | Task schema validation test | Completed |
| M6-025 | M6.1 config + scheduler | Full task mapping is not passed to strategy constructors | Type guard test | Completed |
| M6-026 | M6.1 config + scheduler | A/C/E share task description, starter files, repair limit, seed, model config, and public feedback policy | Captured run-plan equality | Completed |
| M6-027 | M6.1 config + scheduler | C and E use identical raw templates, with E differing only by retrieval capability/evidence | Existing M5 template tests plus factory capture | Completed |
| M6-028 | M6.1 config + scheduler | Strategy E builds exactly one `FrozenRetrievalStore` per run/task | Store builder counter | Completed |
| M6-029 | M6.1 config + scheduler | Strategy A/C never construct retrieval facade/session | Monkeypatch constructor denial | Completed |
| M6-030 | M6.2 result writer + resume | Result writer validates against `result.schema.json` before opening file | Schema failure zero-write test | Completed |
| M6-031 | M6.2 result writer + resume | Result writer writes canonical UTF-8 JSON with one LF per record | Byte assertion | Completed |
| M6-032 | M6.2 result writer + resume | Result writer fsyncs after append | Monkeypatch fsync spy | Completed |
| M6-033 | M6.2 result writer + resume | Partial write failure rolls back to original bytes | Half-line monkeypatch test | Completed |
| M6-034 | M6.2 result writer + resume | Rollback failure raises `result_integrity_unknown=True` | Rollback failure monkeypatch test | Completed |
| M6-035 | M6.2 result writer + resume | Writer rejects absolute path, `..`, sibling-prefix, and symlink/junction escape | Path guard tests | Completed |
| M6-036 | M6.2 result writer + resume | Writer rejects duplicate run ID before append | Duplicate JSONL fixture | Completed |
| M6-037 | M6.2 result writer + resume | Existing malformed JSONL line fails closed during resume | Resume malformed-line test | Completed |
| M6-038 | M6.2 result writer + resume | Resume skips only schema-valid completed run IDs | Completed index test | Completed |
| M6-039 | M6.2 result writer + resume | Resume never reads prompt/response/artifact/retrieval log files as input | Path open spy | Completed |
| M6-040 | M6.2 result writer + resume | Results under `results/raw/` remain retrieval-denied | M4 denylist assertion | Completed |
| M6-041 | M6.2 result writer + resume | Multi-process concurrent append is documented unsupported and not silently enabled | Writer interface review and test | Completed |
| M6-042 | M6.3 strategy/evaluator orchestration | Orchestrator calls `generate_initial_patch()` exactly once per run | Fake strategy counter | Completed |
| M6-043 | M6.3 strategy/evaluator orchestration | Evaluator receives patch strings, not a Strategy object | Evaluator spy | Completed |
| M6-044 | M6.3 strategy/evaluator orchestration | Pass@1 evaluator call uses no repair patches | Evaluator spy | Completed |
| M6-045 | M6.3 strategy/evaluator orchestration | Public pass stops repair immediately | Public-pass fake evaluator | Completed |
| M6-046 | M6.3 strategy/evaluator orchestration | Hidden failure alone does not trigger repair | Hidden-fail/public-pass fixture | Completed |
| M6-047 | M6.3 strategy/evaluator orchestration | Public failure creates `SanitizedPublicFeedback` only from public feedback history | Sentinel feedback test | Completed |
| M6-048 | M6.3 strategy/evaluator orchestration | Strategy repair never receives private audit or hidden details | Type/sentinel test | Completed |
| M6-049 | M6.3 strategy/evaluator orchestration | Repair rounds are capped at two | Counter and result assertion | Completed |
| M6-050 | M6.3 strategy/evaluator orchestration | A schedule max remains 3 provider calls | Fake provider schedule test | Completed |
| M6-051 | M6.3 strategy/evaluator orchestration | C schedule max remains 5 provider calls | Fake provider schedule test | Completed |
| M6-052 | M6.3 strategy/evaluator orchestration | E schedule max remains 14 provider calls and accepted tool calls are separate | Fake provider + retrieval test | Completed |
| M6-053 | M6.3 strategy/evaluator orchestration | Strategy finalization happens only after the full evaluator/repair flow | Artifact manifest timing test | Completed |
| M6-054 | M6.3 strategy/evaluator orchestration | Result artifact path comes only from `StrategyFinalization` | Projection test | Completed |
| M6-055 | M6.3 strategy/evaluator orchestration | Terminal strategy failure closes session and rolls back staged artifact bundle | Failure cleanup test | Completed |
| M6-056 | M6.3 strategy/evaluator orchestration | Successful finalized artifact is preserved after close | Finalized close test | Completed |
| M6-057 | M6.3 strategy/evaluator orchestration | Invalid patch maps to schema `invalid_patch` | Failure classification test | Completed |
| M6-058 | M6.3 strategy/evaluator orchestration | Patch apply failure maps to schema `patch_apply_error` | Failure classification test | Completed |
| M6-059 | M6.3 strategy/evaluator orchestration | Provider timeout maps to schema `model_timeout` | Failure classification test | Completed |
| M6-060 | M6.3 strategy/evaluator orchestration | Gateway/auth transport failure maps to schema `gateway_error` without credential leakage | Failure classification and scan | Completed |
| M6-061 | M6.3 strategy/evaluator orchestration | Finish reason/parser/artifact/projection failures map to schema `unknown` infra errors | Failure classification matrix | Completed |
| M6-062 | M6.3 strategy/evaluator orchestration | Missing provider usage is not exported as fake successful token counts | Projection failure test | Completed |
| M6-063 | M6.3 strategy/evaluator orchestration | Successful result records use real M5 projected tool/token/latency/artifact fields | Projection equality test | Completed |
| M6-064 | M6.3 strategy/evaluator orchestration | Result JSONL contains no raw prompts, raw responses, hidden test paths, or private audit details | Serialized result scan | Completed |
| M6-065 | M6.3 strategy/evaluator orchestration | Retrieval logs for E are under approved `results/raw/retrieval/` root and `.jsonl` | Path assertion | Completed |
| M6-066 | M6.3 strategy/evaluator orchestration | A/C result retrieval fields are `tool_calls=0`, `retrieved_tokens=0`, `retrieval_success=null` | Result assertion | Completed |
| M6-067 | M6.3 strategy/evaluator orchestration | E result retrieval fields come from operational M5 metrics | Result assertion | Completed |
| M6-068 | M6.3 strategy/evaluator orchestration | Total run timeout failure is classified as infra without leaking hidden output | Timeout fake test | Completed |
| M6-069 | M6.4 derived outputs | CSV is generated only from raw JSONL | Open spy test | Completed |
| M6-070 | M6.4 derived outputs | CSV includes required minimum columns | Header assertion | Completed |
| M6-071 | M6.4 derived outputs | CSV row ordering is deterministic | Repeated generation hash test | Completed |
| M6-072 | M6.4 derived outputs | Summary Markdown is generated only from raw JSONL | Open spy test | Completed |
| M6-073 | M6.4 derived outputs | Summary aggregates per task/strategy without reading artifacts | Summary content and open spy | Completed |
| M6-074 | M6.4 derived outputs | Derived generation rejects malformed raw JSONL | Malformed raw fixture | Completed |
| M6-075 | M6.4 derived outputs | Derived output paths reject escape and sibling-prefix attacks | Path guard test | Completed |
| M6-076 | M6.4 derived outputs | `results/derived/` remains retrieval-denied | M4 denylist assertion | Completed |
| M6-077 | M6.5 leakage + full regression | Hidden tests content never enters strategy/provider/result/artifact/retrieval log | Sentinel scan | Completed |
| M6-078 | M6.5 leakage + full regression | `required_evidence` and `grading` never enter model-visible task or provider request | Sentinel/type test | Completed |
| M6-079 | M6.5 leakage + full regression | Previous run artifacts never become later strategy inputs | Cross-run open spy | Completed |
| M6-080 | M6.5 leakage + full regression | Previous raw results never become strategy inputs | Cross-run open spy | Completed |
| M6-081 | M6.5 leakage + full regression | Workspaces are cleaned or isolated after each run | Filesystem residue test | Completed |
| M6-082 | M6.5 leakage + full regression | No `__pycache__`, pyc/pyo, pytest cache, test JSONL, temp sandbox, patch tmp/bak residue remains | Residue scan | Completed |
| M6-083 | M6.5 leakage + full regression | M1-M5 tests remain green | Full pytest | Completed |
| M6-084 | M6.5 leakage + full regression | No production network client is introduced for ordinary M6 | Static scan | Completed |
| M6-085 | M6.5 leakage + full regression | No credential literal appears in results, artifacts, summaries, logs, or errors | Recursive scan | Completed |
| M6-086 | M6.5 leakage + full regression | Result schema remains unchanged | File hash/diff check | Completed |
| M6-087 | M6.5 leakage + full regression | Task/config files remain unchanged unless a future authorized blocker revision permits otherwise | File hash/diff check | Completed |
| M6-088 | M6.5 leakage + full regression | Two consecutive complete pytest runs pass with zero failures/errors and only expected skips | Final verification | Completed |
| M6-089 | M6.6 optional live smoke gated test | Importing M6 live boundary reads no credential and opens no network | Import spy test | Completed |
| M6-090 | M6.6 optional live smoke gated test | Live mode is rejected or skipped without `ARAG_RUN_LIVE_GATEWAY=1` | Env-negative test | Completed |
| M6-091 | M6.6 optional live smoke gated test | Credential injection is confined to future live transport send boundary | Boundary spy/static scan | Completed |
| M6-092 | M6.6 optional live smoke gated test | Ordinary pytest never performs Hermes/Gateway/OpenAI-Compatible/OpenAI/model API calls | Network monkeypatch and static scan | Completed |
| M6-093 | M6.3 strategy/evaluator orchestration | Pass@1 result fields come only from the first evaluator call | Snapshot merge unit test | Completed |
| M6-094 | M6.3 strategy/evaluator orchestration | Later repair evaluator calls never overwrite Pass@1 public/hidden counts | Repair final-pass fixture | Completed |
| M6-095 | M6.3 strategy/evaluator orchestration | Final public/hidden fields come only from the last available evaluator snapshot | Multi-snapshot merge test | Completed |
| M6-096 | M6.3 strategy/evaluator orchestration | Initial strategy failure before evaluator produces Pass@1 and final false/zero fields | Pre-initial failure fixture | Completed |
| M6-097 | M6.3 strategy/evaluator orchestration | Repair strategy failure preserves Pass@1 and uses latest available final snapshot while terminal error fields reflect failure | Repair failure fixture | Completed |
| M6-098 | M6.3 strategy/evaluator orchestration | `merge_evaluator_snapshots()` is the sole helper projecting Pass@1/final evaluator fields into the result record | Unit test and static scan | Completed |
| M6-099 | M6.1 config + scheduler | `artifact_root` is derived exactly as `raw_results_dir / "artifacts"` | Config path derivation test | Completed |
| M6-100 | M6.1 config + scheduler | `retrieval_log_root` is derived exactly as `raw_results_dir / "retrieval"` | Config path derivation test | Completed |
| M6-101 | M6.1 config + scheduler | Raw JSONL, derived CSV, and summary paths are derived exactly from experiment ID and configured roots | Scheduler path test | Completed |
| M6-102 | M6.1 config + scheduler | Config-provided `artifact_root` or `retrieval_log_root` overrides are rejected | Extra-key config fixture | Completed |
| M6-103 | M6.1 config + scheduler | Derived artifact/retrieval paths must remain inside raw results root and repo root | Path escape tests | Completed |
| M6-104 | M6.1 config + scheduler | Derived CSV and summary paths must remain inside derived results root and repo root | Path escape tests | Completed |
| M6-105 | M6.3 strategy/evaluator orchestration | Successful flow with missing M5 usage cannot be exported as `valid_run=true` | Projection failure test | Completed |
| M6-106 | M6.3 strategy/evaluator orchestration | Missing-usage projection failure maps to `valid_run=false`, `infra_error=true`, `error_type="unknown"`, `stop_reason="infra_error"` | Projection failure test | Completed |
| M6-107 | M6.3 strategy/evaluator orchestration | Failure fallback token zeros are documented and used only as failure-only schema values | Failure result schema test | Completed |
| M6-108 | M6.3 strategy/evaluator orchestration | Missing-usage failure preserves artifact path only when finalization already succeeded | Finalization/projection ordering test | Completed |
| M6-109 | M6.1 config + scheduler | `load_experiment_config()` accepts `mode` from caller and never infers live mode from YAML | Config loader signature and behavior test | Completed |
| M6-110 | M6.1 config + scheduler | `load_experiment_config()` accepts injected `env` mapping and checks only `ARAG_RUN_LIVE_GATEWAY` for live gating | Env mapping test | Completed |
| M6-111 | M6.6 optional live smoke gated test | `mode="live"` fails closed when `ARAG_RUN_LIVE_GATEWAY != "1"` | Env-negative live test | Completed |
| M6-112 | M6.6 optional live smoke gated test | `mock_run` and `dry_run` do not read credential environment variables or construct live transport | Credential env spy test | Completed |
| M6-113 | M6.3 strategy/evaluator orchestration | Success and failure records use nonnegative monotonic elapsed time measured before result record construction | Fake-clock success/failure tests | Completed |
| M6-114 | M6.3 strategy/evaluator orchestration | Result latency excludes JSONL append, flush, and fsync time | Record-before-append ordering review | Completed |
| M6-115 | M6.3 strategy/evaluator orchestration | `test_latency_seconds` accumulates every completed initial and repair evaluator call and preserves completed latency on later failure | Three-evaluator and repair-failure tests | Completed |
| M6-116 | M6.3 strategy/evaluator orchestration | Ordinary strategy/evaluator/projection failure closes or rolls back the session successfully before one failure-record append | Close ordering and append-count tests | Completed |
| M6-117 | M6.3 strategy/evaluator orchestration | Artifact close failure, including `artifact_integrity_unknown=True`, propagates with zero append and leaves resume incomplete | Artifact close attack probe | Completed |
| M6-118 | M6.3 strategy/evaluator orchestration | Finalized session close failure prevents append, while BaseException cleanup preserves the original interrupt and writes nothing | Finalized-close and interrupt-precedence tests | Completed |
| M6-119 | M6.3 CLI | Cleanup execution failure increments `execution_failures` and `infra_failures`, not `written` or `writer_failures`, and returns nonzero | CLI summary and exit-code tests | Completed |

## 3. Verification Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/runner -v
python -B -m pytest tests/leakage -v
python -B -m pytest tests/retrieval -v
python -B -m pytest tests/strategies -v
python -B -m pytest tests/providers -v
python -B -m pytest tests/contracts tests/m2 tests/runtime -v
python -B -m pytest tests/live -v
python -B -m pytest -q
python -B -m pytest -q
```

Static scans:

```powershell
rg -n "required_evidence|grading|hidden_test_id|PrivateAuditRecord" experiments/runner experiments/cli.py
rg -n "api_key|API_KEY|authorization|credential|secret" experiments/runner experiments/cli.py tests/runner tests/live
rg -n "requests|httpx|urllib|socket|vertex|gemini|Hermes|OpenAI|api_key|API_KEY" experiments/runner experiments/cli.py tests/runner
rg -n "results/derived|results/raw|workspaces" experiments/retrieval tests/retrieval
```

## 4. Known Limits

- M3 evaluator has no callback interface. M6 uses a wrapper/orchestrator with repeated evaluator calls and accumulated patch lists.
- The total run timeout is a cooperative monotonic deadline checked at M6 operation boundaries. Existing provider and test timeouts remain responsible for interrupting a single blocking operation.
- Current result schema cannot represent detailed provider/parser/artifact errors. M6 maps them into existing enum values.
- Current result schema requires integer token fields. Missing provider usage is exported only as an infrastructure failure placeholder.
- Current experiment config has no live execution opt-in field. Live mode fails closed unless explicitly authorized through caller mode and environment gate.
- Current M3 workspace manager uses temporary directories and does not consume `workspace_base_dir`; M6 does not claim configured persistent workspace behavior.

## 5. Completion Confirmation

- All 119 acceptance items are Completed.
- M6 implementation code, CLI, and tests are limited to the M6-approved runner/CLI/test surfaces.
- No implementation-time result JSONL, derived output, workspace, artifact, or retrieval log remains after verification.
- No schema, config, task, student-system, hidden-test, reference-patch, evaluator, runtime, retrieval, provider, strategy, or M1-M5 behavior is modified.
- No model, Hermes, Gateway, OpenAI-Compatible, OpenAI, external API, or network call is made by ordinary M6 tests.
