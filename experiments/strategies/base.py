from __future__ import annotations

import hashlib
from typing import Any, Callable

from experiments.providers.models import (
    ModelParameters,
    ModelProvider,
    ModelRequest,
    ProviderError,
    ProviderFailureAuditRecord,
    ProviderFinishReasonError,
)
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.metrics import StrategyMetricsCollector
from experiments.strategies.models import (
    CapabilityContext,
    ModelVisibleTask,
    StrategyFinalization,
    StrategyMetrics,
)
from experiments.strategies.parsers import (
    PatchResponseParser,
    ResponseEnvelopeClassifier,
    StrategyResponseError,
)
from experiments.strategies.prompt_loader import PromptLoader


class StrategySessionError(RuntimeError):
    pass


class StrategySessionClosedError(StrategySessionError):
    pass


class StrategySessionSealedError(StrategySessionError):
    pass


class StrategyFinalizationError(StrategySessionError):
    pass


class BaseStrategySession:
    def __init__(
        self,
        *,
        run_id: str,
        task: ModelVisibleTask,
        provider: ModelProvider,
        parameters: ModelParameters,
        artifact_writer: ArtifactBundleWriter,
        retrieval_success: bool | None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        if not isinstance(task, ModelVisibleTask):
            raise TypeError("task must be ModelVisibleTask")
        self.run_id = run_id
        self.task = task
        self.provider = provider
        self.parameters = parameters
        self.artifact_writer = artifact_writer
        self.prompt_loader = prompt_loader or PromptLoader()
        self.metrics_collector = StrategyMetricsCollector(retrieval_success=retrieval_success)
        self._call_index = 0
        self._initial_generated = False
        self._repair_count = 0
        self._closed = False
        self._sealed = False
        self._active_turn = False

    def _assert_callable(self) -> None:
        if self._sealed:
            raise StrategySessionSealedError("strategy session is sealed")
        if self._closed:
            raise StrategySessionClosedError("strategy session is closed")

    def _invoke_patch(
        self,
        *,
        template_name: str,
        role: str,
        phase: str,
        data: dict[str, Any],
        retrieval_enabled: bool = False,
        evidence: tuple[Any, ...] | None = None,
    ) -> tuple[str, StrategyMetrics]:
        patch, response_text, metrics = self._invoke_role(
            template_name=template_name,
            role=role,
            phase=phase,
            data=data,
            parser=PatchResponseParser.parse,
            retrieval_enabled=retrieval_enabled,
            evidence=evidence,
        )
        patch_name = "initial.diff" if phase == "initial" else f"{phase}.diff"
        self.artifact_writer.stage_bytes(f"patches/{patch_name}", response_text.encode("utf-8"))
        return patch, metrics

    def _invoke_role(
        self,
        *,
        template_name: str,
        role: str,
        phase: str,
        data: dict[str, Any],
        parser: Callable[[str], Any],
        retrieval_enabled: bool = False,
        evidence: tuple[Any, ...] | None = None,
    ) -> tuple[Any, str, StrategyMetrics]:
        self._assert_callable()
        rendered = self.prompt_loader.render(
            template_name,
            task=self.task,
            capability=CapabilityContext(retrieval_enabled),
            data=data,
            evidence=evidence,
        )
        self._call_index += 1
        request = ModelRequest(
            call_index=self._call_index,
            request_id=f"{self.run_id}-{self._call_index:04d}",
            system_prompt="",
            user_prompt=rendered.user_prompt,
            parameters=self.parameters,
            cancellation=None,
        )
        self._active_turn = True
        try:
            response = self.provider.generate(request)
            self._ensure_stop(response)
            classification = ResponseEnvelopeClassifier.classify(
                expected_role=role,
                response_text=response.text,
                finish_reason=response.finish_reason,
            )
            if classification.kind != "final_output":
                exc = StrategyResponseError(f"{role} did not return final output")
                exc.raw_response = response.text
                exc.role = role
                raise exc
            try:
                parsed = parser(response.text)
            except Exception as parser_exc:
                if not hasattr(parser_exc, "raw_response"):
                    setattr(parser_exc, "raw_response", response.text)
                if not hasattr(parser_exc, "role"):
                    setattr(parser_exc, "role", role)
                raise parser_exc
            response_hash = hashlib.sha256(response.text.encode("utf-8")).hexdigest()
            self.metrics_collector.record_response(
                response,
                role=role,
                phase=phase,
                template_name=template_name,
                template_hash=rendered.template_hash,
                rendered_prompt_hash=rendered.rendered_prompt_hash,
                response_hash=response_hash,
            )
            prefix = f"{self._call_index:04d}_{role.casefold()}"
            self.artifact_writer.stage_bytes(f"prompts/{prefix}.txt", rendered.user_prompt.encode("utf-8"))
            self.artifact_writer.stage_bytes(f"responses/{prefix}.txt", response.text.encode("utf-8"))
            return parsed, response.text, self.metrics_collector.snapshot()
        except ProviderError as exc:
            if not hasattr(exc, "role"):
                setattr(exc, "role", role)
            self.metrics_collector.record_error(exc)
            self._terminal_close()
            raise
        except Exception:
            self._terminal_close()
            raise
        finally:
            self._active_turn = False

    def finalize(self) -> StrategyFinalization:
        self._assert_callable()
        if self._active_turn:
            raise StrategyFinalizationError("cannot finalize during an active role turn")
        if not self._initial_generated:
            raise StrategyFinalizationError("cannot finalize before initial patch")
        try:
            finalization = self.artifact_writer.finalize(self.metrics_collector.snapshot())
        except Exception:
            self._terminal_close()
            raise
        self._sealed = True
        return finalization

    def close(self) -> None:
        if self._closed:
            return
        self.artifact_writer.close()
        self._closed = True

    def _terminal_close(self) -> None:
        try:
            self.artifact_writer.close()
        finally:
            self._closed = True

    def _ensure_stop(self, response) -> None:
        if response.finish_reason == "stop":
            return
        audit = ProviderFailureAuditRecord(
            call_index=response.attempt_records[0].call_index,
            finish_reason=response.finish_reason,
            sanitized_response_sha256=hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
            elapsed_seconds=response.latency_seconds,
            attempt_records=response.attempt_records,
            error_type="ProviderFinishReasonError",
        )
        raise ProviderFinishReasonError(
            f"finish_reason is not stop: {response.finish_reason}",
            attempt_records=response.attempt_records,
            elapsed_seconds=response.latency_seconds,
            failure_audit=audit,
        )
