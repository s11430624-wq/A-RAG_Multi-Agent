from __future__ import annotations

import pytest
from experiments.live.budget import BudgetLimits, LiveBudgetTracker, BudgetExceededError

def test_budget_tracker_enforces_tokens():
    limits = BudgetLimits(
        max_total_input_tokens=100,
        max_total_output_tokens=50,
        max_total_calls=10,
        max_infra_failures=2,
        max_consecutive_infra_failures=1,
        max_gateway_failures=2,
        max_wall_clock_seconds=600.0,
    )
    tracker = LiveBudgetTracker(limits)
    
    tracker.record_model_call_start()
    tracker.reserve_provider_attempt()
    tracker.record_tokens(50, 20)
    assert tracker.consumed_input_tokens == 50
    assert tracker.consumed_output_tokens == 20
    assert tracker.total_calls == 1
    assert tracker.model_call_count == 1
    
    # Over input token budget
    with pytest.raises(BudgetExceededError, match="Input token budget exceeded"):
        tracker.record_tokens(60, 10)

    # State must not be modified after failure (transactional check)
    assert tracker.consumed_input_tokens == 50
    assert tracker.consumed_output_tokens == 20
    assert tracker.total_calls == 1


def test_failed_attempt_reservation_counts_without_tokens():
    limits = BudgetLimits(
        max_total_input_tokens=100,
        max_total_output_tokens=50,
        max_total_calls=2,
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=600.0,
    )
    tracker = LiveBudgetTracker(limits)

    tracker.record_model_call_start()
    tracker.reserve_provider_attempt()
    tracker.record_failure(is_infra=True, is_gateway=True)

    assert tracker.model_call_count == 1
    assert tracker.provider_attempt_count == 1
    assert tracker.consumed_input_tokens == 0
    assert tracker.consumed_output_tokens == 0


def test_provider_attempt_limit_rejects_before_attempt_23():
    limits = BudgetLimits(
        max_total_input_tokens=1000,
        max_total_output_tokens=1000,
        max_total_calls=22,
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=600.0,
    )
    tracker = LiveBudgetTracker(limits)

    for _ in range(22):
        tracker.reserve_provider_attempt()

    with pytest.raises(BudgetExceededError, match="Total API calls limit exceeded"):
        tracker.reserve_provider_attempt()

    assert tracker.provider_attempt_count == 22


def test_budget_tracker_enforces_consecutive_infra_failures():
    limits = BudgetLimits(
        max_total_input_tokens=1000,
        max_total_output_tokens=1000,
        max_total_calls=10,
        max_infra_failures=5,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=600.0,
    )
    tracker = LiveBudgetTracker(limits)
    
    tracker.record_failure(is_infra=True, is_gateway=False)
    assert tracker.total_infra_failures == 1
    assert tracker.consecutive_infra_failures == 1
    
    # Second failure in a row raises BudgetExceededError
    with pytest.raises(BudgetExceededError, match="Consecutive infrastructure failures limit exceeded"):
        tracker.record_failure(is_infra=True, is_gateway=False)

    # State must not be corrupted
    assert tracker.total_infra_failures == 1
    assert tracker.consecutive_infra_failures == 1


def test_budget_limits_validation():
    # Booleans are rejected
    with pytest.raises(ValueError, match="must be a positive integer"):
        BudgetLimits(
            max_total_input_tokens=True, # Invalid
            max_total_output_tokens=50,
            max_total_calls=10,
            max_infra_failures=2,
            max_consecutive_infra_failures=1,
            max_gateway_failures=2,
            max_wall_clock_seconds=600.0,
        )

    # Negative numbers are rejected
    with pytest.raises(ValueError, match="must be a positive integer"):
        BudgetLimits(
            max_total_input_tokens=-100, # Invalid
            max_total_output_tokens=50,
            max_total_calls=10,
            max_infra_failures=2,
            max_consecutive_infra_failures=1,
            max_gateway_failures=2,
            max_wall_clock_seconds=600.0,
        )

    # Floats are rejected for integer fields
    with pytest.raises(ValueError, match="must be a positive integer"):
        BudgetLimits(
            max_total_input_tokens=100.5, # Invalid
            max_total_output_tokens=50,
            max_total_calls=10,
            max_infra_failures=2,
            max_consecutive_infra_failures=1,
            max_gateway_failures=2,
            max_wall_clock_seconds=600.0,
        )


def test_budget_tracker_input_validation():
    limits = BudgetLimits(
        max_total_input_tokens=1000,
        max_total_output_tokens=1000,
        max_total_calls=10,
        max_infra_failures=5,
        max_consecutive_infra_failures=5,
        max_gateway_failures=5,
        max_wall_clock_seconds=600.0,
    )
    tracker = LiveBudgetTracker(limits)

    # Boolean is rejected for token count
    with pytest.raises(ValueError, match="must be a non-negative integer"):
        tracker.record_tokens(True, 10) # Invalid

    # Negative token count is rejected
    with pytest.raises(ValueError, match="must be a non-negative integer"):
        tracker.record_tokens(-5, 10) # Invalid

    # Float token count is rejected
    with pytest.raises(ValueError, match="must be a non-negative integer"):
        tracker.record_tokens(10.5, 10) # Invalid
