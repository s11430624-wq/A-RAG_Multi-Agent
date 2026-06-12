import pytest

from experiments.providers.models import (
    ModelResponse,
    ProviderAttemptRecord,
    ProviderFailureAuditRecord,
    ProviderTransportError,
    ProviderUsageUnavailableError,
    TransportErrorInfo,
    Usage,
)
from experiments.strategies.metrics import StrategyMetricsCollector, project_for_result_schema
from experiments.strategies.models import StrategyFinalization


def _response(call_index, usage, metadata=()):
    attempt = ProviderAttemptRecord(call_index, 1, 0.2, 0.0, "response", None)
    return ModelResponse("ok", "stop", usage, f"p-{call_index}", "m", 0.2, 0, True, metadata, (attempt,))


def test_metrics_aggregate_successful_calls_and_keep_tools_separate():
    collector = StrategyMetricsCollector(retrieval_success=True)
    collector.record_response(
        _response(1, Usage(2, 3, 5, "provider")),
        role="Planner",
        phase="initial",
        template_name="planner.txt",
        template_hash="a",
        rendered_prompt_hash="b",
        response_hash="c",
    )
    collector.record_tool_result(token_count=7)
    metrics = collector.snapshot()

    assert metrics.model_call_count == 1
    assert metrics.tool_calls == 1
    assert metrics.retrieved_tokens == 7
    assert metrics.input_tokens == 2
    assert metrics.output_tokens == 3


def test_missing_usage_propagates_and_projection_fails_closed():
    collector = StrategyMetricsCollector(retrieval_success=None)
    collector.record_response(
        _response(1, Usage(None, None, None, "missing")),
        role="Single",
        phase="initial",
        template_name="single_llm.txt",
        template_hash="a",
        rendered_prompt_hash="b",
        response_hash="c",
    )
    finalization = StrategyFinalization(collector.snapshot(), "run/path", "f" * 64)

    with pytest.raises(ProviderUsageUnavailableError):
        project_for_result_schema(finalization=finalization)


def test_failed_call_adds_attempt_and_failure_audit_without_model_record():
    attempt = ProviderAttemptRecord(
        2,
        1,
        0.4,
        0.0,
        "transport_error",
        TransportErrorInfo("connection", False, None, "reset"),
    )
    audit = ProviderFailureAuditRecord(2, None, None, 0.4, (attempt,), "ProviderTransportError")
    error = ProviderTransportError("failed", attempt_records=(attempt,), elapsed_seconds=0.4, failure_audit=audit)
    collector = StrategyMetricsCollector(retrieval_success=None)

    collector.record_error(error)
    metrics = collector.snapshot()

    assert metrics.model_call_count == 0
    assert metrics.provider_attempt_count == 1
    assert metrics.failed_provider_call_count == 1
    assert metrics.model_latency_seconds == 0.4
    assert metrics.failure_audit_records == (audit,)


def test_projection_uses_complete_usage_and_finalized_artifact_path():
    collector = StrategyMetricsCollector(retrieval_success=None)
    collector.record_response(
        _response(1, Usage(4, 5, 9, "provider")),
        role="Single",
        phase="initial",
        template_name="single_llm.txt",
        template_hash="a",
        rendered_prompt_hash="b",
        response_hash="c",
    )
    projection = project_for_result_schema(
        finalization=StrategyFinalization(collector.snapshot(), "artifacts/run", "f" * 64)
    )
    assert (projection.input_tokens, projection.output_tokens, projection.artifact_path) == (4, 5, "artifacts/run")


def test_empty_retrieval_result_counts_tool_but_not_success():
    collector = StrategyMetricsCollector(retrieval_success=False)
    collector.record_tool_result(token_count=0)
    metrics = collector.snapshot()

    assert metrics.tool_calls == 1
    assert metrics.retrieved_tokens == 0
    assert metrics.retrieval_success is False


# M7-C.2 ModelCallRecord preserves usage audit metadata tests

def test_model_call_record_preserves_usage_audit_metadata():
    audit_meta = (
        ("normalization_rule", "openai_reasoning_accumulation"),
        ("normalized_output_tokens", "94"),
        ("raw_completion_tokens", "1"),
        ("reasoning_tokens", "93"),
        ("usage_source", "provider_normalized"),
    )
    collector = StrategyMetricsCollector(retrieval_success=None)
    collector.record_response(
        _response(1, Usage(8, 94, 102, "provider_normalized"), metadata=audit_meta),
        role="Planner",
        phase="initial",
        template_name="planner.txt",
        template_hash="a",
        rendered_prompt_hash="b",
        response_hash="c",
    )
    metrics = collector.snapshot()
    assert metrics.model_call_count == 1
    
    record = metrics.call_records[0]
    assert record.input_tokens == 8
    assert record.output_tokens == 94
    assert record.audit_metadata == audit_meta
