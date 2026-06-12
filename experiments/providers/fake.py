from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from experiments.providers.models import (
    FinishReason,
    ModelRequest,
    ModelResponse,
    ProviderAttemptRecord,
    ProviderCancelledError,
    ProviderError,
    ProviderTransportError,
    TransportErrorInfo,
    Usage,
)


@dataclass(frozen=True)
class ScriptedOutcome:
    text: str | None
    finish_reason: FinishReason
    usage: Usage
    error_type: Type[ProviderError] | None
    error_message: str | None

    @classmethod
    def response(
        cls,
        text: str,
        *,
        finish_reason: FinishReason = "stop",
        usage: Usage | None = None,
    ) -> "ScriptedOutcome":
        return cls(
            text=text,
            finish_reason=finish_reason,
            usage=usage or Usage(1, 1, 2, "provider"),
            error_type=None,
            error_message=None,
        )

    @classmethod
    def error(
        cls,
        error_type: Type[ProviderError],
        message: str,
    ) -> "ScriptedOutcome":
        return cls(
            text=None,
            finish_reason="unknown",
            usage=Usage(None, None, None, "missing"),
            error_type=error_type,
            error_message=message,
        )


class ScriptedProvider:
    def __init__(self, outcomes: tuple[ScriptedOutcome, ...]) -> None:
        self._outcomes = outcomes
        self._position = 0
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.cancellation is not None and request.cancellation.is_cancelled():
            attempt = ProviderAttemptRecord(
                request.call_index,
                1,
                0.0,
                0.0,
                "cancelled",
                TransportErrorInfo("cancelled", False, None, "cancelled"),
            )
            try:
                request.cancellation.raise_if_cancelled()
            except ProviderCancelledError as exc:
                raise ProviderCancelledError(
                    str(exc),
                    attempt_records=(attempt,),
                    elapsed_seconds=0.0,
                ) from exc

        if self._position >= len(self._outcomes):
            attempt = _error_attempt(request.call_index, "exhausted")
            raise ProviderTransportError(
                "scripted provider exhausted",
                attempt_records=(attempt,),
                elapsed_seconds=0.0,
            )
        outcome = self._outcomes[self._position]
        self._position += 1
        if outcome.error_type is not None:
            attempt = _error_attempt(request.call_index, outcome.error_message or "error")
            raise outcome.error_type(
                outcome.error_message or "scripted error",
                attempt_records=(attempt,),
                elapsed_seconds=0.0,
            )
        attempt = ProviderAttemptRecord(request.call_index, 1, 0.0, 0.0, "response", None)
        return ModelResponse(
            text=outcome.text or "",
            finish_reason=outcome.finish_reason,
            usage=outcome.usage,
            provider_request_id=f"fake-{request.call_index}",
            model=request.parameters.model,
            latency_seconds=0.0,
            retry_count=0,
            seed_applied=True,
            sanitized_metadata=(),
            attempt_records=(attempt,),
        )


class FakeProvider(ScriptedProvider):
    def __init__(
        self,
        *,
        responses: tuple[str, ...],
        usage: Usage | None = None,
    ) -> None:
        super().__init__(
            tuple(
                ScriptedOutcome.response(text, usage=usage or Usage(1, 1, 2, "provider"))
                for text in responses
            )
        )


def _error_attempt(call_index: int, code: str) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        call_index,
        1,
        0.0,
        0.0,
        "transport_error",
        TransportErrorInfo("connection", True, None, code),
    )
