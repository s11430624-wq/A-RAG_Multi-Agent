from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from experiments.providers.config import load_provider_config
from experiments.providers.models import (
    ModelParameters,
    ModelRequest,
    ModelResponse,
    ProviderAttemptRecord,
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigError,
    ProviderFailureAuditRecord,
    ProviderTransportError,
    TransportErrorInfo,
    Usage,
)


def test_existing_configs_load_exact_provider_parameters(
    models_config_path: Path,
    experiment_config_path: Path,
):
    config = load_provider_config(models_config_path, experiment_config_path)

    assert config == ProviderConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://127.0.0.1:8787/v1",
        parameters=ModelParameters(
            model="google/gemini-3.5-flash",
            temperature=0.0,
            top_p=0.95,
            max_output_tokens=4096,
            timeout_seconds=120.0,
            seed=42,
        ),
        capabilities=ProviderCapabilities(
            supports_seed=True,
            supports_request_id=True,
            returns_usage=True,
        ),
        max_attempts=3,
        retry_backoff_seconds=(0.25, 0.5),
    )


def test_public_provider_dataclasses_are_frozen_with_exact_fields():
    assert [field.name for field in fields(ModelRequest)] == [
        "call_index",
        "request_id",
        "system_prompt",
        "user_prompt",
        "parameters",
        "cancellation",
    ]
    assert [field.name for field in fields(ModelResponse)][-1] == "attempt_records"
    assert [field.name for field in fields(ProviderFailureAuditRecord)] == [
        "call_index",
        "finish_reason",
        "sanitized_response_sha256",
        "elapsed_seconds",
        "attempt_records",
        "error_type",
    ]
    params = ModelParameters("m", 0.0, 1.0, 1, 1.0, 1)
    with pytest.raises(FrozenInstanceError):
        params.model = "changed"


def test_provider_error_exposes_immutable_audit():
    error_info = TransportErrorInfo("connection", True, None, "reset")
    attempt = ProviderAttemptRecord(3, 1, 0.25, 0.0, "transport_error", error_info)
    error = ProviderTransportError(
        "failed",
        attempt_records=(attempt,),
        elapsed_seconds=0.25,
    )

    assert error.attempt_records == (attempt,)
    assert error.elapsed_seconds == 0.25
    with pytest.raises(AttributeError):
        error.attempt_records = ()
    with pytest.raises(AttributeError):
        error._attempt_records = ()


@pytest.mark.parametrize(
    "models_payload,experiment_payload",
    [
        ("default_provider: missing\ndefault_model: m\nproviders: {}\n", "timeout: {agent_response: 1}\nseed: 1\n"),
        ("default_provider: p\ndefault_model: m\nproviders: {p: {api_base: x, models: []}}\n", "timeout: {agent_response: 1}\nseed: 1\n"),
        ("default_provider: p\ndefault_model: m\napi_key: secret\nproviders: {}\n", "timeout: {agent_response: 1}\nseed: 1\n"),
        ("default_provider: p\ndefault_model: m\nproviders: {p: {api_base: x, models: [{id: m, temperature: true, top_p: 1, max_output_tokens: 1}]}}\n", "timeout: {agent_response: 1}\nseed: 1\n"),
        ("default_provider: p\ndefault_model: m\nproviders: {p: {api_base: x, models: [{id: m, temperature: 0, top_p: 1, max_output_tokens: -1}]}}\n", "timeout: {agent_response: 1}\nseed: 1\n"),
        ("default_provider: p\ndefault_model: m\nproviders: {p: {api_base: x, models: [{id: m, temperature: 0, top_p: 1, max_output_tokens: 1}]}}\n", "timeout: {agent_response: false}\nseed: 1\n"),
    ],
)
def test_invalid_configuration_fails_closed(
    tmp_path: Path,
    models_payload: str,
    experiment_payload: str,
):
    models = tmp_path / "models.yaml"
    experiment = tmp_path / "experiment.yaml"
    models.write_text(models_payload, encoding="utf-8")
    experiment.write_text(experiment_payload, encoding="utf-8")

    with pytest.raises(ProviderConfigError):
        load_provider_config(models, experiment)


def test_usage_rejects_bool_negative_and_inconsistent_totals():
    for values in ((True, 1, 2), (-1, 1, 0), (1, 2, 99)):
        with pytest.raises(ValueError):
            Usage(values[0], values[1], values[2], "provider")
