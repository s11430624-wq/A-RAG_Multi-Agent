from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from experiments.runner.config import ExperimentConfig
from experiments.runner.errors import TotalRunTimeoutError
from experiments.runner.failure import build_result_record, classify_runner_exception
from experiments.runner.scheduler import PlannedRun
from experiments.strategies.metrics import project_for_result_schema
from experiments.strategies.models import SanitizedPublicFeedback


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
    raw_result: Mapping[str, Any]


@dataclass(frozen=True)
class MergedEvaluationSnapshots:
    pass1: EvaluatorRunSnapshot | None
    final_or_latest: EvaluatorRunSnapshot | None
    result_fields: Mapping[str, Any]


@dataclass(frozen=True)
class RunExecutionResult:
    identity: object
    result_record: Mapping[str, Any]
    finalization_artifact_path: str | None
    wrote_result: bool
    skipped_existing: bool


class ExperimentOrchestrator:
    def __init__(
        self,
        *,
        config: ExperimentConfig,
        repo_root,
        evaluator,
        strategy_factory,
        writer,
        monotonic=None,
    ) -> None:
        self.config = config
        self.repo_root = repo_root
        self.evaluator = evaluator
        self.strategy_factory = strategy_factory
        self.writer = writer
        self.monotonic = monotonic or time.monotonic

    def execute_run(self, run: PlannedRun) -> RunExecutionResult:
        started_at = self.monotonic()
        deadline = started_at + self.config.total_run_timeout_seconds
        session = None
        pass1: EvaluatorRunSnapshot | None = None
        latest: EvaluatorRunSnapshot | None = None
        finalization_artifact_path: str | None = None
        accumulated_test_latency_seconds = 0.0
        try:
            self._check_deadline(deadline, "strategy factory")
            bundle = self.strategy_factory.create(run=run, config=self.config, repo_root=self.repo_root)
            session = bundle.session
            self._check_deadline(deadline, "strategy factory")
            self._check_deadline(deadline, "initial generation")
            initial_output = session.generate_initial_patch()
            self._check_deadline(deadline, "initial generation")
            initial_patch = initial_output.patch
            repair_patches: list[str] = []

            self._check_deadline(deadline, "initial evaluator")
            pass1_result = self.evaluator.evaluate_task(
                run.identity.task_id,
                initial_patch,
                repair_patches=(),
                max_repair_rounds=0,
                run_id=run.identity.run_id,
                strategy=run.identity.strategy,
                repetition=run.identity.repetition,
                model=self.config.model,
                seed=self.config.seed,
            )
            pass1 = snapshot_from_evaluator_result(pass1_result)
            accumulated_test_latency_seconds += pass1.test_latency_seconds
            latest = pass1
            self._check_deadline(deadline, "initial evaluator")

            while not latest.final_public and len(repair_patches) < self.config.max_repair_rounds:
                feedback = _latest_public_feedback(self.evaluator)
                previous_patch = repair_patches[-1] if repair_patches else initial_patch
                self._check_deadline(deadline, "repair generation")
                repair_output = session.generate_repair_patch(feedback, previous_patch)
                self._check_deadline(deadline, "repair generation")
                repair_patches.append(repair_output.patch)
                self._check_deadline(deadline, "repair evaluator")
                latest_result = self.evaluator.evaluate_task(
                    run.identity.task_id,
                    initial_patch,
                    repair_patches=tuple(repair_patches),
                    max_repair_rounds=len(repair_patches),
                    run_id=run.identity.run_id,
                    strategy=run.identity.strategy,
                    repetition=run.identity.repetition,
                    model=self.config.model,
                    seed=self.config.seed,
                )
                latest = snapshot_from_evaluator_result(latest_result)
                accumulated_test_latency_seconds += latest.test_latency_seconds
                self._check_deadline(deadline, "repair evaluator")

            merged = merge_evaluator_snapshots(
                pass1=pass1,
                final_or_latest=latest if latest is not pass1 else None,
                accumulated_test_latency_seconds=accumulated_test_latency_seconds,
            )
            self._check_deadline(deadline, "strategy finalization")
            finalization = session.finalize()
            finalization_artifact_path = finalization.artifact_path
            self._check_deadline(deadline, "strategy finalization")
            self._check_deadline(deadline, "result projection")
            projection = project_for_result_schema(finalization=finalization)
            self._check_deadline(deadline, "result projection")
        except Exception as exc:
            _close_session(session)
            if hasattr(self.writer, "set_active_exception"):
                self.writer.set_active_exception(exc)
            
            # Diagnostic Logger Integration
            if hasattr(exc, "raw_response") and hasattr(exc, "role"):
                try:
                    from experiments.live.diagnostics import AbortDiagnosticWriter
                    diag_writer = AbortDiagnosticWriter(self.repo_root)
                    diag_writer.write_raw_response(
                        experiment_id=run.identity.experiment_id,
                        run_id=run.identity.run_id,
                        role=getattr(exc, "role"),
                        error_type=exc.__class__.__name__,
                        error_message=str(exc),
                        raw_response=getattr(exc, "raw_response"),
                    )
                except Exception:
                    pass

            failure = classify_runner_exception(exc)
            merged = merge_evaluator_snapshots(
                pass1=pass1,
                final_or_latest=latest if latest is not pass1 else None,
                accumulated_test_latency_seconds=accumulated_test_latency_seconds,
            )
            elapsed_seconds = max(0.0, self.monotonic() - started_at)
            record = build_result_record(
                run=run,
                merged=merged,
                projection=None,
                terminal_failure=failure,
                model=self.config.model,
                finalized_artifact_path=finalization_artifact_path,
                latency_seconds=elapsed_seconds,
            )
        except BaseException:
            _best_effort_close_for_interrupt(session)
            raise
        else:
            _close_session(session)
            elapsed_seconds = max(0.0, self.monotonic() - started_at)
            record = build_result_record(
                run=run,
                merged=merged,
                projection=projection,
                terminal_failure=None,
                model=self.config.model,
                latency_seconds=elapsed_seconds,
            )
        self.writer.append(record)
        return RunExecutionResult(run.identity, MappingProxyType(dict(record)), finalization_artifact_path, True, False)

    def _check_deadline(self, deadline: float, operation: str) -> None:
        if self.monotonic() > deadline:
            raise TotalRunTimeoutError(f"total run deadline exceeded during {operation}")


def snapshot_from_evaluator_result(result: Mapping[str, Any]) -> EvaluatorRunSnapshot:
    raw_copy = dict(result)
    return EvaluatorRunSnapshot(
        pass1_public=bool(raw_copy["pass1_public"]),
        pass1_hidden=bool(raw_copy["pass1_hidden"]),
        pass1_public_tests_passed=int(raw_copy["pass1_public_tests_passed"]),
        pass1_hidden_tests_passed=int(raw_copy["pass1_hidden_tests_passed"]),
        final_public=bool(raw_copy["final_public"]),
        final_hidden=bool(raw_copy["final_hidden"]),
        public_tests_passed=int(raw_copy["public_tests_passed"]),
        public_tests_total=int(raw_copy["public_tests_total"]),
        hidden_tests_passed=int(raw_copy["hidden_tests_passed"]),
        hidden_tests_total=int(raw_copy["hidden_tests_total"]),
        repair_rounds=int(raw_copy["repair_rounds"]),
        patch_apply_failures=int(raw_copy["patch_apply_failures"]),
        test_latency_seconds=float(raw_copy["test_latency_seconds"]),
        raw_result=MappingProxyType(raw_copy),
    )


def merge_evaluator_snapshots(
    *,
    pass1: EvaluatorRunSnapshot | None,
    final_or_latest: EvaluatorRunSnapshot | None,
    accumulated_test_latency_seconds: float | None = None,
) -> MergedEvaluationSnapshots:
    final = final_or_latest or pass1
    if pass1 is None and final is None:
        fields: dict[str, Any] = {
            "pass1_public": False,
            "pass1_hidden": False,
            "pass1_public_tests_passed": 0,
            "pass1_hidden_tests_passed": 0,
            "final_public": False,
            "final_hidden": False,
            "public_tests_passed": 0,
            "public_tests_total": 0,
            "hidden_tests_passed": 0,
            "hidden_tests_total": 0,
            "repair_rounds": 0,
            "patch_apply_failures": 0,
            "test_latency_seconds": 0.0,
        }
    else:
        assert pass1 is not None
        assert final is not None
        fields = {
            "pass1_public": pass1.pass1_public,
            "pass1_hidden": pass1.pass1_hidden,
            "pass1_public_tests_passed": pass1.pass1_public_tests_passed,
            "pass1_hidden_tests_passed": pass1.pass1_hidden_tests_passed,
            "final_public": final.final_public,
            "final_hidden": final.final_hidden,
            "public_tests_passed": final.public_tests_passed,
            "public_tests_total": final.public_tests_total,
            "hidden_tests_passed": final.hidden_tests_passed,
            "hidden_tests_total": final.hidden_tests_total,
            "repair_rounds": final.repair_rounds,
            "patch_apply_failures": final.patch_apply_failures,
            "test_latency_seconds": (
                final.test_latency_seconds
                if accumulated_test_latency_seconds is None
                else float(accumulated_test_latency_seconds)
            ),
        }
    return MergedEvaluationSnapshots(
        pass1=pass1,
        final_or_latest=final,
        result_fields=MappingProxyType(fields),
    )


def _latest_public_feedback(evaluator) -> SanitizedPublicFeedback:
    history = getattr(evaluator, "public_feedback_history", None)
    if not history:
        text = "No public feedback was produced."
        round_index = 0
    else:
        record = history[-1]
        text = str(record.sanitized_public_feedback)
        round_index = int(record.round_index)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SanitizedPublicFeedback(round_index=round_index, text=text, sha256=digest)


def _close_session(session) -> None:
    if session is None or not hasattr(session, "close"):
        return
    session.close()


def _best_effort_close_for_interrupt(session) -> None:
    if session is None or not hasattr(session, "close"):
        return
    try:
        session.close()
    except Exception:
        pass
