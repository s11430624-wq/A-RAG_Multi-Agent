from __future__ import annotations

from experiments.providers.models import (
    ModelResponse,
    ProviderError,
    ProviderFailureAuditRecord,
    ProviderUsageUnavailableError,
)
from experiments.strategies.models import (
    ModelCallRecord,
    StrategyFinalization,
    StrategyMetrics,
    StrategyResultProjection,
)


class StrategyMetricsCollector:
    def __init__(self, *, retrieval_success: bool | None) -> None:
        self._retrieval_success = retrieval_success
        self._call_records: list[ModelCallRecord] = []
        self._attempt_records = []
        self._failure_audits: list[ProviderFailureAuditRecord] = []
        self._failed_calls = 0
        self._tool_calls = 0
        self._retrieved_tokens = 0
        self._failed_latency = 0.0

    def record_response(
        self,
        response: ModelResponse,
        *,
        role: str,
        phase: str,
        template_name: str,
        template_hash: str,
        rendered_prompt_hash: str,
        response_hash: str,
    ) -> None:
        self._attempt_records.extend(response.attempt_records)
        
        # Pull audit metadata from response.sanitized_metadata if present
        audit_meta = []
        for k, v in response.sanitized_metadata:
            if k in {"normalization_rule", "normalized_output_tokens", "raw_completion_tokens", "reasoning_tokens", "usage_source"}:
                audit_meta.append((k, v))
                
        self._call_records.append(
            ModelCallRecord(
                call_index=response.attempt_records[0].call_index,
                role=role,
                phase=phase,
                template_name=template_name,
                template_hash=template_hash,
                rendered_prompt_hash=rendered_prompt_hash,
                response_hash=response_hash,
                provider_request_id=response.provider_request_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model_latency_seconds=response.latency_seconds,
                retry_count=response.retry_count,
                finish_reason="stop",
                seed_applied=response.seed_applied,
                audit_metadata=tuple(sorted(audit_meta)),
            )
        )

    def record_error(self, error: ProviderError) -> None:
        self._attempt_records.extend(error.attempt_records)
        self._failed_calls += 1
        self._failed_latency += error.elapsed_seconds
        if error.failure_audit is not None:
            self._failure_audits.append(error.failure_audit)

    def record_tool_result(self, *, token_count: int) -> None:
        self._tool_calls += 1
        self._retrieved_tokens += token_count
        if token_count > 0:
            self._retrieval_success = True

    def snapshot(self) -> StrategyMetrics:
        complete = bool(self._call_records) and all(
            record.input_tokens is not None and record.output_tokens is not None
            for record in self._call_records
        )
        input_tokens = sum(record.input_tokens or 0 for record in self._call_records) if complete else None
        output_tokens = sum(record.output_tokens or 0 for record in self._call_records) if complete else None
        latency = self._failed_latency + sum(record.model_latency_seconds for record in self._call_records)
        return StrategyMetrics(
            model_call_count=len(self._call_records),
            provider_attempt_count=len(self._attempt_records),
            failed_provider_call_count=self._failed_calls,
            tool_calls=self._tool_calls,
            retrieved_tokens=self._retrieved_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=None,
            model_latency_seconds=latency,
            retrieval_success=self._retrieval_success,
            call_records=tuple(self._call_records),
            attempt_records=tuple(self._attempt_records),
            failure_audit_records=tuple(self._failure_audits),
        )


def project_for_result_schema(*, finalization: StrategyFinalization) -> StrategyResultProjection:
    metrics = finalization.metrics
    if metrics.input_tokens is None or metrics.output_tokens is None:
        raise ProviderUsageUnavailableError("complete provider usage is required for result projection")
    return StrategyResultProjection(
        tool_calls=metrics.tool_calls,
        retrieved_tokens=metrics.retrieved_tokens,
        retrieval_success=metrics.retrieval_success,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        estimated_cost=metrics.estimated_cost,
        model_latency_seconds=metrics.model_latency_seconds,
        artifact_path=finalization.artifact_path,
    )
