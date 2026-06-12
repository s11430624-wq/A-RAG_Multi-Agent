from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

FinishReason = Literal["stop", "length", "content_filter", "tool_request", "unknown"]


def _require_number(name: str, value: object, *, minimum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


@dataclass(frozen=True)
class ModelParameters:
    model: str
    temperature: float
    top_p: float
    max_output_tokens: int
    timeout_seconds: float
    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("model must be a non-empty string")
        _require_number("temperature", self.temperature, minimum=0)
        _require_number("top_p", self.top_p, minimum=0)
        if self.top_p > 1:
            raise ValueError("top_p must be at most 1")
        if isinstance(self.max_output_tokens, bool) or not isinstance(self.max_output_tokens, int) or self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        _require_number("timeout_seconds", self.timeout_seconds, minimum=0)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_seed: bool
    supports_request_id: bool
    returns_usage: bool


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    api_base: str
    parameters: ModelParameters
    capabilities: ProviderCapabilities
    max_attempts: int
    retry_backoff_seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.provider_id or not self.api_base:
            raise ValueError("provider_id and api_base are required")
        if self.max_attempts != 3 or self.retry_backoff_seconds != (0.25, 0.5):
            raise ValueError("M5 retry profile must be 3 attempts with 0.25/0.50 backoff")


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    source: Literal["provider", "missing", "provider_normalized"]

    def __post_init__(self) -> None:
        values = (self.input_tokens, self.output_tokens, self.total_tokens)
        for value in values:
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError("token usage must be non-negative integers or None")
        if self.source not in ("provider", "missing", "provider_normalized"):
            raise ValueError("invalid usage source")
        if self.input_tokens is not None and self.output_tokens is not None and self.total_tokens is not None:
            if self.total_tokens != self.input_tokens + self.output_tokens:
                raise ValueError("total_tokens must equal input_tokens + output_tokens")


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...
    def raise_if_cancelled(self) -> None: ...


@dataclass(frozen=True)
class ModelRequest:
    call_index: int
    request_id: str
    system_prompt: str
    user_prompt: str
    parameters: ModelParameters
    cancellation: CancellationToken | None


@dataclass(frozen=True)
class TransportErrorInfo:
    category: Literal["connection", "timeout", "gateway", "authentication", "cancelled"]
    retryable: bool
    status_code: int | None
    error_code: str | None


@dataclass(frozen=True)
class ProviderAttemptRecord:
    call_index: int
    attempt_index: int
    latency_seconds: float
    backoff_seconds_after: float
    outcome: Literal["response", "transport_error", "cancelled"]
    error: TransportErrorInfo | None


@dataclass(frozen=True)
class ProviderFailureAuditRecord:
    call_index: int
    finish_reason: FinishReason | None
    sanitized_response_sha256: str | None
    elapsed_seconds: float
    attempt_records: tuple[ProviderAttemptRecord, ...]
    error_type: str


@dataclass(frozen=True)
class ModelResponse:
    text: str
    finish_reason: FinishReason
    usage: Usage
    provider_request_id: str | None
    model: str
    latency_seconds: float
    retry_count: int
    seed_applied: bool
    sanitized_metadata: tuple[tuple[str, str], ...]
    attempt_records: tuple[ProviderAttemptRecord, ...]


@dataclass(frozen=True)
class TransportRequest:
    method: Literal["POST"]
    url: str
    public_headers: tuple[tuple[str, str], ...]
    json_body: bytes
    timeout_seconds: float
    client_request_id: str


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    body_bytes: bytes
    allowlisted_headers: tuple[tuple[str, str], ...]
    transport_request_id: str | None


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        attempt_records: tuple[ProviderAttemptRecord, ...] = (),
        elapsed_seconds: float = 0.0,
        failure_audit: ProviderFailureAuditRecord | None = None,
    ) -> None:
        super().__init__(message)
        self._attempt_records = tuple(attempt_records)
        self._elapsed_seconds = elapsed_seconds
        self._failure_audit = failure_audit

    def __setattr__(self, name: str, value) -> None:
        if name in {"_attempt_records", "_elapsed_seconds", "_failure_audit"} and hasattr(self, name):
            raise AttributeError(f"{name} is immutable")
        super().__setattr__(name, value)

    @property
    def attempt_records(self) -> tuple[ProviderAttemptRecord, ...]:
        return self._attempt_records

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed_seconds

    @property
    def failure_audit(self) -> ProviderFailureAuditRecord | None:
        return self._failure_audit


class ProviderConfigError(ProviderError):
    pass


class ProviderTransportError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderGatewayError(ProviderError):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderCancelledError(ProviderError):
    pass


class ProviderEmptyResponseError(ProviderError):
    pass


class ProviderMalformedResponseError(ProviderError):
    pass


class ProviderFinishReasonError(ProviderError):
    pass


class ProviderUsageUnavailableError(ProviderError):
    pass


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class Transport(Protocol):
    def send(
        self,
        request: TransportRequest,
        *,
        cancellation: CancellationToken | None,
    ) -> TransportResponse: ...
