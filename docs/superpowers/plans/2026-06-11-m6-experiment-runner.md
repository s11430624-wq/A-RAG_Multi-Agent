# M6 Experiment Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic experiment execution layer that schedules every task/strategy/repetition run, orchestrates M5 strategies around the M3 evaluator, writes append-only result JSONL, supports resume, and derives CSV/Markdown outputs without leaking hidden data or entering live execution by default.

**Architecture:** M6 adds a thin orchestration layer above existing M1-M5 modules. It does not change task/result schemas, M3 evaluator internals, M4 retrieval, or M5 strategy behavior; instead, it validates config, constructs run plans, calls strategy sessions, calls the evaluator with patch strings only, finalizes artifacts after the full run flow, and writes schema-valid result records atomically. Derived outputs are generated only from raw JSONL.

**Tech Stack:** Python 3.11 standard library, `pyyaml`, `jsonschema`, existing M3 evaluator/runtime, existing M4 retrieval facade/log writer, existing M5 providers/strategies/artifacts, pytest. Ordinary tests use deterministic fake providers and no network.

**Status:** Planned

---

## 0. Planning Scope Guard

This planning round may create or modify only:

- `docs/superpowers/plans/2026-06-11-m6-experiment-runner.md`
- `docs/milestones/M6_acceptance.md`

This planning round must not create or modify implementation code, tests, results, workspaces, configs, schemas, tasks, student-system files, hidden tests, reference patches, M1-M5 production behavior, or M6 outputs.

Future M6 implementation may create the files explicitly named in this plan, but the implementation worker must still follow TDD and stop if any required forbidden change becomes necessary.

## 1. Files Read During Planning

All requested files existed and were inspected:

- `README.md`
- `docs/experiment-contract.md`
- `docs/superpowers/plans/2026-06-11-m5-provider-strategies.md`
- `docs/milestones/M5_acceptance.md`
- `contracts/task.schema.json`
- `contracts/result.schema.json`
- `contracts/retrieval-log.schema.json`
- `configs/experiment.yaml`
- `configs/models.yaml`
- `experiments/tasks.json`
- `experiments/evaluation/evaluator.py`
- `experiments/evaluation/metrics.py`
- `experiments/runtime/workspace.py`
- `experiments/runtime/patching.py`
- `experiments/runtime/test_runner.py`
- `experiments/retrieval/service.py`
- `experiments/retrieval/logging.py`
- `experiments/strategies/base.py`
- `experiments/strategies/single_llm.py`
- `experiments/strategies/multi_agent.py`
- `experiments/strategies/arag_multi_agent.py`
- `experiments/strategies/models.py`
- `experiments/strategies/metrics.py`
- `experiments/strategies/artifacts.py`
- `tests/runtime/test_evaluator_integration.py`
- `tests/strategies/test_repair_boundary.py`
- `tests/retrieval/test_retrieval_permissions.py`
- `tests/leakage/`

No missing file blocker was found.

## 2. Existing Contract Facts M6 Must Respect

1. `Evaluator.evaluate_task()` accepts `task_id`, `initial_patch`, a sequence of precomputed `repair_patches`, `max_repair_rounds`, and result metadata kwargs. It does not accept a callback or a strategy object.
2. The evaluator stores sanitized public feedback in `public_feedback_history` and private hidden metrics in `_private_audit_records`. M6 must never pass private records into any strategy.
3. Repair stop decisions must be based only on public pass/fail status. Hidden pass/fail is recorded in result metrics but cannot trigger repair.
4. `result.schema.json` has required integer `input_tokens` and `output_tokens`. M5 `project_for_result_schema()` raises `ProviderUsageUnavailableError` if any successful provider call lacks usage.
5. `result.schema.json` error enum is limited to `none`, `gateway_error`, `model_timeout`, `test_timeout`, `empty_response`, `invalid_patch`, `patch_apply_error`, `runner_error`, and `unknown`. M6 must map richer M5 errors into this enum without changing schema.
6. `StrategyFinalization.artifact_path` is a relative run artifact root string and is sufficient for `result.schema.json.artifact_path`.
7. M5 strategy generate methods stage artifacts but do not write a manifest; `finalize()` writes the manifest last and seals the session.
8. M4 retrieval builds stores only for Strategy E and retrieval logs must use a caller-approved `.jsonl` path under an approved log root.
9. `results/`, `workspaces/`, hidden tests, reference patches, cache, and artifacts remain denied corpus sources.
10. Current `configs/experiment.yaml` contains strategies, repetitions, max repair rounds, seed, timeout values, and result/workspace paths, but has no explicit live-provider opt-in field.

## 3. M6 Architecture

M6 introduces these future modules:

```text
experiments/
  cli.py                  # argparse CLI entrypoint for dry-run/mock-run/derive
  runner/
    __init__.py
    config.py             # experiment config validation and typed config
    identity.py           # experiment_id, run_id, repetition_id
    scheduler.py          # task x strategy x repetition run plan
    strategy_factory.py   # A/C/E session construction with fake/offline provider
    result_writer.py      # append-only schema-valid JSONL writer
    resume.py             # completed-run index and duplicate detection
    orchestrator.py       # one-run strategy/evaluator loop
    projection.py         # evaluator + strategy finalization -> result record
    derived.py            # CSV and summary from raw JSONL only
    errors.py             # runner error taxonomy and schema mappings
```

Future tests:

```text
tests/runner/
  conftest.py
  test_config.py
  test_identity_scheduler.py
  test_strategy_factory.py
  test_result_writer.py
  test_resume.py
  test_orchestrator.py
  test_projection.py
  test_derived_outputs.py
  test_cli.py
tests/leakage/test_runner_leakage.py
tests/live/test_m6_live_boundary.py
```

M6 will keep `experiments/evaluation/`, `experiments/runtime/`, `experiments/retrieval/`, and `experiments/strategies/` behavior unchanged unless a future explicitly approved blocker revision says otherwise.

## 4. Public Interfaces To Implement

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Protocol

StrategyName = Literal["A", "C", "E"]
RunMode = Literal["dry_run", "mock_run", "live"]
ResultErrorType = Literal[
    "none",
    "gateway_error",
    "model_timeout",
    "test_timeout",
    "empty_response",
    "invalid_patch",
    "patch_apply_error",
    "runner_error",
    "unknown",
]
StopReason = Literal["public_pass", "repair_limit", "infra_error"]

@dataclass(frozen=True)
class ExperimentPaths:
    tasks_definition: Path
    raw_results_dir: Path
    derived_results_dir: Path
    reviews_dir: Path
    workspace_base_dir: Path
    artifact_root: Path
    retrieval_log_root: Path

@dataclass(frozen=True)
class ExperimentConfig:
    strategies: tuple[StrategyName, ...]
    repetitions: int
    max_repair_rounds: int
    seed: int
    agent_timeout_seconds: float
    unit_test_timeout_seconds: float
    total_run_timeout_seconds: float
    paths: ExperimentPaths
    model_provider_id: str
    model: str
    mode: RunMode
    live_opt_in: bool

@dataclass(frozen=True)
class RunIdentity:
    experiment_id: str
    task_id: str
    strategy: StrategyName
    repetition: int
    seed: int
    run_id: str

@dataclass(frozen=True)
class PlannedRun:
    identity: RunIdentity
    task_record: dict
    task_index: int
    strategy_index: int
    repetition_index: int

@dataclass(frozen=True)
class SchedulerPlan:
    experiment_id: str
    runs: tuple[PlannedRun, ...]
    raw_jsonl_path: Path
    derived_csv_path: Path
    summary_path: Path

@dataclass(frozen=True)
class CompletedRunIndex:
    run_ids: frozenset[str]
    source_path: Path
    malformed_line_numbers: tuple[int, ...]

@dataclass(frozen=True)
class RunnerFailure:
    error_type: ResultErrorType
    stop_reason: StopReason
    infra_error: bool
    valid_run: bool
    message: str

@dataclass(frozen=True)
class EvaluatorRunSnapshot:
    pass1_public: bool
    pass1_hidden: bool
    pass1_public_tests_passed: int
    pass1_hidden_tests_passed: int
    final_public: bool
    final_hidden: bool
    public_tests_passed: int
    public_tests_total: int
    hidden_tests_passed: int
    hidden_tests_total: int
    repair_rounds: int
    patch_apply_failures: int
    test_latency_seconds: float
    raw_result: dict

@dataclass(frozen=True)
class MergedEvaluationSnapshots:
    pass1: EvaluatorRunSnapshot | None
    final_or_latest: EvaluatorRunSnapshot | None
    result_fields: dict

def merge_evaluator_snapshots(
    *,
    pass1: EvaluatorRunSnapshot | None,
    final_or_latest: EvaluatorRunSnapshot | None,
) -> MergedEvaluationSnapshots: ...

@dataclass(frozen=True)
class StrategyBundle:
    session: object
    provider: object
    strategy: StrategyName
    model: str
    seed: int
    retrieval_log_path: Path | None

@dataclass(frozen=True)
class RunExecutionResult:
    identity: RunIdentity
    result_record: dict
    finalization_artifact_path: str | None
    wrote_result: bool
    skipped_existing: bool

class ResultJsonlWriter:
    def __init__(self, *, approved_raw_root: Path, jsonl_path: Path, schema_path: Path) -> None: ...
    def append(self, record: dict) -> None: ...

class StrategyFactory:
    def create(self, *, run: PlannedRun, config: ExperimentConfig, repo_root: Path) -> StrategyBundle: ...

class ExperimentOrchestrator:
    def execute_run(self, run: PlannedRun) -> RunExecutionResult: ...

def load_experiment_config(
    *,
    experiment_path: Path,
    models_path: Path,
    repo_root: Path,
    mode: RunMode = "mock_run",
    env: Mapping[str, str] | None = None,
) -> ExperimentConfig: ...
```

### Deterministic IDs

`experiment_id` must be deterministic and Windows-safe:

```text
exp-{YYYYMMDD}-{model_slug}-seed{seed}-r{repetitions}
```

`model_slug` is lowercase ASCII with every non `[a-z0-9]+` span replaced by `-`, trimmed to 48 characters.

`run_id` must be:

```text
{experiment_id}__{task_id}__{strategy}__rep{repetition:02d}__seed{seed}
```

`run_id` may contain only `[A-Za-z0-9_.-]` and `__` separators. No slash, backslash, colon, whitespace, or path traversal segment is allowed.

### Derived Paths From Existing Config

M6 must not modify `configs/experiment.yaml` and must not expand the config
surface with `artifact_root` or `retrieval_log_root` overrides. `ExperimentPaths`
contains those fields only as derived values:

```python
raw_results_dir = resolve_under_repo(paths["raw_results_dir"])
derived_results_dir = resolve_under_repo(paths["derived_results_dir"])
artifact_root = raw_results_dir / "artifacts"
retrieval_log_root = raw_results_dir / "retrieval"
raw_jsonl_path = raw_results_dir / f"{experiment_id}.jsonl"
derived_csv_path = derived_results_dir / f"{experiment_id}.csv"
summary_path = derived_results_dir / f"{experiment_id}_summary.md"
```

Rules:

- Every derived path must resolve inside `repo_root`.
- `artifact_root` and `retrieval_log_root` must resolve inside `raw_results_dir`.
- `raw_jsonl_path` must resolve inside `raw_results_dir`.
- `derived_csv_path` and `summary_path` must resolve inside `derived_results_dir`.
- If YAML provides extra keys named `artifact_root` or `retrieval_log_root`, validation fails closed; M6 must not accept caller-provided overrides for these paths.
- These derived paths remain downstream outputs. `results/raw/`, `results/raw/artifacts/`, `results/raw/retrieval/`, and `results/derived/` must never become retrieval corpus roots.

## 5. Orchestration Algorithm

M6 must not modify `Evaluator` to call strategies. Instead, `ExperimentOrchestrator.execute_run()` controls one run:

1. Build `ModelVisibleTask` from the full task mapping using M5 visibility factory.
2. Create the strategy session through `StrategyFactory`.
3. Call `strategy.generate_initial_patch()`.
4. Call `Evaluator.evaluate_task(task_id, initial_patch, repair_patches=(), max_repair_rounds=0, metadata...)` to evaluate Pass@1 only.
5. If Pass@1 public passes, call `strategy.finalize()`, project strategy metrics, merge evaluator metrics, append result, and stop with `public_pass`.
6. If Pass@1 public fails and the task/config repair limit permits repair, convert only the evaluator's latest `PublicFeedbackRecord` into M5 `SanitizedPublicFeedback`.
7. Call `strategy.generate_repair_patch(feedback, previous_patch)`.
8. Re-evaluate from scratch with `Evaluator.evaluate_task(task_id, initial_patch, repair_patches=(repair1, ...), max_repair_rounds=len(repair_patches), metadata...)`.
9. Repeat until public pass or two repairs have been used.
10. After the final evaluator call, call `strategy.finalize()` exactly once, then project M5 metrics into result fields.
11. Append one schema-valid result JSONL record.
12. On terminal strategy/provider/artifact/projection failure, close the strategy session to rollback staged artifacts, map failure into a schema-valid result record when possible, append it if integrity is known, and never claim a completed run if append fails.

The repeated evaluator call pattern is inefficient but preserves M3 private audit isolation without changing M3. A future M3 callback API would be a separate milestone or approved M6 blocker revision.

`total_run_timeout_seconds` is enforced as a cooperative monotonic deadline.
The orchestrator checks the deadline before and after strategy factory creation,
initial generation, every evaluator call, every repair generation, finalization,
and result projection. Once expired, no later repair, provider turn,
finalization, or projection begins. A single blocking provider or test operation
is still interrupted by its existing provider/test timeout; the cooperative
deadline does not preempt Python code that is already blocked inside one call.

`latency_seconds` is the monotonic elapsed time from entry into
`execute_run()` through all required strategy, evaluator, finalization,
projection, and session cleanup work. The cutoff is immediately before result
record construction. Result JSONL validation, append, flush, and fsync are not
included. The value is clamped with `max(0.0, monotonic() - started_at)` so a
malformed injected test clock cannot produce a schema-invalid negative value.

`test_latency_seconds` is accumulated after every evaluator call that returns
a result. Pass@1 and final outcome fields still use the first/latest snapshot
rules, but test latency is the sum of all completed initial and repair
evaluator calls. A failure before the first evaluator uses `0.0`; a repair
generation failure preserves latency from evaluator calls already completed.

Result append is outside the strategy/evaluator failure-mapping block.
`ResultValidationError` and `ResultWriteError` propagate to the caller and the
same `run_id` is never retried automatically. A finalized artifact may remain
for audit, but the run is not considered written or resumable until the one
schema-valid JSONL append succeeds.

For an ordinary `Exception`, the orchestrator must close the strategy session
before building or appending either a success or failure record. An
`ArtifactWriteError` from close propagates unchanged, produces no result
append, and leaves the run incomplete for resume. This rule also applies after
successful finalization: finalized session close completes before append.

`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` use a separate
best-effort cleanup path. A close `Exception` is suppressed only on that path
so the original `BaseException` remains authoritative; no result record is
written.

`MockRunSummary.execution_failures` counts orchestration cleanup failures that
prevented append. These increment `attempted` and `infra_failures`, do not
increment `written`, are distinct from writer failures, and make the CLI exit
nonzero.

Mock execution uses a fresh deterministic provider per `PlannedRun`. Its
planner and patch responses are generated only from the current visible task
and starter file, never from hidden tests, grading, reference patches, or prior
run state.

### Pass@1 And Final Snapshot Preservation

Repeated evaluator calls must not blur Pass@1 and final metrics. M6 must capture
each evaluator result into an immutable `EvaluatorRunSnapshot` immediately after
the call returns.

Rules:

- Pass@1 fields in the final result record can come only from the first evaluator call, where `repair_patches=()` and `max_repair_rounds=0`.
- Later evaluator calls must never overwrite `pass1_public`, `pass1_hidden`, `pass1_public_tests_passed`, or `pass1_hidden_tests_passed`.
- Final fields can come only from the last available evaluator call.
- If strategy/provider/artifact failure occurs before an initial patch exists and before any evaluator call, both Pass@1 and final fields are `false` / `0`.
- If the initial evaluator call succeeds but repair strategy later fails, Pass@1 remains the first evaluator snapshot. Final fields use the latest available evaluator snapshot. If there is no evaluator result newer than Pass@1, final fields equal Pass@1.
- `error_type`, `stop_reason`, `infra_error`, and `valid_run` always reflect the terminal outcome, even when Pass@1/final test-count fields are preserved from earlier evaluator snapshots.
- `merge_evaluator_snapshots(pass1, final_or_latest)` is the only helper allowed to project Pass@1/final evaluator fields into the result record.

## 6. Error Mapping

M6 must map implementation exceptions into current `result.schema.json` values:

| Source error | `error_type` | `stop_reason` | `infra_error` | Notes |
| :--- | :--- | :--- | :--- | :--- |
| No error and final public pass | `none` | `public_pass` | `false` | Valid run |
| No error and repair limit reached | `none` | `repair_limit` | `false` | Valid run |
| `ProviderTimeoutError` | `model_timeout` | `infra_error` | `true` | No retry beyond provider policy |
| `ProviderTransportError` or retryable gateway final failure | `gateway_error` | `infra_error` | `true` | Credential value must not appear |
| `ProviderAuthenticationError` | `gateway_error` | `infra_error` | `true` | Schema has no auth enum |
| `ProviderEmptyResponseError` or evaluator `EmptyResponseError` | `empty_response` | `repair_limit` | `false` unless no result can be produced | Content failure, not hidden-triggered |
| `InvalidPatchError` or M5 `InvalidPatchError` | `invalid_patch` | `repair_limit` | `false` | Valid experimental failure |
| `PatchApplyError` | `patch_apply_error` | `repair_limit` | `false` | Valid experimental failure |
| `TestTimeoutError` | `test_timeout` | `infra_error` | `true` | From public or hidden runner |
| `RunnerError`, `CleanupError`, JSONL integrity unknown | `runner_error` | `infra_error` | `true` | Infrastructure |
| `ProviderFinishReasonError`, parser error, usage projection failure, artifact write error | `unknown` | `infra_error` | `true` | Current schema has no precise enum |

When an error occurs before any evaluator result exists, M6 must still produce a schema-valid failure record with zero test counts, `pass1_public=false`, `pass1_hidden=false`, `final_public=false`, `final_hidden=false`, pending manual review, and safe metric defaults.

Token rules for fallback failure records:

- A successful run must never use `input_tokens=0` or `output_tokens=0` to disguise missing provider usage.
- If the evaluator/strategy flow succeeds but M5 `project_for_result_schema()` fails because usage is missing, the whole run becomes an infrastructure failure: `valid_run=false`, `infra_error=true`, `error_type="unknown"`, `stop_reason="infra_error"`, `input_tokens=0`, `output_tokens=0`, and `estimated_cost=null`.
- In that projection-failure case, `artifact_path` is preserved only if `strategy.finalize()` already succeeded and returned `StrategyFinalization`; otherwise it is `null`.
- Provider/strategy failures before the initial evaluator call also use `input_tokens=0` and `output_tokens=0`.
- These zeros are failure-only schema values required by the existing schema, not successful usage estimates.

## 7. Result JSONL Writer Rules

`ResultJsonlWriter` is single-process, single-writer and mirrors the M4 retrieval writer integrity model:

1. Validate the record against `contracts/result.schema.json` before opening the file.
2. Serialize canonical JSON in memory with `ensure_ascii=False`, `sort_keys=True`, `separators=(",", ":")`.
3. Encode UTF-8 and append exactly one `LF`.
4. Open the same handle in binary append/update mode.
5. Record original size.
6. Seek EOF.
7. Write the complete line.
8. Flush and `os.fsync`.
9. On any write/flush/fsync failure, truncate back to original size through the same handle.
10. Flush and `os.fsync` rollback.
11. If rollback fails, raise `ResultWriteError` with `result_integrity_unknown=True`.
12. Multi-process concurrent writes are unsupported; future CLI must run one writer per process.

`jsonl_path` must resolve under `approved_raw_root`, end in `.jsonl`, and reject absolute escape, `..`, symlink/junction escape, and sibling-prefix escape.

The writer must reject duplicate `run_id` before append by scanning existing valid lines. Malformed existing lines fail closed during resume unless the caller explicitly runs a separate audit mode; ordinary resume cannot skip over corrupted raw data.

## 8. Derived Output Rules

Derived files are optional M6 outputs but, if implemented, must be generated only from `results/raw/{experiment_id}.jsonl`.

CSV columns must include at least:

- `experiment_id`
- `run_id`
- `task_id`
- `strategy`
- `repetition`
- `model`
- `pass1_public`
- `pass1_hidden`
- `final_public`
- `final_hidden`
- `repair_rounds`
- `valid_run`
- `infra_error`
- `error_type`
- `stop_reason`
- `tool_calls`
- `retrieved_tokens`
- `retrieval_success`
- `input_tokens`
- `output_tokens`
- `estimated_cost`
- `model_latency_seconds`
- `artifact_path`

The Markdown summary must be deterministic and must aggregate only raw JSONL fields. It must not read prompts, responses, artifacts, retrieval logs, hidden test files, or workspaces.

`results/derived/` remains retrieval-denied and must never become M4 corpus.

## 9. Live Execution Boundary

M6 may design but must not default to live execution.

Rules:

- Default mode is `mock_run`.
- `live` mode requires both explicit config intent and an environment opt-in such as `ARAG_RUN_LIVE_GATEWAY=1`.
- Importing M6 modules cannot read credentials, construct a live transport, or open network sockets.
- Credential injection can occur only inside a future live transport boundary immediately before send.
- Ordinary pytest must monkeypatch or statically scan network APIs and must never call Hermes, Gateway, Vertex, OpenAI, or any model API.
- API keys, bearer tokens, cookies, and raw authorization headers cannot appear in result JSONL, artifacts, retrieval logs, errors, summaries, or stdout.

`mode` is supplied by CLI/caller and is never inferred from YAML. The config
loader interface is:

```python
load_experiment_config(
    *,
    experiment_path: Path,
    models_path: Path,
    repo_root: Path,
    mode: RunMode = "mock_run",
    env: Mapping[str, str] | None = None,
) -> ExperimentConfig
```

`env` is an explicit mapping for testability. The loader may inspect only
`env.get("ARAG_RUN_LIVE_GATEWAY")` for live gating. It must not read API keys,
tokens, credentials, or authorization environment variables. The rule is:

```python
live_opt_in = mode == "live" and env.get("ARAG_RUN_LIVE_GATEWAY") == "1"
```

If `mode == "live"` and `live_opt_in` is false, config validation fails closed.
For `mock_run` and `dry_run`, the loader does not read credential env vars and
does not construct a live transport.

## 10. Known Blockers And Contract Mismatches

These are not blockers to planning, but they must be handled explicitly during M6 implementation:

1. **Evaluator callback mismatch:** M3 cannot evaluate one patch and return control through a callback. M6 must orchestrate repeated full evaluator calls with accumulated patch lists, or stop and request approval to add a new evaluator adapter.
2. **Result schema narrow error enum:** M5 provider/parser/artifact errors do not have exact schema enum values. M6 must map them to existing enum values and preserve detail only in artifacts or internal audit.
3. **Required integer token fields:** Missing provider usage cannot be exported as a successful result. M6 must either use providers with usage in mock/live runs or classify projection failure as infra error.
4. **Config lacks live opt-in:** Live execution cannot be enabled by current config alone. `mode` must come from CLI/caller and only `ARAG_RUN_LIVE_GATEWAY=1` can satisfy the explicit live gate.
5. **Artifact failure versus result failure priority:** If artifact finalization fails before result append, staged artifacts must be rolled back and the result must record infra failure. If result append then fails, the run is not completed for resume purposes.
6. **Resume must not read model inputs:** Resume may read only raw result JSONL run IDs and schema fields. It must never read previous prompts, responses, artifacts, retrieval logs, or summaries as strategy inputs.
7. **Derived outputs are denied corpus:** `results/derived/` must remain downstream-only and retrieval-denied.
8. **Workspaces path config:** Current M3 `WorkspaceManager` uses temporary directories, not configured `workspace_base_dir`. M6 must not claim persistent workspace scheduling unless a later approved change adds it.

## 11. TDD Implementation Tasks

Every task below must follow RED -> GREEN -> regression. Do not implement production code before the failing test for that task exists and has been run.

### Task 1: Config Loader And Experiment Plan Validation

**Files to create:**

- `experiments/runner/__init__.py`
- `experiments/runner/config.py`
- `experiments/runner/errors.py`
- `tests/runner/conftest.py`
- `tests/runner/test_config.py`

**Files to modify:** none.

**Public interfaces:** `ExperimentPaths`, `ExperimentConfig`, `RunMode`, `ExperimentConfigError`, `load_experiment_config()`.

**Failing tests to write first:**

```python
def test_loads_existing_configs_into_frozen_experiment_config(project_root):
    config = load_experiment_config(
        experiment_path=project_root / "configs/experiment.yaml",
        models_path=project_root / "configs/models.yaml",
        repo_root=project_root,
        mode="mock_run",
        env={},
    )
    assert config.strategies == ("A", "C", "E")
    assert config.repetitions == 3
    assert config.max_repair_rounds == 2
    assert config.seed == 42
    assert config.model == "google/gemini-3.5-flash"
    assert config.model_provider_id == "hermes_vertex_gateway"
    assert config.mode == "mock_run"
    assert config.live_opt_in is False
    assert config.paths.artifact_root == config.paths.raw_results_dir / "artifacts"
    assert config.paths.retrieval_log_root == config.paths.raw_results_dir / "retrieval"
```

```python
def test_config_rejects_unsafe_or_missing_values(tmp_path, project_root):
    bad_experiment = tmp_path / "experiment.yaml"
    bad_models = tmp_path / "models.yaml"
    bad_experiment.write_text(
        "strategies: [A, B]\nrepetitions: 0\nmax_repair_rounds: 3\n"
        "seed: true\ntimeout: {agent_response: 1, unit_test: 1, total_run: 1}\n"
        "paths: {tasks_definition: experiments/tasks.json, raw_results_dir: ../escape, "
        "derived_results_dir: results/derived, reviews_dir: results/reviews, workspace_base_dir: workspaces}\n",
        encoding="utf-8",
    )
    bad_models.write_text("default_provider: missing\ndefault_model: m\nproviders: {}\n", encoding="utf-8")
    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=bad_experiment,
            models_path=bad_models,
            repo_root=project_root,
            mode="mock_run",
            env={},
        )
```

```python
def test_config_rejects_artifact_and_retrieval_log_path_overrides(tmp_path, project_root):
    experiment = tmp_path / "experiment.yaml"
    models = project_root / "configs/models.yaml"
    experiment.write_text(
        "strategies: [A]\nrepetitions: 1\nmax_repair_rounds: 1\nseed: 42\n"
        "timeout: {agent_response: 1, unit_test: 1, total_run: 10}\n"
        "paths: {tasks_definition: experiments/tasks.json, raw_results_dir: results/raw, "
        "derived_results_dir: results/derived, reviews_dir: results/reviews, "
        "workspace_base_dir: workspaces, artifact_root: elsewhere, retrieval_log_root: elsewhere}\n",
        encoding="utf-8",
    )
    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=experiment,
            models_path=models,
            repo_root=project_root,
            mode="mock_run",
            env={},
        )
```

```python
def test_mock_and_dry_run_do_not_read_credential_environment(project_root):
    env = {
        "ARAG_RUN_LIVE_GATEWAY": "1",
        "API_KEY": "SECRET_SHOULD_NOT_BE_READ",
        "TOKEN": "SECRET_SHOULD_NOT_BE_READ",
    }
    for mode in ("mock_run", "dry_run"):
        config = load_experiment_config(
            experiment_path=project_root / "configs/experiment.yaml",
            models_path=project_root / "configs/models.yaml",
            repo_root=project_root,
            mode=mode,
            env=env,
        )
        assert config.live_opt_in is False
```

**RED expectation:** `ModuleNotFoundError: No module named 'experiments.runner'`.

**GREEN expectation:** config object is frozen, resolves all configured and derived paths under repo root, derives artifact/retrieval roots from existing config only, rejects artifact/retrieval overrides, rejects unsafe strategies, bool/zero/negative numeric values, missing provider/model, credential-like keys, and live mode without explicit opt-in.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_config.py tests/providers/test_config.py -v
```

**Completion definition:** Existing YAML can be loaded for offline/mock M6, and unsafe config fails closed without modifying config files.

### Task 2: Run Identity And Scheduler

**Files to create:**

- `experiments/runner/identity.py`
- `experiments/runner/scheduler.py`
- `tests/runner/test_identity_scheduler.py`

**Files to modify:**

- `experiments/runner/__init__.py`

**Public interfaces:** `RunIdentity`, `PlannedRun`, `SchedulerPlan`, `make_experiment_id()`, `make_run_id()`, `build_scheduler_plan()`.

**Failing tests to write first:**

```python
def test_scheduler_builds_deterministic_45_run_plan(project_root, experiment_config):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")
    assert len(plan.runs) == 45
    assert plan.runs[0].identity.run_id.endswith("__T01__A__rep01__seed42")
    assert plan.runs[-1].identity.run_id.endswith("__T05__E__rep03__seed42")
    assert [run.identity.run_id for run in plan.runs] == sorted(run.identity.run_id for run in plan.runs)
```

```python
def test_run_ids_are_windows_safe_and_unique(experiment_config, project_root):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")
    run_ids = [run.identity.run_id for run in plan.runs]
    assert len(run_ids) == len(set(run_ids))
    assert all("/" not in value and "\\" not in value and ":" not in value for value in run_ids)
    assert all(".." not in value.split("__") for value in run_ids)
```

```python
def test_scheduler_derives_exact_output_paths(project_root, experiment_config):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")
    assert plan.raw_jsonl_path == experiment_config.paths.raw_results_dir / f"{plan.experiment_id}.jsonl"
    assert plan.derived_csv_path == experiment_config.paths.derived_results_dir / f"{plan.experiment_id}.csv"
    assert plan.summary_path == experiment_config.paths.derived_results_dir / f"{plan.experiment_id}_summary.md"
```

**RED expectation:** scheduler module missing.

**GREEN expectation:** deterministic ordering is task ID, strategy A/C/E, repetition 1..N; IDs are safe; raw JSONL path resolves under raw results root; derived CSV and summary paths resolve under derived results root.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_identity_scheduler.py tests/contracts -v
```

**Completion definition:** M6 can enumerate the exact intended run set without creating results or workspaces.

### Task 3: Strategy Factory And Offline Provider Wiring

**Files to create:**

- `experiments/runner/strategy_factory.py`
- `tests/runner/test_strategy_factory.py`

**Files to modify:**

- `experiments/runner/__init__.py`

**Public interfaces:** `StrategyBundle`, `StrategyFactory`.

**Failing tests to write first:**

```python
def test_factory_constructs_a_c_e_with_same_provider_parameters(project_root, experiment_config, planned_runs):
    factory = StrategyFactory(repo_root=project_root)
    bundles = [factory.create(run=run, config=experiment_config, repo_root=project_root) for run in planned_runs[:3]]
    assert [bundle.strategy for bundle in bundles] == ["A", "C", "E"]
    assert {bundle.model for bundle in bundles} == {"google/gemini-3.5-flash"}
    assert {bundle.seed for bundle in bundles} == {42}
```

```python
def test_strategy_e_gets_one_store_and_approved_retrieval_log(project_root, experiment_config, e_planned_run):
    bundle = StrategyFactory(repo_root=project_root).create(
        run=e_planned_run,
        config=experiment_config,
        repo_root=project_root,
    )
    assert bundle.strategy == "E"
    assert bundle.retrieval_log_path is not None
    assert bundle.retrieval_log_path.suffix == ".jsonl"
    assert "results" in bundle.retrieval_log_path.parts
```

**RED expectation:** factory module missing.

**GREEN expectation:** A creates `SingleLLMStrategySession`, C creates `MultiAgentStrategySession`, E builds one `FrozenRetrievalStore` from `allowed_corpus`, creates role sessions through M5, and uses `RetrievalLogWriter` under `results/raw/retrieval/{experiment_id}/`.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_strategy_factory.py tests/strategies tests/retrieval -v
```

**Completion definition:** Strategy construction is deterministic, offline by default, uses no live transport, and passes full-task data only through allowed visibility/retrieval spec boundaries.

### Task 4: Append-Only Result JSONL Writer

**Files to create:**

- `experiments/runner/result_writer.py`
- `tests/runner/test_result_writer.py`

**Files to modify:**

- `experiments/runner/__init__.py`

**Public interfaces:** `ResultJsonlWriter`, `ResultWriteError`, `ResultValidationError`.

**Failing tests to write first:**

```python
def test_result_writer_appends_canonical_schema_valid_jsonl(tmp_path, valid_result_record, result_schema_path):
    raw_root = tmp_path / "results" / "raw"
    writer = ResultJsonlWriter(
        approved_raw_root=raw_root,
        jsonl_path=raw_root / "exp.jsonl",
        schema_path=result_schema_path,
    )
    writer.append(valid_result_record)
    line = (raw_root / "exp.jsonl").read_bytes()
    assert line.endswith(b"\n")
    assert json.loads(line) == valid_result_record
```

```python
def test_partial_result_write_rolls_back_to_original_bytes(tmp_path, valid_result_record, result_schema_path, monkeypatch):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    raw_root.mkdir(parents=True)
    original = b'{"run_id":"existing"}\n'
    path.write_bytes(original)
    writer = ResultJsonlWriter(approved_raw_root=raw_root, jsonl_path=path, schema_path=result_schema_path)
    monkeypatch.setattr(writer, "_write_line_once", lambda handle, line: (handle.write(line[:7]), (_ for _ in ()).throw(OSError("boom"))))
    with pytest.raises(ResultWriteError):
        writer.append(valid_result_record)
    assert path.read_bytes() == original
```

**RED expectation:** writer module missing.

**GREEN expectation:** validates before opening, rejects path escapes/sibling-prefix/symlink escapes, writes one line, fsyncs, rolls back half-lines, reports `result_integrity_unknown=True` if rollback fails, and rejects duplicate run IDs.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_result_writer.py tests/contracts/test_result_schema.py -v
```

**Completion definition:** raw results can be appended safely without partial lines or duplicate run IDs.

### Task 5: Resume And Duplicate Detection

**Files to create:**

- `experiments/runner/resume.py`
- `tests/runner/test_resume.py`

**Files to modify:**

- `experiments/runner/result_writer.py`

**Public interfaces:** `CompletedRunIndex`, `load_completed_run_index()`, `filter_pending_runs()`.

**Failing tests to write first:**

```python
def test_resume_skips_only_schema_valid_completed_run_ids(tmp_path, valid_result_record, scheduler_plan, result_schema_path):
    raw_path = tmp_path / "results/raw/exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(json.dumps(valid_result_record, sort_keys=True) + "\n", encoding="utf-8")
    index = load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)
    pending = filter_pending_runs(scheduler_plan.runs, index)
    assert valid_result_record["run_id"] not in {run.identity.run_id for run in pending}
```

```python
def test_resume_fails_closed_on_malformed_existing_line(tmp_path, result_schema_path):
    raw_path = tmp_path / "results/raw/exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text('{"run_id":"ok"}\n{bad json\n', encoding="utf-8")
    with pytest.raises(ResultValidationError):
        load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)
```

**RED expectation:** resume module missing.

**GREEN expectation:** resume reads only raw JSONL records, validates every line, skips only exact completed run IDs, rejects duplicate run IDs, and never opens artifact/prompt/response/retrieval-log files.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_resume.py tests/runner/test_result_writer.py -v
```

**Completion definition:** interrupted experiments can resume without feeding prior outputs back into strategies.

### Task 6: Strategy-Evaluator Orchestration Loop

**Files to create:**

- `experiments/runner/orchestrator.py`
- `experiments/runner/projection.py`
- `tests/runner/test_orchestrator.py`
- `tests/runner/test_projection.py`

**Files to modify:**

- `experiments/runner/errors.py`

**Public interfaces:** `ExperimentOrchestrator`, `RunExecutionResult`, `RunnerFailure`, `EvaluatorRunSnapshot`, `MergedEvaluationSnapshots`, `merge_evaluator_snapshots()`, `merge_evaluator_and_strategy_result()`.

**Failing tests to write first:**

```python
def test_orchestrator_stops_after_public_pass_without_repair(fake_public_pass_run):
    result = fake_public_pass_run.execute()
    assert result.result_record["stop_reason"] == "public_pass"
    assert result.result_record["repair_rounds"] == 0
    assert fake_public_pass_run.strategy.generate_repair_calls == 0
    assert fake_public_pass_run.strategy.finalize_calls == 1
```

```python
def test_orchestrator_repairs_only_from_public_feedback(fake_public_fail_then_pass_run):
    result = fake_public_fail_then_pass_run.execute()
    assert result.result_record["repair_rounds"] == 1
    assert fake_public_fail_then_pass_run.strategy.feedback_texts == ["PUBLIC ONLY"]
    assert "hidden" not in repr(fake_public_fail_then_pass_run.strategy.feedback_texts).lower()
```

```python
def test_repair_final_pass_preserves_failed_pass1_snapshot(fake_public_fail_then_pass_run):
    result = fake_public_fail_then_pass_run.execute()
    assert result.result_record["pass1_public"] is False
    assert result.result_record["pass1_public_tests_passed"] == 0
    assert result.result_record["final_public"] is True
    assert result.result_record["public_tests_passed"] == result.result_record["public_tests_total"]
```

```python
def test_repair_does_not_overwrite_pass1_hidden_counts(fake_hidden_counts_change_after_repair_run):
    result = fake_hidden_counts_change_after_repair_run.execute()
    assert result.result_record["pass1_hidden_tests_passed"] == 1
    assert result.result_record["hidden_tests_passed"] == 3
    assert result.result_record["pass1_hidden_tests_passed"] != result.result_record["hidden_tests_passed"]
```

```python
def test_repair_strategy_failure_preserves_pass1_and_latest_final(fake_repair_strategy_failure_run):
    result = fake_repair_strategy_failure_run.execute()
    assert result.result_record["pass1_public"] is False
    assert result.result_record["final_public"] is False
    assert result.result_record["error_type"] == "unknown"
    assert result.result_record["stop_reason"] == "infra_error"
    assert result.result_record["infra_error"] is True
```

**RED expectation:** orchestrator module missing.

**GREEN expectation:** orchestrator calls `generate_initial_patch`, evaluates pass 1, preserves Pass@1 fields from the first evaluator snapshot, calls repair only when public fails, never uses hidden results for repair decisions, finalizes after entire flow, closes/rolls back on terminal strategy failure, and passes only patch strings to evaluator.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_orchestrator.py tests/runner/test_projection.py tests/runtime/test_evaluator_integration.py tests/strategies/test_repair_boundary.py -v
```

**Completion definition:** One run can be executed through M3+M5 with correct public feedback isolation and artifact lifecycle.

### Task 7: Failure Classification And Result Projection

**Files to create:**

- `tests/runner/test_failure_classification.py`

**Files to modify:**

- `experiments/runner/errors.py`
- `experiments/runner/projection.py`
- `experiments/runner/orchestrator.py`

**Public interfaces:** `classify_runner_exception()`, `make_failure_result_record()`.

**Failing tests to write first:**

```python
@pytest.mark.parametrize(
    ("exc", "error_type", "stop_reason", "infra_error"),
    [
        (ProviderTimeoutError("timeout", attempt_records=(), elapsed_seconds=1.0), "model_timeout", "infra_error", True),
        (ProviderFinishReasonError("bad finish", attempt_records=(), elapsed_seconds=1.0), "unknown", "infra_error", True),
        (InvalidPatchError("bad patch"), "invalid_patch", "repair_limit", False),
        (PatchApplyError("cannot apply"), "patch_apply_error", "repair_limit", False),
    ],
)
def test_exception_mapping_uses_only_result_schema_enums(exc, error_type, stop_reason, infra_error):
    failure = classify_runner_exception(exc)
    assert failure.error_type == error_type
    assert failure.stop_reason == stop_reason
    assert failure.infra_error is infra_error
```

```python
def test_missing_usage_projection_becomes_infra_failure_not_fake_tokens(planned_run, evaluator_result_without_usage):
    record = make_failure_result_record(
        run=planned_run,
        failure=RunnerFailure("unknown", "infra_error", True, False, "usage unavailable"),
        evaluator_result=evaluator_result_without_usage,
    )
    assert record["valid_run"] is False
    assert record["input_tokens"] == 0
    assert record["output_tokens"] == 0
    assert record["error_type"] == "unknown"
    assert record["stop_reason"] == "infra_error"
    assert record["estimated_cost"] is None
```

```python
def test_successful_missing_usage_cannot_export_valid_run_true(planned_run, successful_evaluator_result, finalized_without_usage):
    record = make_failure_result_record(
        run=planned_run,
        failure=RunnerFailure("unknown", "infra_error", True, False, "usage unavailable"),
        evaluator_result=successful_evaluator_result,
        finalization=finalized_without_usage,
    )
    assert successful_evaluator_result["final_public"] is True
    assert record["valid_run"] is False
    assert record["infra_error"] is True
    assert record["input_tokens"] == 0
    assert record["output_tokens"] == 0
    assert record["artifact_path"] == finalized_without_usage.artifact_path
```

**RED expectation:** failure classifier missing or maps errors inconsistently.

**GREEN expectation:** all provider/parser/artifact/evaluator errors map into current result schema enums; successful records use real projected token counts only; failure fallback records use `0` token values only when `valid_run=false` and do not contain raw prompt/response text.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_failure_classification.py tests/contracts/test_result_schema.py -v
```

**Completion definition:** Every planned terminal path has a deterministic, schema-valid result projection policy.

### Task 8: Derived CSV And Markdown Summary

**Files to create:**

- `experiments/runner/derived.py`
- `tests/runner/test_derived_outputs.py`

**Files to modify:**

- `experiments/runner/__init__.py`

**Public interfaces:** `write_derived_csv()`, `write_summary_markdown()`.

**Failing tests to write first:**

```python
def test_derived_csv_contains_required_columns_from_raw_jsonl_only(tmp_path, raw_jsonl_with_two_records):
    csv_path = tmp_path / "results/derived/exp.csv"
    write_derived_csv(raw_jsonl_path=raw_jsonl_with_two_records, csv_path=csv_path)
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert "experiment_id" in header
    assert "run_id" in header
    assert "artifact_path" in header
```

```python
def test_summary_does_not_read_artifacts_or_retrieval_logs(tmp_path, raw_jsonl_with_two_records, monkeypatch):
    opened = []
    original_open = Path.open
    def tracking_open(self, *args, **kwargs):
        opened.append(self.as_posix())
        return original_open(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", tracking_open)
    summary_path = tmp_path / "results/derived/exp_summary.md"
    write_summary_markdown(raw_jsonl_path=raw_jsonl_with_two_records, summary_path=summary_path)
    assert all("artifacts" not in path and "retrieval" not in path for path in opened)
```

**RED expectation:** derived module missing.

**GREEN expectation:** derived files are deterministic, sorted by run ID, use only raw JSONL, write under approved derived root, and reject malformed raw records.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_derived_outputs.py tests/runner/test_resume.py -v
```

**Completion definition:** CSV and summary are reproducible downstream views of raw JSONL only.

### Task 9: CLI Dry-Run And Mock-Run Commands

**Files to create:**

- `experiments/cli.py`
- `tests/runner/test_cli.py`

**Files to modify:** none.

**Public interfaces:** `main(argv: list[str] | None = None) -> int`.

**Failing tests to write first:**

```python
def test_cli_dry_run_prints_plan_without_creating_results(project_root, capsys):
    exit_code = main(["dry-run", "--repo-root", str(project_root)])
    assert exit_code == 0
    assert "45 planned runs" in capsys.readouterr().out
    assert not (project_root / "results/raw").exists()
```

```python
def test_cli_mock_run_requires_no_network_or_credentials(project_root, monkeypatch):
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    exit_code = main(["mock-run", "--repo-root", str(project_root), "--limit", "1"])
    assert exit_code == 0
```

**RED expectation:** `experiments.cli` missing.

**GREEN expectation:** dry-run creates no result files; mock-run uses fake/offline provider; live command fails closed unless explicitly opted in; CLI arguments cannot escape approved result roots.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/runner/test_cli.py tests/live/test_gateway_smoke.py -v
```

**Completion definition:** Users can inspect planned runs and execute deterministic mock runs without network.

### Task 10: Leakage, Residue, And Full Regression

**Files to create:**

- `tests/leakage/test_runner_leakage.py`

**Files to modify:** M6 runner modules only if tests expose a bug.

**Public interfaces:** none new.

**Failing tests to write first:**

```python
def test_runner_never_passes_hidden_or_grading_fields_to_strategy(monkeypatch, full_task_with_secret_sentinel):
    captured = []
    def fake_create_visible_task(self, task_record):
        visible = ModelVisibleTaskFactory(repo_root=self.repo_root).from_task_record(task_record)
        captured.append(repr(visible))
        return visible
    monkeypatch.setattr(StrategyFactory, "_create_visible_task", fake_create_visible_task)
    run_one_mock_task(full_task_with_secret_sentinel)
    assert "required_evidence" not in "".join(captured)
    assert "grading" not in "".join(captured)
    assert "hidden" not in "".join(captured).lower()
```

```python
def test_results_and_derived_outputs_remain_retrieval_denied():
    assert is_denylisted_repo_path("results/raw/exp.jsonl")
    assert is_denylisted_repo_path("results/derived/exp.csv")
```

**RED expectation:** leakage test fails until M6 runner boundaries exist.

**GREEN expectation:** no hidden/private fields enter strategy/provider prompts/results/artifacts; previous raw results, derived outputs, retrieval logs, and artifact files are never read as strategy input; no cache/JSONL/synthetic workspace residue remains after tests.

**Regression command:**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/runner -v
python -B -m pytest tests/leakage -v
python -B -m pytest tests/retrieval -v
python -B -m pytest tests/strategies -v
python -B -m pytest tests/contracts tests/m2 tests/runtime -v
python -B -m pytest -q
```

**Completion definition:** M6 does not regress M1-M5 and leaves no unapproved residue.

### Task 11: Optional Live Smoke Gated Boundary

**Files to create:**

- `tests/live/test_m6_live_boundary.py`

**Files to modify:**

- `experiments/runner/config.py`
- `experiments/runner/strategy_factory.py`
- `experiments/cli.py`

**Public interfaces:** no new public API beyond `mode="live"` validation.

**Failing tests to write first:**

```python
def test_live_mode_skips_without_env_opt_in(project_root, monkeypatch):
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=project_root / "configs/experiment.yaml",
            models_path=project_root / "configs/models.yaml",
            repo_root=project_root,
            mode="live",
            env={},
        )
```

```python
def test_importing_live_boundary_reads_no_credentials(monkeypatch):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("API_KEY", "SECRET_SHOULD_NOT_BE_READ_ON_IMPORT")
    import experiments.cli
    assert "SECRET_SHOULD_NOT_BE_READ_ON_IMPORT" not in repr(experiments.cli)
```

```python
def test_live_mode_uses_only_explicit_gate_from_injected_env(project_root):
    config = load_experiment_config(
        experiment_path=project_root / "configs/experiment.yaml",
        models_path=project_root / "configs/models.yaml",
        repo_root=project_root,
        mode="live",
        env={"ARAG_RUN_LIVE_GATEWAY": "1", "API_KEY": "SECRET_SHOULD_NOT_BE_READ"},
    )
    assert config.live_opt_in is True
```

**RED expectation:** live boundary behavior not yet explicit in M6 modules.

**GREEN expectation:** ordinary pytest never constructs live transport or reads credentials; live behavior remains opt-in and may still skip actual network until a future authorized live execution round.

**Regression command:**

```powershell
Remove-Item Env:ARAG_RUN_LIVE_GATEWAY -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/live -v
```

**Completion definition:** Live boundary is safe, explicit, and not required for M6 offline acceptance.

## 12. Final Verification Commands

After all M6 implementation tasks are complete, run at least two consecutive full rounds:

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
rg -n "requests|httpx|urllib|socket|vertex|gemini|Hermes" experiments/runner experiments/cli.py tests/runner
rg -n "results/derived|results/raw|workspaces" experiments/retrieval tests/retrieval
```

Residue scan:

```powershell
Get-ChildItem -Recurse -Force | Where-Object {
    $_.Name -eq '__pycache__' -or
    $_.Name -eq '.pytest_cache' -or
    $_.Name -like 'temp_sandbox_*' -or
    $_.Name -like '.patch_tmp_*' -or
    $_.Name -like '.patch_bak_*' -or
    $_.Extension -in '.pyc','.pyo','.jsonl'
}
```

Clean only confirmed test residue under approved temporary paths. Do not recursively delete uncertain paths.

## 13. Acceptance Update Rule

`docs/milestones/M6_acceptance.md` starts with all items Planned. During implementation, mark an item Completed only after its verification command or static scan has actually passed in the current workspace. Do not claim live model success unless a separately authorized live run is performed.

## 14. Planning-Round Confirmation

- This document is a plan only.
- No M6 code, tests, CLI, result JSONL, derived output, workspace, or live transport was created in this planning round.
- No schema, config, task, student-system, evaluator, runtime, retrieval, provider, strategy, hidden-test, or reference-patch file was modified in this planning round.
- No model, Hermes, Gateway, Vertex, OpenAI, or network call was made.
