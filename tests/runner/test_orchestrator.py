from __future__ import annotations

from dataclasses import dataclass

import pytest

from experiments.runner.errors import ResultWriteError
from experiments.runner.orchestrator import (
    EvaluatorRunSnapshot,
    ExperimentOrchestrator,
    merge_evaluator_snapshots,
    snapshot_from_evaluator_result,
)
from experiments.strategies.artifacts import ArtifactWriteError
from experiments.runner.strategy_factory import StrategyBundle
from experiments.strategies.models import StrategyFinalization, StrategyMetrics, StrategyPatchOutput


def _result(
    *,
    pass1_public: bool,
    pass1_hidden: bool,
    pass1_public_tests_passed: int,
    pass1_hidden_tests_passed: int,
    final_public: bool,
    final_hidden: bool,
    public_tests_passed: int,
    hidden_tests_passed: int,
    repair_rounds: int,
    test_latency_seconds: float = 0.25,
) -> dict:
    return {
        "pass1_public": pass1_public,
        "pass1_hidden": pass1_hidden,
        "pass1_public_tests_passed": pass1_public_tests_passed,
        "pass1_hidden_tests_passed": pass1_hidden_tests_passed,
        "final_public": final_public,
        "final_hidden": final_hidden,
        "public_tests_passed": public_tests_passed,
        "public_tests_total": 3,
        "hidden_tests_passed": hidden_tests_passed,
        "hidden_tests_total": 2,
        "repair_rounds": repair_rounds,
        "patch_apply_failures": 0,
        "test_latency_seconds": test_latency_seconds,
    }


def test_snapshot_from_evaluator_result_is_immutable_and_keeps_raw_result_copy():
    raw = _result(
        pass1_public=False,
        pass1_hidden=False,
        pass1_public_tests_passed=1,
        pass1_hidden_tests_passed=0,
        final_public=False,
        final_hidden=False,
        public_tests_passed=1,
        hidden_tests_passed=0,
        repair_rounds=0,
    )

    snapshot = snapshot_from_evaluator_result(raw)
    raw["public_tests_passed"] = 99

    assert isinstance(snapshot, EvaluatorRunSnapshot)
    assert snapshot.public_tests_passed == 1
    assert snapshot.raw_result["public_tests_passed"] == 1


def test_repair_final_pass_does_not_overwrite_pass1_fields():
    pass1 = snapshot_from_evaluator_result(
        _result(
            pass1_public=False,
            pass1_hidden=False,
            pass1_public_tests_passed=1,
            pass1_hidden_tests_passed=0,
            final_public=False,
            final_hidden=False,
            public_tests_passed=1,
            hidden_tests_passed=0,
            repair_rounds=0,
        )
    )
    latest = snapshot_from_evaluator_result(
        _result(
            pass1_public=True,
            pass1_hidden=True,
            pass1_public_tests_passed=3,
            pass1_hidden_tests_passed=2,
            final_public=True,
            final_hidden=True,
            public_tests_passed=3,
            hidden_tests_passed=2,
            repair_rounds=1,
        )
    )

    merged = merge_evaluator_snapshots(pass1=pass1, final_or_latest=latest)

    assert merged.result_fields["pass1_public"] is False
    assert merged.result_fields["pass1_hidden"] is False
    assert merged.result_fields["pass1_public_tests_passed"] == 1
    assert merged.result_fields["pass1_hidden_tests_passed"] == 0
    assert merged.result_fields["final_public"] is True
    assert merged.result_fields["final_hidden"] is True
    assert merged.result_fields["public_tests_passed"] == 3
    assert merged.result_fields["hidden_tests_passed"] == 2
    assert merged.result_fields["repair_rounds"] == 1


def test_repair_failure_after_initial_preserves_pass1_as_final_when_no_newer_snapshot():
    pass1 = snapshot_from_evaluator_result(
        _result(
            pass1_public=False,
            pass1_hidden=False,
            pass1_public_tests_passed=2,
            pass1_hidden_tests_passed=1,
            final_public=False,
            final_hidden=False,
            public_tests_passed=2,
            hidden_tests_passed=1,
            repair_rounds=0,
        )
    )

    merged = merge_evaluator_snapshots(pass1=pass1, final_or_latest=None)

    assert merged.result_fields["pass1_public_tests_passed"] == 2
    assert merged.result_fields["public_tests_passed"] == 2
    assert merged.result_fields["hidden_tests_passed"] == 1
    assert merged.result_fields["final_public"] is False
    assert merged.result_fields["final_hidden"] is False


def test_pre_initial_failure_uses_false_zero_evaluator_fields():
    merged = merge_evaluator_snapshots(pass1=None, final_or_latest=None)

    assert merged.result_fields == {
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


def test_orchestrator_calls_initial_once_and_pass1_evaluator_has_no_repairs(a_planned_run, experiment_config, project_root):
    session = FakeSession(initial_patch="diff-1", finalization=_finalization("artifact/ok"))
    evaluator = FakeEvaluator(
        [
            _result(
                pass1_public=True,
                pass1_hidden=False,
                pass1_public_tests_passed=3,
                pass1_hidden_tests_passed=1,
                final_public=True,
                final_hidden=False,
                public_tests_passed=3,
                hidden_tests_passed=1,
                repair_rounds=0,
            )
        ]
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=evaluator,
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert session.initial_calls == 1
    assert session.repair_calls == 0
    assert evaluator.calls == [("T01", "diff-1", ())]
    assert result.result_record["stop_reason"] == "public_pass"
    assert result.result_record["artifact_path"] == "artifact/ok"
    assert writer.records == [result.result_record]
    assert session.closed is True
    assert result.finalization_artifact_path == "artifact/ok"


def test_orchestrator_repairs_with_public_feedback_only(a_planned_run, experiment_config, project_root):
    session = FakeSession(initial_patch="diff-1", repair_patches=["diff-2"], finalization=_finalization("artifact/repaired"))
    evaluator = FakeEvaluator(
        [
            _result(
                pass1_public=False,
                pass1_hidden=False,
                pass1_public_tests_passed=1,
                pass1_hidden_tests_passed=0,
                final_public=False,
                final_hidden=False,
                public_tests_passed=1,
                hidden_tests_passed=0,
                repair_rounds=0,
            ),
            _result(
                pass1_public=True,
                pass1_hidden=True,
                pass1_public_tests_passed=3,
                pass1_hidden_tests_passed=2,
                final_public=True,
                final_hidden=True,
                public_tests_passed=3,
                hidden_tests_passed=2,
                repair_rounds=1,
            ),
        ],
        feedback_texts=["PUBLIC_ONLY no hidden sentinel"],
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=evaluator,
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert session.repair_calls == 1
    assert session.feedback_texts == ["PUBLIC_ONLY no hidden sentinel"]
    assert evaluator.calls == [("T01", "diff-1", ()), ("T01", "diff-1", ("diff-2",))]
    assert session.finalize_order == ["finalize"]
    assert result.result_record["pass1_public"] is False
    assert result.result_record["final_public"] is True
    assert result.result_record["repair_rounds"] == 1


def test_orchestrator_caps_repairs_at_two(a_planned_run, experiment_config, project_root):
    session = FakeSession(
        initial_patch="diff-1",
        repair_patches=["diff-2", "diff-3", "diff-4"],
        finalization=_finalization("artifact/limit"),
    )
    evaluator = FakeEvaluator(
        [
            _result(
                pass1_public=False,
                pass1_hidden=False,
                pass1_public_tests_passed=1,
                pass1_hidden_tests_passed=0,
                final_public=False,
                final_hidden=False,
                public_tests_passed=1,
                hidden_tests_passed=0,
                repair_rounds=0,
            ),
            _result(
                pass1_public=False,
                pass1_hidden=False,
                pass1_public_tests_passed=2,
                pass1_hidden_tests_passed=0,
                final_public=False,
                final_hidden=False,
                public_tests_passed=2,
                hidden_tests_passed=0,
                repair_rounds=1,
            ),
            _result(
                pass1_public=False,
                pass1_hidden=False,
                pass1_public_tests_passed=2,
                pass1_hidden_tests_passed=1,
                final_public=False,
                final_hidden=False,
                public_tests_passed=2,
                hidden_tests_passed=1,
                repair_rounds=2,
            ),
        ]
    )
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=evaluator,
        strategy_factory=FakeFactory(session),
        writer=FakeWriter(),
    )

    result = orchestrator.execute_run(a_planned_run)

    assert session.repair_calls == 2
    assert len(evaluator.calls) == 3
    assert result.result_record["stop_reason"] == "repair_limit"
    assert result.result_record["repair_rounds"] == 2
    assert result.result_record["test_latency_seconds"] == pytest.approx(0.75)


def test_success_result_uses_elapsed_monotonic_latency(a_planned_run, experiment_config, project_root):
    clock = SequenceClock([10.0] * 11 + [12.5])
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator(
            [
                _result(
                    pass1_public=True,
                    pass1_hidden=False,
                    pass1_public_tests_passed=3,
                    pass1_hidden_tests_passed=1,
                    final_public=True,
                    final_hidden=False,
                    public_tests_passed=3,
                    hidden_tests_passed=1,
                    repair_rounds=0,
                )
            ]
        ),
        strategy_factory=FakeFactory(FakeSession(initial_patch="diff-1", finalization=_finalization("artifact/ok"))),
        writer=FakeWriter(),
        monotonic=clock,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert result.result_record["latency_seconds"] == pytest.approx(2.5)


def test_terminal_failure_uses_elapsed_monotonic_latency(a_planned_run, experiment_config, project_root):
    clock = SequenceClock([5.0, 5.0, 5.0, 5.0, 7.0])
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(
            FakeSession(initial_error=RuntimeError("boom"), finalization=_finalization("artifact/never"))
        ),
        writer=FakeWriter(),
        monotonic=clock,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert result.result_record["latency_seconds"] == pytest.approx(2.0)


def test_repair_generation_failure_preserves_completed_evaluator_latency(
    a_planned_run,
    experiment_config,
    project_root,
):
    session = FakeSession(
        initial_patch="diff-1",
        repair_error=RuntimeError("repair failed"),
        finalization=_finalization("artifact/never"),
    )
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator(
            [
                _result(
                    pass1_public=False,
                    pass1_hidden=False,
                    pass1_public_tests_passed=1,
                    pass1_hidden_tests_passed=0,
                    final_public=False,
                    final_hidden=False,
                    public_tests_passed=1,
                    hidden_tests_passed=0,
                    repair_rounds=0,
                    test_latency_seconds=0.4,
                )
            ]
        ),
        strategy_factory=FakeFactory(session),
        writer=FakeWriter(),
    )

    result = orchestrator.execute_run(a_planned_run)

    assert result.result_record["test_latency_seconds"] == pytest.approx(0.4)


def test_orchestrator_closes_and_writes_failure_record_on_strategy_failure(a_planned_run, experiment_config, project_root):
    session = FakeSession(initial_error=RuntimeError("boom"), finalization=_finalization("artifact/never"))
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert session.closed is True
    assert session.close_calls == 1
    assert result.result_record["valid_run"] is False
    assert result.result_record["input_tokens"] == 0
    assert writer.records == [result.result_record]


def test_strategy_failure_close_error_prevents_append(a_planned_run, experiment_config, project_root):
    close_error = ArtifactWriteError("artifact rollback failed")
    session = FakeSession(
        initial_error=RuntimeError("boom"),
        close_error=close_error,
        finalization=_finalization("artifact/never"),
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(ArtifactWriteError, match="artifact rollback failed"):
        orchestrator.execute_run(a_planned_run)

    assert session.close_calls == 1
    assert writer.records == []


def test_strategy_failure_close_integrity_unknown_prevents_append(
    a_planned_run,
    experiment_config,
    project_root,
):
    session = FakeSession(
        initial_error=RuntimeError("boom"),
        close_error=ArtifactWriteError("artifact_integrity_unknown=True"),
        finalization=_finalization("artifact/never"),
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(ArtifactWriteError, match="artifact_integrity_unknown=True"):
        orchestrator.execute_run(a_planned_run)

    assert writer.records == []


def test_finalized_close_error_prevents_append(a_planned_run, experiment_config, project_root):
    session = FakeSession(
        initial_patch="diff-1",
        close_error=ArtifactWriteError("finalized close failed"),
        finalization=_finalization("artifact/finalized"),
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator(
            [
                _result(
                    pass1_public=True,
                    pass1_hidden=True,
                    pass1_public_tests_passed=3,
                    pass1_hidden_tests_passed=2,
                    final_public=True,
                    final_hidden=True,
                    public_tests_passed=3,
                    hidden_tests_passed=2,
                    repair_rounds=0,
                )
            ]
        ),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(ArtifactWriteError, match="finalized close failed"):
        orchestrator.execute_run(a_planned_run)

    assert session.finalize_order == ["finalize"]
    assert session.close_calls == 1
    assert writer.records == []


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(9), GeneratorExit()])
def test_base_exceptions_close_session_and_propagate(
    a_planned_run,
    experiment_config,
    project_root,
    interrupt,
):
    session = FakeSession(initial_error=interrupt, finalization=_finalization("artifact/never"))
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(type(interrupt)):
        orchestrator.execute_run(a_planned_run)

    assert session.closed is True
    assert writer.records == []


def test_keyboard_interrupt_precedes_close_failure_and_writes_nothing(
    a_planned_run,
    experiment_config,
    project_root,
):
    interrupt = KeyboardInterrupt()
    session = FakeSession(
        initial_error=interrupt,
        close_error=ArtifactWriteError("artifact_integrity_unknown=True"),
        finalization=_finalization("artifact/never"),
    )
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        orchestrator.execute_run(a_planned_run)

    assert caught.value is interrupt
    assert session.close_calls == 1
    assert writer.records == []


def test_writer_failure_propagates_and_append_is_called_once(a_planned_run, experiment_config, project_root):
    session = FakeSession(initial_patch="diff-1", finalization=_finalization("artifact/finalized"))
    writer = FailingWriter(ResultWriteError("transient writer failure"))
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator(
            [
                _result(
                    pass1_public=True,
                    pass1_hidden=True,
                    pass1_public_tests_passed=3,
                    pass1_hidden_tests_passed=2,
                    final_public=True,
                    final_hidden=True,
                    public_tests_passed=3,
                    hidden_tests_passed=2,
                    repair_rounds=0,
                )
            ]
        ),
        strategy_factory=FakeFactory(session),
        writer=writer,
    )

    with pytest.raises(ResultWriteError, match="transient writer failure"):
        orchestrator.execute_run(a_planned_run)

    assert writer.calls == 1
    assert session.closed is True
    assert session.finalize_order == ["finalize"]


def test_integrity_unknown_writer_failure_is_not_retried(a_planned_run, experiment_config, project_root):
    writer = FailingWriter(ResultWriteError("result_integrity_unknown=True"))
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=FakeEvaluator([]),
        strategy_factory=FakeFactory(
            FakeSession(initial_error=RuntimeError("strategy failed"), finalization=_finalization("artifact/never"))
        ),
        writer=writer,
    )

    with pytest.raises(ResultWriteError, match="result_integrity_unknown=True"):
        orchestrator.execute_run(a_planned_run)

    assert writer.calls == 1


def test_total_run_timeout_stops_before_evaluator_and_finalize(
    a_planned_run,
    experiment_config,
    project_root,
):
    clock = SequenceClock([0.0, 0.0, 0.0, 0.0, experiment_config.total_run_timeout_seconds + 1.0])
    session = FakeSession(initial_patch="diff-1", finalization=_finalization("artifact/never"))
    evaluator = FakeEvaluator([])
    writer = FakeWriter()
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=evaluator,
        strategy_factory=FakeFactory(session),
        writer=writer,
        monotonic=clock,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert evaluator.calls == []
    assert session.finalize_order == []
    assert session.closed is True
    assert result.result_record["valid_run"] is False
    assert result.result_record["infra_error"] is True
    assert result.result_record["error_type"] == "runner_error"
    assert result.result_record["stop_reason"] == "infra_error"
    assert result.result_record["latency_seconds"] >= 0.0


def test_total_run_timeout_after_evaluator_does_not_start_repair_or_finalize(
    a_planned_run,
    experiment_config,
    project_root,
):
    timeout = experiment_config.total_run_timeout_seconds
    clock = SequenceClock([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, timeout + 1.0])
    session = FakeSession(initial_patch="diff-1", repair_patches=["diff-2"], finalization=_finalization("artifact/never"))
    evaluator = FakeEvaluator(
        [
            _result(
                pass1_public=False,
                pass1_hidden=False,
                pass1_public_tests_passed=1,
                pass1_hidden_tests_passed=0,
                final_public=False,
                final_hidden=False,
                public_tests_passed=1,
                hidden_tests_passed=0,
                repair_rounds=0,
            )
        ]
    )
    orchestrator = ExperimentOrchestrator(
        config=experiment_config,
        repo_root=project_root,
        evaluator=evaluator,
        strategy_factory=FakeFactory(session),
        writer=FakeWriter(),
        monotonic=clock,
    )

    result = orchestrator.execute_run(a_planned_run)

    assert len(evaluator.calls) == 1
    assert session.repair_calls == 0
    assert session.finalize_order == []
    assert result.result_record["error_type"] == "runner_error"


@dataclass
class FakePublicFeedbackRecord:
    round_index: int
    sanitized_public_feedback: str


class FakeEvaluator:
    def __init__(self, results: list[dict], feedback_texts: list[str] | None = None) -> None:
        self.results = list(results)
        self.feedback_texts = feedback_texts or ["public feedback"]
        self.public_feedback_history: list[FakePublicFeedbackRecord] = []
        self.calls: list[tuple[str, str, tuple[str, ...]]] = []

    def evaluate_task(self, task_id, initial_patch, repair_patches=(), max_repair_rounds=0, **kwargs):
        assert isinstance(initial_patch, str)
        assert isinstance(repair_patches, tuple)
        self.calls.append((task_id, initial_patch, repair_patches))
        result = self.results.pop(0)
        if not result["final_public"]:
            self.public_feedback_history.append(
                FakePublicFeedbackRecord(len(self.public_feedback_history), self.feedback_texts[-1])
            )
        return result


class FakeFactory:
    def __init__(self, session: "FakeSession") -> None:
        self.session = session

    def create(self, *, run, config, repo_root):
        return StrategyBundle(
            session=self.session,
            provider=object(),
            strategy=run.identity.strategy,
            model=config.model,
            seed=config.seed,
            retrieval_log_path=None,
        )


class FakeSession:
    def __init__(
        self,
        *,
        initial_patch: str = "diff",
        repair_patches: list[str] | None = None,
        finalization: StrategyFinalization,
        initial_error: BaseException | None = None,
        repair_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.initial_patch = initial_patch
        self.repair_patches = list(repair_patches or [])
        self.finalization = finalization
        self.initial_error = initial_error
        self.repair_error = repair_error
        self.close_error = close_error
        self.initial_calls = 0
        self.repair_calls = 0
        self.feedback_texts: list[str] = []
        self.finalize_order: list[str] = []
        self.closed = False
        self.close_calls = 0

    def generate_initial_patch(self):
        self.initial_calls += 1
        if self.initial_error is not None:
            raise self.initial_error
        return StrategyPatchOutput(patch=self.initial_patch, reviewer_verdict=None, metrics=self.finalization.metrics)

    def generate_repair_patch(self, feedback, previous_patch):
        self.repair_calls += 1
        self.feedback_texts.append(feedback.text)
        if self.repair_error is not None:
            raise self.repair_error
        return StrategyPatchOutput(
            patch=self.repair_patches.pop(0),
            reviewer_verdict=None,
            metrics=self.finalization.metrics,
        )

    def finalize(self):
        self.finalize_order.append("finalize")
        return self.finalization

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeWriter:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def append(self, record: dict) -> None:
        self.records.append(dict(record))


class FailingWriter:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def append(self, record: dict) -> None:
        self.calls += 1
        raise self.error


class SequenceClock:
    def __init__(self, values: list[float]) -> None:
        self.values = list(values)
        self.last = self.values[-1]

    def __call__(self) -> float:
        if self.values:
            self.last = self.values.pop(0)
        return self.last


def _finalization(artifact_path: str) -> StrategyFinalization:
    return StrategyFinalization(
        metrics=StrategyMetrics(
            model_call_count=1,
            provider_attempt_count=1,
            failed_provider_call_count=0,
            tool_calls=0,
            retrieved_tokens=0,
            input_tokens=5,
            output_tokens=4,
            estimated_cost=None,
            model_latency_seconds=0.1,
            retrieval_success=None,
            call_records=(),
            attempt_records=(),
            failure_audit_records=(),
        ),
        artifact_path=artifact_path,
        manifest_sha256="0" * 64,
    )
