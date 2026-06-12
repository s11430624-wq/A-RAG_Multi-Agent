from __future__ import annotations

from typing import Any

from experiments.evaluation.metrics import EmptyResponseError, RunnerError, TestTimeoutError
from experiments.providers.models import (
    ProviderAuthenticationError,
    ProviderEmptyResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
    ProviderUsageUnavailableError,
)
from experiments.runner.errors import RunnerFailure, TotalRunTimeoutError
from experiments.runner.scheduler import PlannedRun
from experiments.runtime.patching import InvalidPatchError as RuntimeInvalidPatchError
from experiments.runtime.patching import PatchApplyError
from experiments.runtime.workspace import CleanupError
from experiments.strategies.models import StrategyResultProjection
from experiments.strategies.parsers import InvalidPatchError as StrategyInvalidPatchError


def classify_runner_exception(exc: BaseException) -> RunnerFailure:
    from experiments.live.budget import BudgetExceededError
    if isinstance(exc, BudgetExceededError):
        return _failure("budget_exceeded", "infra_error", True, False, str(exc))
    if isinstance(exc, ProviderTimeoutError):
        return _failure("model_timeout", "infra_error", True, False, str(exc))
    if isinstance(exc, (ProviderTransportError, ProviderAuthenticationError)):
        return _failure("gateway_error", "infra_error", True, False, str(exc))
    if isinstance(exc, (ProviderEmptyResponseError, EmptyResponseError)):
        return _failure("empty_response", "repair_limit", False, True, str(exc))
    if isinstance(exc, (StrategyInvalidPatchError, RuntimeInvalidPatchError)):
        return _failure("invalid_patch", "repair_limit", False, True, str(exc))
    if isinstance(exc, PatchApplyError):
        return _failure("patch_apply_error", "repair_limit", False, True, str(exc))
    if isinstance(exc, TestTimeoutError):
        return _failure("test_timeout", "infra_error", True, False, str(exc))
    if isinstance(exc, (RunnerError, CleanupError)):
        return _failure("runner_error", "infra_error", True, False, str(exc))
    if isinstance(exc, TotalRunTimeoutError):
        return _failure("runner_error", "infra_error", True, False, str(exc))
    if isinstance(exc, ProviderUsageUnavailableError):
        return _failure("unknown", "infra_error", True, False, str(exc))
    return _failure("unknown", "infra_error", True, False, str(exc))


def build_result_record(
    *,
    run: PlannedRun,
    merged,
    projection: StrategyResultProjection | None,
    terminal_failure: RunnerFailure | None,
    model: str | None = None,
    finalized_artifact_path: str | None = None,
    latency_seconds: float = 0.0,
) -> dict[str, Any]:
    if terminal_failure is None:
        if projection is None:
            raise ValueError("projection is required for successful result records")
        status = _terminal_status_from_evaluation(merged)
        usage_fields = {
            "tool_calls": projection.tool_calls,
            "retrieved_tokens": projection.retrieved_tokens,
            "retrieval_success": projection.retrieval_success,
            "input_tokens": projection.input_tokens,
            "output_tokens": projection.output_tokens,
            "estimated_cost": projection.estimated_cost,
            "model_latency_seconds": projection.model_latency_seconds,
            "infra_error": False,
            "error_type": "none",
            "stop_reason": status,
            "artifact_path": projection.artifact_path,
            "valid_run": True,
        }
    else:
        usage_fields = {
            "tool_calls": 0,
            "retrieved_tokens": 0,
            "retrieval_success": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": None,
            "model_latency_seconds": 0.0,
            "infra_error": terminal_failure.infra_error,
            "error_type": terminal_failure.error_type,
            "stop_reason": terminal_failure.stop_reason,
            "artifact_path": finalized_artifact_path,
            "valid_run": terminal_failure.valid_run,
        }
    record = {
        "run_id": run.identity.run_id,
        "task_id": run.identity.task_id,
        "strategy": run.identity.strategy,
        "repetition": run.identity.repetition,
        "model": model or _model_from_experiment_id(run.identity.experiment_id),
        "seed": run.identity.seed,
        **usage_fields,
        **dict(merged.result_fields),
        "latency_seconds": float(latency_seconds),
        "api_correct": None,
        "hallucinated_api": None,
        "requirement_score": None,
        "quality_score": None,
        "manual_review_status": "pending",
    }
    return record


def _terminal_status_from_evaluation(merged: MergedEvaluationSnapshots) -> str:
    if merged.result_fields["final_public"]:
        return "public_pass"
    return "repair_limit"


def _model_from_experiment_id(experiment_id: str) -> str:
    parts = experiment_id.split("-")
    if len(parts) >= 4 and parts[0] == "exp":
        try:
            seed_index = parts.index("seed42")
        except ValueError:
            seed_index = next((index for index, part in enumerate(parts) if part.startswith("seed")), len(parts))
        slug = "-".join(parts[2:seed_index])
        if slug:
            return slug
    return "unknown"


def _failure(error_type, stop_reason, infra_error, valid_run, message) -> RunnerFailure:
    return RunnerFailure(
        error_type=error_type,
        stop_reason=stop_reason,
        infra_error=infra_error,
        valid_run=valid_run,
        message=message,
    )
