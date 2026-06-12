from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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


class ExperimentConfigError(ValueError):
    pass


class ResultValidationError(ValueError):
    pass


class ResultWriteError(RuntimeError):
    pass


class TotalRunTimeoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunnerFailure:
    error_type: ResultErrorType
    stop_reason: StopReason
    infra_error: bool
    valid_run: bool
    message: str
