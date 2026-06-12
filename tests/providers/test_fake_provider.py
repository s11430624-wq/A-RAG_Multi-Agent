import pytest

from experiments.providers.fake import FakeProvider, ScriptedOutcome, ScriptedProvider
from experiments.providers.models import (
    ModelParameters,
    ModelRequest,
    ProviderCancelledError,
    ProviderTransportError,
    Usage,
)


def _request(call_index: int = 1, cancellation=None) -> ModelRequest:
    return ModelRequest(
        call_index=call_index,
        request_id=f"client-{call_index}",
        system_prompt="",
        user_prompt="prompt",
        parameters=ModelParameters("model", 0.0, 0.95, 100, 5.0, 42),
        cancellation=cancellation,
    )


def test_fake_provider_is_deterministic_and_records_requests():
    provider = FakeProvider(
        responses=("first", "second"),
        usage=Usage(3, 2, 5, "provider"),
    )

    first = provider.generate(_request(1))
    second = provider.generate(_request(2))

    assert (first.text, second.text) == ("first", "second")
    assert [request.call_index for request in provider.requests] == [1, 2]
    assert first.attempt_records[0].call_index == 1


@pytest.mark.parametrize("reason", ["stop", "length", "content_filter", "tool_request", "unknown"])
def test_scripted_provider_supports_every_finish_reason(reason):
    provider = ScriptedProvider(
        (ScriptedOutcome.response("text", finish_reason=reason),)
    )

    assert provider.generate(_request()).finish_reason == reason


def test_scripted_provider_supports_missing_usage_and_failures():
    provider = ScriptedProvider(
        (
            ScriptedOutcome.response("text", usage=Usage(None, None, None, "missing")),
            ScriptedOutcome.error(ProviderTransportError, "offline"),
        )
    )

    assert provider.generate(_request(1)).usage.source == "missing"
    with pytest.raises(ProviderTransportError) as exc_info:
        provider.generate(_request(2))
    assert exc_info.value.attempt_records[0].call_index == 2


def test_scripted_provider_exhaustion_fails_closed():
    provider = ScriptedProvider(())
    with pytest.raises(ProviderTransportError, match="exhausted"):
        provider.generate(_request())


def test_cancellation_is_delivered_with_audit():
    class Cancelled:
        def is_cancelled(self):
            return True

        def raise_if_cancelled(self):
            raise ProviderCancelledError("cancelled")

    provider = FakeProvider(responses=("unused",))
    with pytest.raises(ProviderCancelledError) as exc_info:
        provider.generate(_request(cancellation=Cancelled()))
    assert exc_info.value.attempt_records[0].outcome == "cancelled"
