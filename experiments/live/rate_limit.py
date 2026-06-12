from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import time
from email.utils import parsedate_to_datetime

@dataclass(frozen=True)
class LiveRateLimitPolicy:
    minimum_attempt_interval_seconds: float
    inter_run_cooldown_seconds: float
    retry_after_min_seconds: float
    retry_after_max_seconds: float
    fallback_429_delays: tuple[float, float]

class LiveRateLimiter:
    def __init__(
        self,
        policy: LiveRateLimitPolicy,
        clock: Callable[[], float] = time.monotonic,
        epoch_clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.policy = policy
        self.clock = clock
        self.epoch_clock = epoch_clock
        self.sleeper = sleeper
        self.last_attempt_time: float | None = None

    def wait_before_attempt(
        self, *, cancellation: object | None = None, check_budget_fn: Callable[[], None] | None = None
    ) -> float:
        self._check_cancellation(cancellation)
        if check_budget_fn is not None:
            check_budget_fn()
        now = self.clock()
        slept = 0.0
        if self.last_attempt_time is not None:
            elapsed = now - self.last_attempt_time
            needed = self.policy.minimum_attempt_interval_seconds
            if elapsed < needed:
                wait_time = needed - elapsed
                self.sleeper(wait_time)
                slept = wait_time
                if check_budget_fn is not None:
                    check_budget_fn()
        
        self._check_cancellation(cancellation)
        self.last_attempt_time = self.clock()
        return slept

    def wait_after_completed_run(
        self, *, cancellation: object | None = None, check_budget_fn: Callable[[], None] | None = None
    ) -> float:
        self._check_cancellation(cancellation)
        if check_budget_fn is not None:
            check_budget_fn()
        cooldown = self.policy.inter_run_cooldown_seconds
        if cooldown > 0:
            self.sleeper(cooldown)
            if check_budget_fn is not None:
                check_budget_fn()
        self._check_cancellation(cancellation)
        return cooldown

    def resolve_retry_delay(
        self,
        attempt_index: int,
        response: object, # TransportResponse
        now_epoch_seconds: float,
    ) -> float:
        status = getattr(response, "status_code", None)
        if status != 429:
            if status in (502, 503, 504):
                if attempt_index == 1:
                    return 0.25
                elif attempt_index == 2:
                    return 0.50
                return 0.50
            return 0.0

        retry_after_val = None
        headers = getattr(response, "allowlisted_headers", ())
        for k, v in headers:
            if k.lower() == "retry-after":
                retry_after_val = v
                break
        
        delay = None
        if retry_after_val is not None:
            try:
                val = int(retry_after_val)
                if val >= 0:
                    delay = float(val)
            except ValueError:
                try:
                    dt = parsedate_to_datetime(retry_after_val)
                    target_epoch = dt.timestamp()
                    delay = target_epoch - now_epoch_seconds
                except Exception:
                    pass

        if delay is None or delay < 0:
            if attempt_index == 1:
                delay = self.policy.fallback_429_delays[0]
            else:
                delay = self.policy.fallback_429_delays[1]

        delay = max(self.policy.retry_after_min_seconds, min(self.policy.retry_after_max_seconds, delay))
        return delay

    def _check_cancellation(self, cancellation: object | None) -> None:
        if cancellation is not None:
            is_cancelled = getattr(cancellation, "is_cancelled", None)
            if is_cancelled is not None and is_cancelled():
                raise RuntimeError("Request cancelled")
            raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
            if raise_if_cancelled is not None:
                raise_if_cancelled()
