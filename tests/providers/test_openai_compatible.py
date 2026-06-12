import json
import pytest

from experiments.providers.models import (
    ModelParameters,
    ModelRequest,
    ProviderAuthenticationError,
    ProviderCancelledError,
    ProviderCapabilities,
    ProviderConfig,
    ProviderFinishReasonError,
    ProviderGatewayError,
    ProviderMalformedResponseError,
    ProviderTransportError,
    TransportResponse,
    Usage,
)
from experiments.providers.openai_compatible import OpenAICompatibleProvider, _parse_usage


class ScriptedTransport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def send(self, request, *, cancellation):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _config(seed=True, provider_id="p"):
    return ProviderConfig(
        provider_id,
        "http://gateway/v1",
        ModelParameters("model", 0.0, 0.95, 128, 9.0, 42),
        ProviderCapabilities(seed, True, True),
        3,
        (0.25, 0.5),
    )


def _request(call_index=1):
    return ModelRequest(call_index, "client-id", "", "EXACT USER", _config().parameters, None)


def _response(*, status=200, finish_reason="stop", usage=None):
    body = {
        "id": "provider-id",
        "model": "model",
        "choices": [{"message": {"content": "answer"}, "finish_reason": finish_reason}],
    }
    if usage is not None:
        body["usage"] = usage
    return TransportResponse(
        status,
        json.dumps(body).encode("utf-8"),
        (("x-request-id", "transport-id"), ("authorization", "must-drop")),
        "transport-id",
    )


def test_adapter_sends_exact_canonical_payload_without_prompt_wrappers():
    transport = ScriptedTransport([_response(usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5})])
    provider = OpenAICompatibleProvider(_config(), transport=transport)

    response = provider.generate(_request())
    sent = transport.requests[0]
    payload = json.loads(sent.json_body)

    assert payload["messages"] == [
        {"role": "system", "content": ""},
        {"role": "user", "content": "EXACT USER"},
    ]
    assert sent.json_body == json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert dict(sent.public_headers) == {"accept": "application/json", "content-type": "application/json"}
    assert response.usage.total_tokens == 5
    assert response.sanitized_metadata == (("x-request-id", "transport-id"),)


def test_retryable_transport_failures_use_fixed_backoff_and_one_call_index():
    transport = ScriptedTransport([OSError("reset"), _response(status=503), _response(usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})])
    sleeps = []
    provider = OpenAICompatibleProvider(_config(), transport=transport, sleeper=sleeps.append)

    response = provider.generate(_request(call_index=7))

    assert sleeps == [0.25, 0.5]
    assert response.retry_count == 2
    assert [record.call_index for record in response.attempt_records] == [7, 7, 7]
    assert [record.attempt_index for record in response.attempt_records] == [1, 2, 3]


@pytest.mark.parametrize("status,error", [(401, ProviderAuthenticationError), (403, ProviderAuthenticationError), (400, ProviderGatewayError)])
def test_non_retryable_status_fails_with_atomic_audit(status, error):
    transport = ScriptedTransport([_response(status=status)])
    provider = OpenAICompatibleProvider(_config(), transport=transport)
    with pytest.raises(error) as exc_info:
        provider.generate(_request(call_index=4))
    assert len(transport.requests) == 1
    assert exc_info.value.attempt_records[0].call_index == 4


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_request", "unknown"])
def test_non_stop_finish_reason_fails_without_retry_and_preserves_hash(reason):
    transport = ScriptedTransport([_response(finish_reason=reason, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})])
    provider = OpenAICompatibleProvider(_config(), transport=transport)

    with pytest.raises(ProviderFinishReasonError) as exc_info:
        provider.generate(_request())
    assert len(transport.requests) == 1
    assert exc_info.value.failure_audit.finish_reason == reason
    assert exc_info.value.failure_audit.sanitized_response_sha256


def test_missing_usage_remains_missing_and_seed_can_be_omitted():
    transport = ScriptedTransport([_response()])
    provider = OpenAICompatibleProvider(_config(seed=False), transport=transport)

    response = provider.generate(_request())

    assert response.usage.input_tokens is None
    assert response.seed_applied is False
    assert "seed" not in json.loads(transport.requests[0].json_body)


def test_terminal_transport_failure_has_no_mutable_last_call_side_channel():
    transport = ScriptedTransport([OSError("a"), OSError("b"), OSError("c")])
    provider = OpenAICompatibleProvider(_config(), transport=transport, sleeper=lambda _: None)

    with pytest.raises(ProviderTransportError) as exc_info:
        provider.generate(_request(call_index=9))
    assert len(exc_info.value.attempt_records) == 3
    assert not hasattr(provider, "last_attempt_records")


def test_invalid_usage_preserves_attempt_audit():
    transport = ScriptedTransport(
        [_response(usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 99})]
    )
    provider = OpenAICompatibleProvider(_config(), transport=transport)

    with pytest.raises(ProviderMalformedResponseError) as exc_info:
        provider.generate(_request(call_index=6))
    assert exc_info.value.attempt_records[0].call_index == 6
    assert exc_info.value.elapsed_seconds >= 0


def test_malformed_response_retries_and_can_recover():
    malformed = TransportResponse(
        200,
        json.dumps(
            {
                "id": "provider-id",
                "model": "model",
                "choices": [{"finish_reason": "length"}],
            }
        ).encode("utf-8"),
        (),
        "transport-id",
    )
    transport = ScriptedTransport(
        [
            malformed,
            _response(usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}),
        ]
    )
    sleeps = []
    provider = OpenAICompatibleProvider(_config(), transport=transport, sleeper=sleeps.append)

    response = provider.generate(_request(call_index=11))

    assert response.text == "answer"
    assert response.retry_count == 1
    assert len(response.attempt_records) == 2
    assert response.attempt_records[0].outcome == "response_error"
    assert response.attempt_records[0].error.error_code == "malformed_response"
    assert sleeps == [0.25]


def test_provider_accepts_top_level_choice_content():
    body = {
        "id": "provider-id",
        "model": "model",
        "choices": [{"content": "answer", "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    transport = ScriptedTransport(
        [TransportResponse(200, json.dumps(body).encode("utf-8"), (), "transport-id")]
    )
    provider = OpenAICompatibleProvider(_config(), transport=transport)

    response = provider.generate(_request())

    assert response.text == "answer"


def test_provider_accepts_text_part_content_lists():
    body = {
        "id": "provider-id",
        "model": "model",
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "text", "text": " world"},
                    ]
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    transport = ScriptedTransport(
        [TransportResponse(200, json.dumps(body).encode("utf-8"), (), "transport-id")]
    )
    provider = OpenAICompatibleProvider(_config(), transport=transport)

    response = provider.generate(_request())

    assert response.text == "hello world"


def test_429_backoff_sleep_does_not_trigger_per_request_timeout():
    transport = ScriptedTransport(
        [
            _response(status=429),
            _response(status=429),
            _response(usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}),
        ]
    )
    sleeps = []
    provider = OpenAICompatibleProvider(
        _config(),
        transport=transport,
        sleeper=sleeps.append,
        retry_delay_resolver=lambda attempt, response, now: 30.0 if attempt == 1 else 60.0,
    )

    response = provider.generate(_request())

    assert response.text == "answer"
    assert response.retry_count == 2
    assert sleeps == [30.0, 60.0]


def test_malformed_response_preserves_raw_payload_for_diagnostics():
    malformed_body = {"id": "provider-id", "model": "model", "choices": [{"finish_reason": "stop"}]}
    transport = ScriptedTransport(
        [
            TransportResponse(200, json.dumps(malformed_body).encode("utf-8"), (), "transport-id"),
            TransportResponse(200, json.dumps(malformed_body).encode("utf-8"), (), "transport-id"),
            TransportResponse(200, json.dumps(malformed_body).encode("utf-8"), (), "transport-id"),
        ]
    )
    provider = OpenAICompatibleProvider(_config(), transport=transport, sleeper=lambda _: None)

    with pytest.raises(ProviderMalformedResponseError) as exc_info:
        provider.generate(_request())

    assert getattr(exc_info.value, "raw_response", None) == json.dumps(malformed_body)


def test_cancellation_after_transport_return_is_checked():
    class CancelAfterSend:
        checks = 0

        def is_cancelled(self):
            self.checks += 1
            return self.checks >= 2

        def raise_if_cancelled(self):
            raise ProviderCancelledError("cancelled")

    transport = ScriptedTransport([_response(usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})])
    provider = OpenAICompatibleProvider(_config(), transport=transport)
    request = ModelRequest(8, "id", "", "prompt", _config().parameters, CancelAfterSend())

    with pytest.raises(ProviderCancelledError) as exc_info:
        provider.generate(request)
    assert exc_info.value.attempt_records[-1].call_index == 8


# M7-C.2 Specialized TDD Reasoning Token Normalization Tests

def test_provider_parses_reasoning_tokens_into_normalized_output_tokens():
    raw_usage = {
        "prompt_tokens": 8,
        "completion_tokens": 1,
        "total_tokens": 102,
        "completion_tokens_details": {
            "reasoning_tokens": 93
        }
    }
    
    # 1. Direct parser check on hermes_vertex_gateway
    usage, meta = _parse_usage(raw_usage, "hermes_vertex_gateway")
    assert usage.input_tokens == 8
    assert usage.output_tokens == 94
    assert usage.total_tokens == 102
    assert usage.source == "provider_normalized"
    
    meta_dict = dict(meta)
    assert meta_dict["normalization_rule"] == "google_vertex_reasoning_accumulation"
    assert meta_dict["raw_completion_tokens"] == "1"
    assert meta_dict["reasoning_tokens"] == "93"
    assert meta_dict["normalized_output_tokens"] == "94"
    assert meta_dict["usage_source"] == "provider_normalized"


def test_provider_rejects_malformed_reasoning_tokens():
    raw_usage = {
        "prompt_tokens": 8,
        "completion_tokens": 1,
        "total_tokens": 102,
        "completion_tokens_details": {
            "reasoning_tokens": "not_an_int"
        }
    }
    with pytest.raises(ProviderMalformedResponseError, match="reasoning_tokens must be a non-negative integer"):
        _parse_usage(raw_usage, "hermes_vertex_gateway")


def test_provider_rejects_negative_reasoning_tokens():
    raw_usage = {
        "prompt_tokens": 8,
        "completion_tokens": 1,
        "total_tokens": 102,
        "completion_tokens_details": {
            "reasoning_tokens": -5
        }
    }
    with pytest.raises(ProviderMalformedResponseError, match="reasoning_tokens must be a non-negative integer"):
        _parse_usage(raw_usage, "hermes_vertex_gateway")


def test_provider_rejects_mismatch_when_reasoning_tokens_absent():
    raw_usage = {
        "prompt_tokens": 8,
        "completion_tokens": 1,
        "total_tokens": 102,  # mismatched because 8+1 != 102 and reasoning is absent
    }
    # For a non-hermes provider, or even hermes when reasoning is absent, mismatch raises:
    with pytest.raises(ProviderMalformedResponseError, match="total_tokens must equal input_tokens \\+ output_tokens"):
        _parse_usage(raw_usage, "hermes_vertex_gateway")


def test_provider_does_not_normalize_non_hermes_provider():
    raw_usage = {
        "prompt_tokens": 8,
        "completion_tokens": 1,
        "total_tokens": 102,
        "completion_tokens_details": {
            "reasoning_tokens": 93
        }
    }
    # Non-hermes provider, e.g. "openai"
    with pytest.raises(ProviderMalformedResponseError, match="total_tokens must equal input_tokens \\+ output_tokens"):
        _parse_usage(raw_usage, "openai")


def test_no_tokenizer_module_is_imported_or_used():
    # Make sure we never import tiktoken or sentencepiece in openai_compatible or models
    import sys
    assert "tiktoken" not in sys.modules
    assert "sentencepiece" not in sys.modules
