from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

class BudgetExceededError(Exception):
    pass


@dataclass(frozen=True)
class BudgetLimits:
    max_total_input_tokens: int
    max_total_output_tokens: int
    max_total_calls: int
    max_infra_failures: int
    max_consecutive_infra_failures: int
    max_gateway_failures: int
    max_wall_clock_seconds: float
    max_total_cost_usd: float | None = None
    max_run_cost_usd: float | None = None

    def __post_init__(self) -> None:
        # Validate required limits are positive integers and NOT boolean
        for field_name in (
            "max_total_input_tokens",
            "max_total_output_tokens",
            "max_total_calls",
            "max_infra_failures",
            "max_consecutive_infra_failures",
            "max_gateway_failures",
        ):
            val = getattr(self, field_name)
            if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                raise ValueError(f"{field_name} must be a positive integer, got {val}")

        # max_wall_clock_seconds must be a positive number
        val = self.max_wall_clock_seconds
        if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
            raise ValueError(f"max_wall_clock_seconds must be a positive number, got {val}")

        # max_total_cost_usd and max_run_cost_usd must be None or positive numbers
        for field_name in ("max_total_cost_usd", "max_run_cost_usd"):
            val = getattr(self, field_name)
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
                    raise ValueError(f"{field_name} must be a positive number, got {val}")


def validate_non_negative_integer(val, name: str) -> None:
    # Reject boolean, float, or negative integer
    if isinstance(val, bool) or not isinstance(val, int) or val < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {val}")


class LiveBudgetTracker:
    def __init__(self, limits: BudgetLimits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self.clock = clock
        self.consumed_input_tokens = 0
        self.consumed_output_tokens = 0
        self.provider_attempt_count = 0
        self.model_call_count = 0
        self.consecutive_infra_failures = 0
        self.total_infra_failures = 0
        self.gateway_failures = 0
        self.start_time = clock()

    @property
    def total_calls(self) -> int:
        return self.provider_attempt_count

    def record_model_call_start(self) -> None:
        self._check_wall_clock()
        self.model_call_count += 1

    def reserve_provider_attempt(self) -> None:
        if self.provider_attempt_count >= self.limits.max_total_calls:
            raise BudgetExceededError("Total API calls limit exceeded")
        self._check_wall_clock()
        self.provider_attempt_count += 1

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        validate_non_negative_integer(input_tokens, "input_tokens")
        validate_non_negative_integer(output_tokens, "output_tokens")

        # Hypothesize new state
        new_input = self.consumed_input_tokens + input_tokens
        new_output = self.consumed_output_tokens + output_tokens
        # Check limits on hypothesized state before modifying actual state
        if new_input > self.limits.max_total_input_tokens:
            raise BudgetExceededError("Input token budget exceeded")
        if new_output > self.limits.max_total_output_tokens:
            raise BudgetExceededError("Output token budget exceeded")
        self._check_wall_clock()

        # If safe, commit modifications
        self.consumed_input_tokens = new_input
        self.consumed_output_tokens = new_output

    def record_failure(self, is_infra: bool, is_gateway: bool) -> None:
        if not isinstance(is_infra, bool) or not isinstance(is_gateway, bool):
            raise ValueError("is_infra and is_gateway must be booleans")

        # Hypothesize new state
        new_total_infra = self.total_infra_failures
        new_consecutive_infra = self.consecutive_infra_failures
        new_gateway = self.gateway_failures

        if is_infra:
            new_total_infra += 1
            new_consecutive_infra += 1
        else:
            new_consecutive_infra = 0

        if is_gateway:
            new_gateway += 1

        # Check limits on hypothesized state before committing
        if new_total_infra > self.limits.max_infra_failures:
            raise BudgetExceededError("Infrastructure failures limit exceeded")
        if new_consecutive_infra >= self.limits.max_consecutive_infra_failures:
            raise BudgetExceededError("Consecutive infrastructure failures limit exceeded")
        if new_gateway > self.limits.max_gateway_failures:
            raise BudgetExceededError("Gateway failures limit exceeded")

        self._check_wall_clock()

        # Commit modifications
        self.total_infra_failures = new_total_infra
        self.consecutive_infra_failures = new_consecutive_infra
        self.gateway_failures = new_gateway

    def _check_wall_clock(self) -> None:
        elapsed = self.clock() - self.start_time
        if elapsed > self.limits.max_wall_clock_seconds:
            raise BudgetExceededError("Wall clock time budget exceeded")
