from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from experiments.evaluation.metrics import EmptyResponseError, RunnerError, TestTimeoutError
from experiments.providers.models import (
    ProviderAuthenticationError,
    ProviderEmptyResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
    ProviderUsageUnavailableError,
)
from experiments.runner.failure import build_result_record, classify_runner_exception
from experiments.runner.orchestrator import merge_evaluator_snapshots, snapshot_from_evaluator_result
from experiments.runtime.patching import InvalidPatchError as RuntimeInvalidPatchError
from experiments.runtime.patching import PatchApplyError
from experiments.strategies.artifacts import ArtifactWriteError
from experiments.strategies.models import StrategyResultProjection
from experiments.strategies.parsers import InvalidPatchError as StrategyInvalidPatchError


@pytest.mark.parametrize(
    ("exc", "error_type", "stop_reason", "infra_error", "valid_run"),
    [
        (ProviderTimeoutError("timeout"), "model_timeout", "infra_error", True, False),
        (ProviderTransportError("gateway"), "gateway_error", "infra_error", True, False),
        (ProviderAuthenticationError("auth"), "gateway_error", "infra_error", True, False),
        (ProviderEmptyResponseError("empty"), "empty_response", "repair_limit", False, True),
        (EmptyResponseError("empty"), "empty_response", "repair_limit", False, True),
        (StrategyInvalidPatchError("invalid"), "invalid_patch", "repair_limit", False, True),
        (RuntimeInvalidPatchError("invalid"), "invalid_patch", "repair_limit", False, True),
        (PatchApplyError("apply"), "patch_apply_error", "repair_limit", False, True),
        (TestTimeoutError("tests"), "test_timeout", "infra_error", True, False),
        (RunnerError("runner"), "runner_error", "infra_error", True, False),
        (ProviderUsageUnavailableError("missing"), "unknown", "infra_error", True, False),
        (ArtifactWriteError("artifact"), "unknown", "infra_error", True, False),
        (RuntimeError("surprise"), "unknown", "infra_error", True, False),
    ],
)
def test_exception_mapping_uses_only_result_schema_enums(exc, error_type, stop_reason, infra_error, valid_run):
    failure = classify_runner_exception(exc)

    assert failure.error_type == error_type
    assert failure.stop_reason == stop_reason
    assert failure.infra_error is infra_error
    assert failure.valid_run is valid_run


def test_build_success_result_uses_real_projected_usage(a_planned_run, result_schema_path):
    merged = merge_evaluator_snapshots(
        pass1=snapshot_from_evaluator_result(
            {
                "pass1_public": True,
                "pass1_hidden": True,
                "pass1_public_tests_passed": 3,
                "pass1_hidden_tests_passed": 2,
                "final_public": True,
                "final_hidden": True,
                "public_tests_passed": 3,
                "public_tests_total": 3,
                "hidden_tests_passed": 2,
                "hidden_tests_total": 2,
                "repair_rounds": 0,
                "patch_apply_failures": 0,
                "test_latency_seconds": 0.5,
            }
        ),
        final_or_latest=None,
    )
    projection = StrategyResultProjection(
        tool_calls=0,
        retrieved_tokens=0,
        retrieval_success=None,
        input_tokens=11,
        output_tokens=7,
        estimated_cost=None,
        model_latency_seconds=0.25,
        artifact_path="artifact/run",
    )

    record = build_result_record(run=a_planned_run, merged=merged, projection=projection, terminal_failure=None)

    assert record["valid_run"] is True
    assert record["input_tokens"] == 11
    assert record["output_tokens"] == 7
    assert record["stop_reason"] == "public_pass"
    _assert_schema_valid(record, result_schema_path)


def test_a_and_c_success_records_have_null_retrieval_fields(a_planned_run, c_planned_run, result_schema_path):
    merged = merge_evaluator_snapshots(pass1=None, final_or_latest=None)
    projection = StrategyResultProjection(
        tool_calls=0,
        retrieved_tokens=0,
        retrieval_success=None,
        input_tokens=1,
        output_tokens=1,
        estimated_cost=None,
        model_latency_seconds=0.1,
        artifact_path="artifact/run",
    )

    for run in (a_planned_run, c_planned_run):
        record = build_result_record(run=run, merged=merged, projection=projection, terminal_failure=None)
        assert record["tool_calls"] == 0
        assert record["retrieved_tokens"] == 0
        assert record["retrieval_success"] is None
        _assert_schema_valid(record, result_schema_path)


def test_e_success_record_uses_operational_retrieval_metrics(e_planned_run, result_schema_path):
    merged = merge_evaluator_snapshots(pass1=None, final_or_latest=None)
    projection = StrategyResultProjection(
        tool_calls=2,
        retrieved_tokens=17,
        retrieval_success=True,
        input_tokens=9,
        output_tokens=4,
        estimated_cost=None,
        model_latency_seconds=0.2,
        artifact_path="artifact/e",
    )

    record = build_result_record(run=e_planned_run, merged=merged, projection=projection, terminal_failure=None)

    assert record["tool_calls"] == 2
    assert record["retrieved_tokens"] == 17
    assert record["retrieval_success"] is True
    _assert_schema_valid(record, result_schema_path)


def test_successful_missing_usage_cannot_export_valid_run_true(a_planned_run, result_schema_path):
    merged = merge_evaluator_snapshots(pass1=None, final_or_latest=None)
    failure = classify_runner_exception(ProviderUsageUnavailableError("complete provider usage is required"))

    record = build_result_record(
        run=a_planned_run,
        merged=merged,
        projection=None,
        terminal_failure=failure,
        finalized_artifact_path="artifact/finalized",
    )

    assert record["valid_run"] is False
    assert record["infra_error"] is True
    assert record["error_type"] == "unknown"
    assert record["stop_reason"] == "infra_error"
    assert record["input_tokens"] == 0
    assert record["output_tokens"] == 0
    assert record["estimated_cost"] is None
    assert record["artifact_path"] == "artifact/finalized"
    _assert_schema_valid(record, result_schema_path)


def test_failure_placeholder_tokens_are_only_used_for_invalid_runs(a_planned_run, result_schema_path):
    merged = merge_evaluator_snapshots(pass1=None, final_or_latest=None)
    failure = classify_runner_exception(RuntimeError("boom"))

    record = build_result_record(run=a_planned_run, merged=merged, projection=None, terminal_failure=failure)

    assert record["valid_run"] is False
    assert record["input_tokens"] == 0
    assert record["output_tokens"] == 0
    _assert_schema_valid(record, result_schema_path)


def _assert_schema_valid(record: dict, schema_path):
    import json

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    assert list(validator.iter_errors(record)) == []
