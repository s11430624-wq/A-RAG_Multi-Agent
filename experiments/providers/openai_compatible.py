from __future__ import annotations

import hashlib
import json
import time
from typing import Callable

from experiments.providers.models import (
    ModelRequest,
    ModelResponse,
    ProviderAttemptRecord,
    ProviderAuthenticationError,
    ProviderCancelledError,
    ProviderConfig,
    ProviderEmptyResponseError,
    ProviderFailureAuditRecord,
    ProviderFinishReasonError,
    ProviderGatewayError,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
    Transport,
    TransportErrorInfo,
    TransportRequest,
    TransportResponse,
    Usage,
)

_RETRYABLE_STATUSES = {429, 502, 503, 504}
_FINISH_REASONS = {"stop", "length", "content_filter", "tool_request", "unknown"}


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Transport,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        epoch_clock: Callable[[], float] = time.time,
        retry_delay_resolver: Callable[[int, object, float], float] | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self._sleeper = sleeper
        self._clock = clock
        self._epoch_clock = epoch_clock
        self.retry_delay_resolver = retry_delay_resolver

    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.system_prompt != "":
            raise ProviderMalformedResponseError("system_prompt must be empty")
        payload = {
            "max_tokens": request.parameters.max_output_tokens,
            "messages": [
                {"content": "", "role": "system"},
                {"content": request.user_prompt, "role": "user"},
            ],
            "model": request.parameters.model,
            "temperature": request.parameters.temperature,
            "top_p": request.parameters.top_p,
        }
        if self.config.capabilities.supports_seed:
            payload["seed"] = request.parameters.seed
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        transport_request = TransportRequest(
            method="POST",
            url=self.config.api_base.rstrip("/") + "/chat/completions",
            public_headers=(("accept", "application/json"), ("content-type", "application/json")),
            json_body=body,
            timeout_seconds=request.parameters.timeout_seconds,
            client_request_id=request.request_id,
        )

        started = self._clock()
        attempts: list[ProviderAttemptRecord] = []
        for attempt_index in range(1, self.config.max_attempts + 1):
            self._check_cancelled(request, attempts, started, attempt_index)
            attempt_started = self._clock()
            try:
                response = self.transport.send(transport_request, cancellation=request.cancellation)
            except TimeoutError as exc:
                retryable = attempt_index < self.config.max_attempts
                backoff = self._retry_backoff(attempt_index) if retryable else 0.0
                attempts.append(_attempt(request.call_index, attempt_index, self._clock() - attempt_started, backoff, "timeout"))
                if not retryable:
                    raise ProviderTimeoutError(
                        "provider transport timed out",
                        attempt_records=tuple(attempts),
                        elapsed_seconds=self._clock() - started,
                    ) from exc
                self._sleep_with_cancellation(request, backoff, attempts, started)
                continue
            except OSError as exc:
                retryable = attempt_index < self.config.max_attempts
                backoff = self._retry_backoff(attempt_index) if retryable else 0.0
                attempts.append(_attempt(request.call_index, attempt_index, self._clock() - attempt_started, backoff, "connection"))
                if not retryable:
                    raise ProviderTransportError(
                        "provider transport failed",
                        attempt_records=tuple(attempts),
                        elapsed_seconds=self._clock() - started,
                    ) from exc
                self._sleep_with_cancellation(request, backoff, attempts, started)
                continue

            self._check_cancelled(request, attempts, started, attempt_index)
            status_error = self._status_error(response)
            if status_error is not None:
                error_type, retryable, category = status_error
                can_retry = retryable and attempt_index < self.config.max_attempts
                if can_retry:
                    if self.retry_delay_resolver is not None:
                        backoff = self.retry_delay_resolver(attempt_index, response, self._epoch_clock())
                    else:
                        backoff = self._retry_backoff(attempt_index)
                else:
                    backoff = 0.0
                attempts.append(
                    ProviderAttemptRecord(
                        request.call_index,
                        attempt_index,
                        self._clock() - attempt_started,
                        backoff,
                        "transport_error",
                        TransportErrorInfo(category, can_retry, response.status_code, f"http_{response.status_code}"),
                    )
                )
                if can_retry:
                    self._sleep_with_cancellation(request, backoff, attempts, started)
                    continue
                exc_inst = error_type(
                    f"provider returned HTTP {response.status_code}",
                    attempt_records=tuple(attempts),
                    elapsed_seconds=self._clock() - started,
                )
                if hasattr(response, "allowlisted_headers"):
                    exc_inst.allowlisted_headers = response.allowlisted_headers
                raise exc_inst

            attempts.append(
                ProviderAttemptRecord(
                    request.call_index,
                    attempt_index,
                    self._clock() - attempt_started,
                    0.0,
                    "response",
                    None,
                )
            )
            try:
                return self._parse_response(request, response, tuple(attempts), self._clock() - started)
            except ProviderEmptyResponseError:
                can_retry = attempt_index < self.config.max_attempts
                if not can_retry:
                    raise
                backoff = self._retry_backoff(attempt_index)
                attempts[-1] = ProviderAttemptRecord(
                    request.call_index,
                    attempt_index,
                    self._clock() - attempt_started,
                    backoff,
                    "response_error",
                    TransportErrorInfo("provider_response", True, response.status_code, "empty_response"),
                )
                self._sleep_with_cancellation(request, backoff, attempts, started)
                continue
            except ProviderMalformedResponseError as exc:
                can_retry = attempt_index < self.config.max_attempts and str(exc) == "provider response is malformed"
                if not can_retry:
                    raise
                backoff = self._retry_backoff(attempt_index)
                attempts[-1] = ProviderAttemptRecord(
                    request.call_index,
                    attempt_index,
                    self._clock() - attempt_started,
                    backoff,
                    "response_error",
                    TransportErrorInfo("provider_response", True, response.status_code, "malformed_response"),
                )
                self._sleep_with_cancellation(request, backoff, attempts, started)
                continue

        raise AssertionError("unreachable")

    def _parse_response(
        self,
        request: ModelRequest,
        response: TransportResponse,
        attempts: tuple[ProviderAttemptRecord, ...],
        elapsed: float,
    ) -> ModelResponse:
        payload_text = response.body_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(payload_text)
            choice = payload["choices"][0]
            text = _extract_choice_text(choice)
            finish_reason = choice.get("finish_reason", "unknown")
            model = payload.get("model", request.parameters.model)
        except Exception as exc:
            malformed = ProviderMalformedResponseError(
                "provider response is malformed",
                attempt_records=attempts,
                elapsed_seconds=elapsed,
            )
            malformed.raw_response = payload_text
            raise malformed from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderEmptyResponseError(
                "provider response content is empty",
                attempt_records=attempts,
                elapsed_seconds=elapsed,
            )
        if finish_reason not in _FINISH_REASONS:
            finish_reason = "unknown"
        if finish_reason != "stop":
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            audit = ProviderFailureAuditRecord(
                request.call_index,
                finish_reason,
                digest,
                elapsed,
                attempts,
                "ProviderFinishReasonError",
            )
            raise ProviderFinishReasonError(
                f"finish_reason is not stop: {finish_reason}",
                attempt_records=attempts,
                elapsed_seconds=elapsed,
                failure_audit=audit,
            )
        try:
            usage, audit_meta = _parse_usage(payload.get("usage"), self.config.provider_id)
        except ProviderMalformedResponseError as exc:
            audit = ProviderFailureAuditRecord(
                request.call_index,
                "stop",
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                elapsed,
                attempts,
                "ProviderMalformedResponseError",
            )
            raise ProviderMalformedResponseError(
                str(exc),
                attempt_records=attempts,
                elapsed_seconds=elapsed,
                failure_audit=audit,
            ) from exc
        metadata = list(
            sorted(
                (key.casefold(), value)
                for key, value in response.allowlisted_headers
                if key.casefold() in {"x-request-id", "request-id"}
            )
        )
        if audit_meta:
            metadata.extend(sorted(audit_meta))
        metadata_tuple = tuple(metadata)
        return ModelResponse(
            text=text,
            finish_reason="stop",
            usage=usage,
            provider_request_id=payload.get("id") or response.transport_request_id,
            model=model,
            latency_seconds=elapsed,
            retry_count=len(attempts) - 1,
            seed_applied=self.config.capabilities.supports_seed,
            sanitized_metadata=metadata_tuple,
            attempt_records=attempts,
        )

    def _status_error(self, response: TransportResponse):
        if response.status_code in (401, 403):
            return ProviderAuthenticationError, False, "authentication"
        if response.status_code >= 400:
            return ProviderGatewayError, response.status_code in _RETRYABLE_STATUSES, "gateway"
        return None

    def _retry_backoff(self, attempt_index: int) -> float:
        return self.config.retry_backoff_seconds[attempt_index - 1]

    def _check_cancelled(self, request, attempts, started, attempt_index) -> None:
        if request.cancellation is None or not request.cancellation.is_cancelled():
            return
        record = ProviderAttemptRecord(
            request.call_index,
            attempt_index,
            0.0,
            0.0,
            "cancelled",
            TransportErrorInfo("cancelled", False, None, "cancelled"),
        )
        records = tuple(attempts) + (record,)
        try:
            request.cancellation.raise_if_cancelled()
        except Exception as exc:
            raise ProviderCancelledError(
                "provider call cancelled",
                attempt_records=records,
                elapsed_seconds=self._clock() - started,
            ) from exc

    def _sleep_with_cancellation(self, request, seconds, attempts, started) -> None:
        self._check_cancelled(request, attempts, started, len(attempts) + 1)
        self._sleeper(seconds)
        self._check_cancelled(request, attempts, started, len(attempts) + 1)


def _extract_choice_text(choice: object) -> str:
    if not isinstance(choice, dict):
        raise TypeError("choice must be an object")

    candidate = None
    message = choice.get("message")
    if isinstance(message, dict):
        candidate = message.get("content")
    if candidate is None and "content" in choice:
        candidate = choice.get("content")
    if candidate is None:
        delta = choice.get("delta")
        if isinstance(delta, dict):
            candidate = delta.get("content")

    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, list):
        text_parts: list[str] = []
        for item in candidate:
            if isinstance(item, str):
                text_parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
                continue
            nested_text = item.get("text")
            if isinstance(nested_text, dict) and isinstance(nested_text.get("value"), str):
                text_parts.append(nested_text["value"])
        return "".join(text_parts)
    raise TypeError("choice content is missing")


def _attempt(call_index: int, attempt_index: int, latency: float, backoff: float, category: str):
    return ProviderAttemptRecord(
        call_index,
        attempt_index,
        latency,
        backoff,
        "transport_error",
        TransportErrorInfo(category, backoff > 0, None, category),
    )


def _parse_usage(value, provider_id: str = "") -> tuple[Usage, tuple[tuple[str, str], ...]]:
    if value is None:
        return Usage(None, None, None, "missing"), ()
    if not isinstance(value, dict):
        raise ProviderMalformedResponseError("usage must be an object")

    prompt_tokens = value.get("prompt_tokens")
    completion_tokens = value.get("completion_tokens")
    total_tokens = value.get("total_tokens")

    # Reasoning token normalization support
    details = value.get("completion_tokens_details")
    reasoning_tokens = None
    if isinstance(details, dict):
        reasoning_tokens = details.get("reasoning_tokens")

    # Validate non-negative inputs
    for name, v in [("prompt_tokens", prompt_tokens), ("completion_tokens", completion_tokens), ("total_tokens", total_tokens)]:
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise ProviderMalformedResponseError(f"{name} must be a non-negative integer")

    if reasoning_tokens is not None:
        if isinstance(reasoning_tokens, bool) or not isinstance(reasoning_tokens, int) or reasoning_tokens < 0:
            raise ProviderMalformedResponseError("reasoning_tokens must be a non-negative integer")

    is_hermes = provider_id == "hermes_vertex_gateway"
    
    if reasoning_tokens is not None and reasoning_tokens > 0:
        if is_hermes:
            # Check physical invariant: total == prompt + completion + reasoning
            if total_tokens is not None and prompt_tokens is not None and completion_tokens is not None:
                if total_tokens == prompt_tokens + completion_tokens + reasoning_tokens:
                    normalized_output = completion_tokens + reasoning_tokens
                    usage = Usage(
                        input_tokens=prompt_tokens,
                        output_tokens=normalized_output,
                        total_tokens=total_tokens,
                        source="provider_normalized"
                    )
                    audit_meta = (
                        ("normalization_rule", "google_vertex_reasoning_accumulation"),
                        ("normalized_output_tokens", str(normalized_output)),
                        ("raw_completion_tokens", str(completion_tokens)),
                        ("reasoning_tokens", str(reasoning_tokens)),
                        ("usage_source", "provider_normalized"),
                    )
                    return usage, audit_meta
                else:
                    # Mismatch of reasoning tokens even with reasoning_tokens present
                    raise ProviderMalformedResponseError(
                        f"mismatch when reasoning_tokens present: total({total_tokens}) != prompt({prompt_tokens}) + completion({completion_tokens}) + reasoning({reasoning_tokens})"
                    )
        else:
            # Non-hermes provider cannot套用 reasoning normalization, must fail closed if input + output != total
            if total_tokens is not None and prompt_tokens is not None and completion_tokens is not None:
                if total_tokens != prompt_tokens + completion_tokens:
                    raise ProviderMalformedResponseError(
                        f"total_tokens must equal input_tokens + output_tokens: total({total_tokens}) != prompt({prompt_tokens}) + completion({completion_tokens})"
                    )

    # Standard OpenAI parsing
    try:
        usage = Usage(
            prompt_tokens,
            completion_tokens,
            total_tokens,
            "provider",
        )
        return usage, ()
    except ValueError as exc:
        raise ProviderMalformedResponseError(f"invalid provider usage: {exc}") from exc
