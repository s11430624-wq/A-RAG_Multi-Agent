from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Callable

from experiments.evaluation.evaluator import Evaluator
from experiments.live.budget import BudgetLimits, LiveBudgetTracker
from experiments.live.smoke_gate import (
    LeakageAuditor,
    LeakageEvidence,
    ResumeAuditor,
    ResumeEvidence,
    SmokeGateAuditor,
    SmokeGateReport,
)
from experiments.live.smoke_scheduler import build_smoke_scheduler_plan
from experiments.providers.models import (
    ModelProvider,
    ProviderEmptyResponseError,
    ProviderError,
    ProviderFinishReasonError,
    ProviderMalformedResponseError,
)
from experiments.runner.config import ExperimentPaths, load_experiment_config
from experiments.runner.identity import make_run_id
from experiments.runner.orchestrator import ExperimentOrchestrator
from experiments.runner.result_writer import ResultJsonlWriter
from experiments.runner.scheduler import PlannedRun
from experiments.runner.strategy_factory import StrategyFactory


_EXPERIMENT_ID = re.compile(r"^m7d_smoke_[0-9]{8}T[0-9]{6}Z$")
_FULL_RUN_EXPERIMENT_ID = re.compile(r"^m7e_full_[0-9]{8}T[0-9]{6}Z$")


@dataclass(frozen=True)
class ProviderAttemptHooks:
    reserve_provider_attempt: Callable[[], None]
    limiter: object | None = None


@dataclass(frozen=True)
class SmokeExecutionRequest:
    experiment_id: str
    repo_root: Path
    raw_jsonl_path: Path
    artifact_root: Path
    retrieval_log_root: Path
    smoke_report_path: Path
    budget_limits: BudgetLimits
    provider_factory: Callable[[PlannedRun, ProviderAttemptHooks], ModelProvider]


@dataclass(frozen=True)
class SmokeExecutionResult:
    completed_run_ids: tuple[str, ...]
    model_call_count: int
    provider_attempt_count: int
    total_input_tokens: int
    total_output_tokens: int
    quarantined: bool
    abort_reason: str | None
    report: SmokeGateReport | None
    leakage_evidence: LeakageEvidence | None
    resume_evidence: ResumeEvidence | None


class SmokeExecutionAbort(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveExecutionRequest:
    experiment_id: str
    repo_root: Path
    planned_runs: tuple[PlannedRun, ...]
    raw_jsonl_path: Path
    artifact_root: Path
    retrieval_log_root: Path
    budget_limits: BudgetLimits
    provider_factory: Callable[[PlannedRun, ProviderAttemptHooks], ModelProvider]
    mode: str  # "smoke" or "full"
    smoke_report_path: Path | None = None
    smoke_report_sha256: str | None = None


@dataclass(frozen=True)
class LiveExecutionResult:
    completed_run_ids: tuple[str, ...]
    attempted_run_count: int
    written_record_count: int
    model_call_count: int
    provider_attempt_count: int
    total_input_tokens: int
    total_output_tokens: int
    quarantined: bool
    abort_reason: str | None
    raw_jsonl_path: Path
    artifact_root: Path
    retrieval_log_root: Path
    report: SmokeGateReport | None = None
    leakage_evidence: LeakageEvidence | None = None
    resume_evidence: ResumeEvidence | None = None


class LiveExecutionAbort(RuntimeError):
    pass


class LiveExperimentExecutor:
    def __init__(
        self,
        *,
        limiter: object | None = None,
        clock: Callable[[], float] | None = None,
        epoch_clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._limiter = limiter
        self._clock = clock
        self._epoch_clock = epoch_clock
        self._sleeper = sleeper if sleeper is not None else time.sleep

    def execute(self, request: LiveExecutionRequest) -> LiveExecutionResult:
        rebound_runs = _bind_plan_to_request(request.planned_runs, request.experiment_id)
        request = replace(request, planned_runs=rebound_runs)
        repo_root = validate_live_execution_request(request)
        
        if request.mode == "smoke":
            config = _load_smoke_config(request, repo_root)
        elif request.mode in ("full", "pilot15"):
            config = _load_full_config(request, repo_root)
        else:
            raise ValueError(f"invalid mode: {request.mode}")

        from experiments.live.rate_limit import LiveRateLimitPolicy, LiveRateLimiter
        policy = LiveRateLimitPolicy(
            minimum_attempt_interval_seconds=1.0,
            inter_run_cooldown_seconds=10.0,
            retry_after_min_seconds=1.0,
            retry_after_max_seconds=120.0,
            fallback_429_delays=(30.0, 60.0),
        )
        clock = self._clock or time.monotonic
        epoch_clock = self._epoch_clock or time.time
        sleeper = self._sleeper
        
        tracker = LiveBudgetTracker(request.budget_limits, clock=clock)
        if self._limiter is not None:
            limiter = self._limiter
        else:
            limiter = LiveRateLimiter(policy, clock=clock, epoch_clock=epoch_clock, sleeper=sleeper)
        hooks = ProviderAttemptHooks(tracker.reserve_provider_attempt, limiter=limiter)

        def provider_builder(run, _task, _provider_config):
            provider = request.provider_factory(run, hooks)
            return _BudgetedProvider(provider, tracker)

        strategy_factory = StrategyFactory(
            repo_root=repo_root,
            provider_builder=provider_builder,
            artifact_root=request.artifact_root,
            retrieval_log_root=request.retrieval_log_root,
        )
        result_writer = ResultJsonlWriter(
            approved_raw_root=request.raw_jsonl_path.parent,
            jsonl_path=request.raw_jsonl_path,
            schema_path=repo_root / "contracts" / "result.schema.json",
        )
        guarded_writer = _CompletedOnlyWriter(result_writer)
        evaluator = Evaluator(repo_root / "experiments" / "tasks.json")
        orchestrator = ExperimentOrchestrator(
            config=config,
            repo_root=repo_root,
            evaluator=evaluator,
            strategy_factory=strategy_factory,
            writer=guarded_writer,
        )

        completed_run_ids: list[str] = []
        
        # Resume verification & filtering
        if request.raw_jsonl_path.exists():
            from experiments.runner.resume import load_completed_run_index, filter_pending_runs
            try:
                completed_index = load_completed_run_index(
                    raw_path=request.raw_jsonl_path,
                    schema_path=repo_root / "contracts" / "result.schema.json"
                )
                completed_run_ids = list(completed_index.run_ids)
                pending_runs = filter_pending_runs(request.planned_runs, completed_index)
            except Exception as exc:
                raise ValueError(f"Resume validation failed: {exc}")
        else:
            pending_runs = request.planned_runs

        # Snapshot consistency checks on resume
        if request.mode == "full" and completed_run_ids:
            import json
            with open(request.raw_jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line)
                        if rec.get("model") != config.model:
                            raise ValueError("consistency mismatch: model in existing JSONL does not match config")
                        run_id = rec.get("run_id", "")
                        if not run_id.startswith(request.experiment_id):
                            raise ValueError("consistency mismatch: experiment_id in existing JSONL does not match request")

        completed_this_session = []
        for i, run in enumerate(pending_runs):
            try:
                execution = orchestrator.execute_run(run)
                if execution.result_record["infra_error"]:
                    raise LiveExecutionAbort(
                        f"run {run.identity.run_id} ended with infrastructure failure"
                    )
                completed_this_session.append(run.identity.run_id)
                if i < len(pending_runs) - 1:
                    limiter.wait_after_completed_run(
                        cancellation=getattr(run, "cancellation", None),
                        check_budget_fn=tracker._check_wall_clock,
                    )
            except Exception as exc:
                import traceback
                print("--- RUNTIME EXCEPTION IN LIVE-RUN EXECUTION ---")
                traceback.print_exc()
                print("-----------------------------------------------")
                from experiments.live.diagnostics import write_provider_failure_diagnostic
                try:
                    write_provider_failure_diagnostic(
                        approved_root=repo_root,
                        experiment_id=request.experiment_id,
                        run=run,
                        config=config,
                        exc=exc,
                        elapsed_seconds=tracker.clock() - tracker.start_time,
                    )
                except FileExistsError as diag_err:
                    print(f"Warning: could not write failure diagnostic because it already exists: {diag_err}")
                return LiveExecutionResult(
                    completed_run_ids=tuple(completed_run_ids + completed_this_session),
                    attempted_run_count=len(pending_runs),
                    written_record_count=len(completed_run_ids + completed_this_session),
                    model_call_count=tracker.model_call_count,
                    provider_attempt_count=tracker.provider_attempt_count,
                    total_input_tokens=tracker.consumed_input_tokens,
                    total_output_tokens=tracker.consumed_output_tokens,
                    quarantined=True,
                    abort_reason=str(exc),
                    raw_jsonl_path=request.raw_jsonl_path,
                    artifact_root=request.artifact_root,
                    retrieval_log_root=request.retrieval_log_root,
                )

        all_completed_ids = completed_run_ids + completed_this_session

        leakage_evidence = LeakageAuditor(
            repo_root,
            artifact_root=request.artifact_root,
            retrieval_log_root=request.retrieval_log_root,
        ).audit_leakage(request.experiment_id, request.raw_jsonl_path)
        
        resume_evidence = ResumeAuditor(
            repo_root,
            artifact_root=request.artifact_root,
        ).audit_resume(request.experiment_id, request.raw_jsonl_path)

        report = None
        if request.mode == "smoke":
            report = SmokeGateAuditor(
                request.raw_jsonl_path,
                repo_root,
                artifact_root=request.artifact_root,
                retrieval_log_root=request.retrieval_log_root,
                leakage_evidence=leakage_evidence,
                resume_evidence=resume_evidence,
            ).audit_smoke_runs()
            
            if request.smoke_report_path:
                request.smoke_report_path.parent.mkdir(parents=True, exist_ok=True)
                report.write_to_file(request.smoke_report_path)

        return LiveExecutionResult(
            completed_run_ids=tuple(all_completed_ids),
            attempted_run_count=len(pending_runs),
            written_record_count=len(all_completed_ids),
            model_call_count=tracker.model_call_count,
            provider_attempt_count=tracker.provider_attempt_count,
            total_input_tokens=tracker.consumed_input_tokens,
            total_output_tokens=tracker.consumed_output_tokens,
            quarantined=False,
            abort_reason=None,
            report=report,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
            raw_jsonl_path=request.raw_jsonl_path,
            artifact_root=request.artifact_root,
            retrieval_log_root=request.retrieval_log_root,
        )


class SmokeExecutor:
    def __init__(self, *, sleeper: Callable[[float], None] | None = None) -> None:
        self._sleeper = sleeper

    def execute(self, request: SmokeExecutionRequest) -> SmokeExecutionResult:
        repo_root = _validate_request(request)
        config = _load_smoke_config_from_smoke_request(request, repo_root)
        plan = build_smoke_scheduler_plan(
            config,
            repo_root=repo_root,
            today=request.experiment_id[len("m7d_smoke_") : len("m7d_smoke_") + 8],
        )
        runs = _bind_plan_to_request(plan.runs, request.experiment_id)
        
        live_req = LiveExecutionRequest(
            experiment_id=request.experiment_id,
            repo_root=request.repo_root,
            planned_runs=runs,
            raw_jsonl_path=request.raw_jsonl_path,
            artifact_root=request.artifact_root,
            retrieval_log_root=request.retrieval_log_root,
            budget_limits=request.budget_limits,
            provider_factory=request.provider_factory,
            mode="smoke",
            smoke_report_path=request.smoke_report_path,
        )
        
        live_executor = LiveExperimentExecutor(sleeper=self._sleeper)
        res = live_executor.execute(live_req)
        
        return SmokeExecutionResult(
            completed_run_ids=res.completed_run_ids,
            model_call_count=res.model_call_count,
            provider_attempt_count=res.provider_attempt_count,
            total_input_tokens=res.total_input_tokens,
            total_output_tokens=res.total_output_tokens,
            quarantined=res.quarantined,
            abort_reason=res.abort_reason,
            report=res.report,
            leakage_evidence=res.leakage_evidence,
            resume_evidence=res.resume_evidence,
        )


def validate_smoke_execution_request(request: SmokeExecutionRequest) -> Path:
    return _validate_request(request)


class _BudgetedProvider:
    def __init__(self, provider: ModelProvider, tracker: LiveBudgetTracker) -> None:
        self.provider = provider
        self.tracker = tracker

    def generate(self, request):
        self.tracker.record_model_call_start()
        before_attempts = self.tracker.provider_attempt_count
        try:
            response = self.provider.generate(request)
        except ProviderError as exc:
            try:
                _assert_attempt_accounting(
                    before_attempts,
                    self.tracker.provider_attempt_count,
                    len(exc.attempt_records),
                )
            except Exception:
                pass
            is_infra = not isinstance(
                exc,
                (
                    ProviderEmptyResponseError,
                    ProviderMalformedResponseError,
                    ProviderFinishReasonError,
                ),
            )
            self.tracker.record_failure(is_infra=is_infra, is_gateway=is_infra)
            raise
        _assert_attempt_accounting(
            before_attempts,
            self.tracker.provider_attempt_count,
            len(response.attempt_records),
        )
        usage = response.usage
        if usage.input_tokens is None or usage.output_tokens is None:
            raise LiveExecutionAbort("provider usage is incomplete")
        self.tracker.record_tokens(usage.input_tokens, usage.output_tokens)
        return response


class _CompletedOnlyWriter:
    def __init__(self, writer: ResultJsonlWriter) -> None:
        self.writer = writer
        self._active_exception = None

    def set_active_exception(self, exc: Exception) -> None:
        self._active_exception = exc

    def append(self, record) -> None:
        if (
            record.get("infra_error")
            or not record.get("valid_run")
            or record.get("error_type") != "none"
        ):
            exc_val = self._active_exception
            self._active_exception = None
            if exc_val is not None:
                err_msg = f"{type(exc_val).__name__}: {exc_val}"
                raise LiveExecutionAbort(err_msg) from exc_val
            else:
                err_msg = f"incomplete run rejected: {record.get('error_type', 'unknown')}"
                raise LiveExecutionAbort(err_msg)
        self.writer.append(dict(record))


def _validate_request(request: SmokeExecutionRequest) -> Path:
    repo_root = Path(request.repo_root).resolve()
    if _EXPERIMENT_ID.fullmatch(request.experiment_id) is None:
        raise ValueError("invalid smoke experiment_id")
    raw_root = (repo_root / "results" / "raw").resolve()
    contracts = {
        Path(request.raw_jsonl_path).resolve(): raw_root
        / f"{request.experiment_id}.jsonl",
        Path(request.artifact_root).resolve(): raw_root
        / "artifacts"
        / request.experiment_id,
        Path(request.retrieval_log_root).resolve(): raw_root
        / "retrieval"
        / request.experiment_id,
        Path(request.smoke_report_path).resolve(): raw_root
        / "gates"
        / f"{request.experiment_id}.json",
    }
    for actual, expected in contracts.items():
        actual.relative_to(repo_root)
        if actual != expected.resolve():
            raise ValueError(f"smoke output path mismatch: {actual}")
        if actual.exists():
            raise FileExistsError(f"smoke output already exists: {actual}")
    return repo_root


def validate_live_execution_request(request: LiveExecutionRequest) -> Path:
    repo_root = Path(request.repo_root).resolve()
    raw_root = (repo_root / "results" / "raw").resolve()
    
    if request.mode == "smoke":
        if _EXPERIMENT_ID.fullmatch(request.experiment_id) is None:
            raise ValueError("invalid smoke experiment_id")
        if not request.smoke_report_path:
            raise ValueError("smoke mode requires smoke_report_path")
        
        contracts = {
            Path(request.raw_jsonl_path).resolve(): raw_root / f"{request.experiment_id}.jsonl",
            Path(request.artifact_root).resolve(): raw_root / "artifacts" / request.experiment_id,
            Path(request.retrieval_log_root).resolve(): raw_root / "retrieval" / request.experiment_id,
            Path(request.smoke_report_path).resolve(): raw_root / "gates" / f"{request.experiment_id}.json",
        }
    elif request.mode in ("full", "pilot15"):
        if _FULL_RUN_EXPERIMENT_ID.fullmatch(request.experiment_id) is None:
            raise ValueError("invalid full experiment_id")
        
        # Preflight: reject if any planned output path exists (unless we are resuming!)
        # Wait, if we are resuming, the raw_jsonl_path DOES exist. So in request validation,
        # we can bypass FileExistsError only if raw_jsonl_path exists but contains completed records.
        # But wait! "Must reject if any planned output path exists" is the approval/preflight prerequisite.
        # So we check if the raw_jsonl_path exists. If it exists, but the file is not empty or we are not explicitly resuming, we raise FileExistsError.
        # Wait, how does it know we are resuming? If we are in full-run mode and raw_jsonl_path exists:
        # If it exists, we load it. If it's valid, we proceed with resume. If it's empty or invalid or we don't want to resume, we reject.
        # Actually, let's just make it: if actual.exists() and actual != Path(request.raw_jsonl_path).resolve():
        # raise FileExistsError.
        # And if actual == Path(request.raw_jsonl_path).resolve(), we only allow it to exist if it contains valid records (for resume).
        
        for p in (request.raw_jsonl_path, request.artifact_root, request.retrieval_log_root):
            if "smoke" in str(p).lower():
                raise ValueError("full mode cannot write to smoke paths")
                
        contracts = {
            Path(request.raw_jsonl_path).resolve(): raw_root / f"{request.experiment_id}.jsonl",
            Path(request.artifact_root).resolve(): raw_root / "artifacts" / request.experiment_id,
            Path(request.retrieval_log_root).resolve(): raw_root / "retrieval" / request.experiment_id,
        }
    else:
        raise ValueError(f"invalid mode: {request.mode}")

    is_resume = False
    if request.mode == "full" and Path(request.raw_jsonl_path).resolve().exists():
        is_resume = True

    for actual, expected in contracts.items():
        actual.relative_to(repo_root)
        if actual != expected.resolve():
            raise ValueError(f"output path mismatch: {actual}")
        if actual.exists():
            # For full mode, if it is a resume run, we allow existence of all paths!
            if request.mode == "full" and is_resume:
                continue
            raise FileExistsError(f"output already exists: {actual}")
            
    # Validation of planned_runs
    if request.mode == "smoke":
        if len(request.planned_runs) != 3:
            raise ValueError("smoke mode requires exactly 3 planned runs")
        for r in request.planned_runs:
            if r.identity.task_id != "T01":
                raise ValueError("smoke mode only allows T01")
            if r.identity.strategy not in ("A", "C", "E"):
                raise ValueError("smoke mode only allows strategies A, C, E")
    elif request.mode == "full":
        if len(request.planned_runs) != 45:
            raise ValueError("full mode requires exactly 45 planned runs")
        
        # Verify strategies: 15 for A, 15 for C, 15 for E
        count_A = sum(1 for r in request.planned_runs if r.identity.strategy == "A")
        count_C = sum(1 for r in request.planned_runs if r.identity.strategy == "C")
        count_E = sum(1 for r in request.planned_runs if r.identity.strategy == "E")
        if count_A != 15 or count_C != 15 or count_E != 15:
            raise ValueError(f"full mode requires exactly 15 runs per strategy, got A={count_A}, C={count_C}, E={count_E}")
            
        # Verify tasks: 9 for each of T01-T05
        tasks = [f"T0{i}" for i in range(1, 6)]
        for t in tasks:
            count_t = sum(1 for r in request.planned_runs if r.identity.task_id == t)
            if count_t != 9:
                raise ValueError(f"full mode requires exactly 9 runs per task, got {t}={count_t}")
    elif request.mode == "pilot15":
        expected = tuple(
            ("T01", strategy, repetition)
            for strategy in ("A", "C", "E")
            for repetition in (1, 2, 3)
        ) + tuple(
            ("T02", strategy, repetition)
            for strategy in ("A", "C")
            for repetition in (1, 2, 3)
        )
        actual = tuple(
            (
                run.identity.task_id,
                run.identity.strategy,
                run.identity.repetition,
            )
            for run in request.planned_runs
        )
        if actual != expected:
            raise ValueError("pilot15 mode requires the canonical first 15 planned runs")
                
    return repo_root


def _load_smoke_config(request: LiveExecutionRequest, repo_root: Path):
    base = load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=repo_root / "configs" / "models.yaml",
        repo_root=repo_root,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo_root / "experiments" / "tasks.json").resolve(),
        raw_results_dir=Path(request.raw_jsonl_path).resolve().parent,
        derived_results_dir=(repo_root / "results" / "derived").resolve(),
        reviews_dir=(repo_root / "results" / "reviews").resolve(),
        workspace_base_dir=(repo_root / "workspaces" / request.experiment_id).resolve(),
        artifact_root=Path(request.artifact_root).resolve(),
        retrieval_log_root=Path(request.retrieval_log_root).resolve(),
    )
    return replace(base, repetitions=1, paths=paths)


def _load_smoke_config_from_smoke_request(request: SmokeExecutionRequest, repo_root: Path):
    base = load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=repo_root / "configs" / "models.yaml",
        repo_root=repo_root,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo_root / "experiments" / "tasks.json").resolve(),
        raw_results_dir=Path(request.raw_jsonl_path).resolve().parent,
        derived_results_dir=(repo_root / "results" / "derived").resolve(),
        reviews_dir=(repo_root / "results" / "reviews").resolve(),
        workspace_base_dir=(repo_root / "workspaces" / request.experiment_id).resolve(),
        artifact_root=Path(request.artifact_root).resolve(),
        retrieval_log_root=Path(request.retrieval_log_root).resolve(),
    )
    return replace(base, repetitions=1, paths=paths)


def _load_full_config(request: LiveExecutionRequest, repo_root: Path):
    base = load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=repo_root / "configs" / "models.yaml",
        repo_root=repo_root,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo_root / "experiments" / "tasks.json").resolve(),
        raw_results_dir=Path(request.raw_jsonl_path).resolve().parent,
        derived_results_dir=(repo_root / "results" / "derived").resolve(),
        reviews_dir=(repo_root / "results" / "reviews").resolve(),
        workspace_base_dir=(repo_root / "workspaces" / request.experiment_id).resolve(),
        artifact_root=Path(request.artifact_root).resolve(),
        retrieval_log_root=Path(request.retrieval_log_root).resolve(),
    )
    return replace(base, repetitions=3, paths=paths)


def _bind_plan_to_request(
    runs: tuple[PlannedRun, ...],
    experiment_id: str,
) -> tuple[PlannedRun, ...]:
    rebound = []
    for run in runs:
        identity = replace(
            run.identity,
            experiment_id=experiment_id,
            run_id=make_run_id(
                experiment_id=experiment_id,
                task_id=run.identity.task_id,
                strategy=run.identity.strategy,
                repetition=run.identity.repetition,
                seed=42,
            ),
        )
        rebound.append(replace(run, identity=identity))
    return tuple(rebound)


def _assert_attempt_accounting(
    before: int,
    after: int,
    recorded_attempts: int,
) -> None:
    if after - before != recorded_attempts:
        raise LiveExecutionAbort(
            "provider did not reserve every transport attempt before execution"
        )


def _result(
    tracker: LiveBudgetTracker,
    completed: list[str],
    *,
    quarantined: bool,
    abort_reason: str | None,
    report: SmokeGateReport | None = None,
    leakage_evidence: LeakageEvidence | None = None,
    resume_evidence: ResumeEvidence | None = None,
) -> SmokeExecutionResult:
    return SmokeExecutionResult(
        completed_run_ids=tuple(completed),
        model_call_count=tracker.model_call_count,
        provider_attempt_count=tracker.provider_attempt_count,
        total_input_tokens=tracker.consumed_input_tokens,
        total_output_tokens=tracker.consumed_output_tokens,
        quarantined=quarantined,
        abort_reason=abort_reason,
        report=report,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )
