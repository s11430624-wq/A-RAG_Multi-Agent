from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from experiments.providers.models import ModelResponse, Usage, ModelRequest, TransportResponse
from experiments.live.probe import GatewayProbe, run_live_probe_cli

class FakeProvider:
    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.calls = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return self.response


def test_probe_succeeds_under_ideal_conditions():
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    
    # Must run without errors
    probe.run_probe(model="google/gemini-3.5-flash")
    assert provider.calls == 1


def test_probe_fails_on_model_identity_mismatch():
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash-wrong",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    
    with pytest.raises(ValueError, match="Model identity mismatch"):
        probe.run_probe(model="google/gemini-3.5-flash")


def test_probe_fails_on_inconsistent_token_usage():
    # If Usage is missing or some fields are None:
    resp_missing = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=None, output_tokens=None, total_tokens=None, source="missing"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider_missing = FakeProvider(resp_missing)
    probe_missing = GatewayProbe(provider_missing, supports_request_id=True, supports_seed=True)
    with pytest.raises(ValueError, match="Token usage is incomplete or missing"):
        probe_missing.run_probe(model="google/gemini-3.5-flash")


def test_probe_fails_if_request_id_missing_and_supported():
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id=None, # Missing!
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    with pytest.raises(ValueError, match="Request ID is missing"):
        probe.run_probe(model="google/gemini-3.5-flash")


def test_probe_fails_if_seed_not_applied_and_supported():
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=False, # Seed not applied!
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    with pytest.raises(ValueError, match="Seed applied check failed"):
        probe.run_probe(model="google/gemini-3.5-flash")


def test_live_gateway_single_probe_requires_opt_in():
    if os.getenv("ARAG_RUN_LIVE_GATEWAY") != "1" or os.getenv("ARAG_ALLOW_SINGLE_PROBE") != "1":
        pytest.skip("set ARAG_RUN_LIVE_GATEWAY=1 and ARAG_ALLOW_SINGLE_PROBE=1 to run live probe")


def _setup_tmp_env(tmp_path):
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    models_yaml = configs_dir / "models.yaml"
    models_yaml.write_text("""
default_model: "google/gemini-3.5-flash"
default_provider: "hermes_vertex_gateway"
providers:
  hermes_vertex_gateway:
    api_base: "http://127.0.0.1:8787/v1"
    models:
      - id: "google/gemini-3.5-flash"
        temperature: 0.0
        top_p: 0.95
        max_output_tokens: 100
""", encoding="utf-8")
    
    experiment_yaml = configs_dir / "experiment.yaml"
    experiment_yaml.write_text("""
strategies:
  - "A"
repetitions: 1
max_repair_rounds: 1
seed: 42
timeout:
  agent_response: 120
  unit_test: 30
  total_run: 600
model_provider_id: "hermes_vertex_gateway"
paths:
  tasks_definition: "experiments/tasks.json"
  raw_results_dir: "results"
  derived_results_dir: "results/derived"
  reviews_dir: "results/reviews"
  workspace_base_dir: "workspaces"
""", encoding="utf-8")


def test_run_live_probe_cli_accepts_provider_normalized_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SINGLE_PROBE", "1")
    _setup_tmp_env(tmp_path)

    # 1. We mock the real provider with the new normalization-enabled provider
    from experiments.providers.openai_compatible import OpenAICompatibleProvider
    from experiments.providers.models import ProviderConfig, ModelParameters, ProviderCapabilities
    
    # Configure the Provider to use "hermes_vertex_gateway" so it allows reasoning token normalization
    config = ProviderConfig(
        "hermes_vertex_gateway",
        "http://127.0.0.1:8787/v1",
        ModelParameters("google/gemini-3.5-flash", 0.0, 0.95, 100, 30.0, 42),
        ProviderCapabilities(True, True, True),
        3,
        (0.25, 0.5),
    )
    
    mock_transport = MagicMock()
    mock_transport.no_auth_loopback = True
    
    # Let the mock transport return raw Gemini 3.5 response
    response_body = {
        "id": "fV8qauqHLY6R9tMPg-uF4QY",
        "model": "google/gemini-3.5-flash",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "hi",
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 1,
            "total_tokens": 102,
            "completion_tokens_details": {
                "reasoning_tokens": 93
            }
        }
    }
    
    import json
    mock_response = TransportResponse(
        status_code=200,
        body_bytes=json.dumps(response_body).encode("utf-8"),
        allowlisted_headers=(("content-type", "application/json"), ("x-request-id", "fV8qauqHLY6R9tMPg-uF4QY")),
        transport_request_id=None,
    )
    mock_transport.send.return_value = mock_response
    
    # Wrap in spy / mock tracker to assert single generate call
    real_provider = OpenAICompatibleProvider(config, transport=mock_transport)
    generate_spy = MagicMock(wraps=real_provider.generate)
    real_provider.generate = generate_spy
    
    with patch("socket.socket.connect") as mock_connect:
        with patch("experiments.live.factory.LiveProviderFactory.create_provider", return_value=real_provider):
            # Run live-probe helper
            exit_code = run_live_probe_cli(tmp_path)
            
            # 1. Assert exit code == 0 (successfully normalized usage works!)
            assert exit_code == 0
            
            # 2. Check generate was called EXACTLY ONCE
            assert generate_spy.call_count == 1
            
            # 3. Check transport.send was called EXACTLY ONCE
            assert mock_transport.send.call_count == 1
            
            # 4. Check transport boundary was respected
            assert mock_transport.send.called
            
            # 5. Check no authorization leaks in transport request
            sent_req = mock_transport.send.call_args[0][0]
            headers_dict = {k.lower(): v for k, v in sent_req.public_headers}
            assert "authorization" not in headers_dict
            
            # 6. Check that no workspace/smoke results were written
            results_dir = tmp_path / "results"
            assert not results_dir.exists() or len(list(results_dir.iterdir())) == 0


def test_run_live_probe_cli_rejects_normalized_usage_missing_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SINGLE_PROBE", "1")
    _setup_tmp_env(tmp_path)

    from experiments.providers.openai_compatible import OpenAICompatibleProvider
    from experiments.providers.models import ProviderConfig, ModelParameters, ProviderCapabilities
    
    config = ProviderConfig(
        "hermes_vertex_gateway",
        "http://127.0.0.1:8787/v1",
        ModelParameters("google/gemini-3.5-flash", 0.0, 0.95, 100, 30.0, 42),
        ProviderCapabilities(True, True, True),
        3,
        (0.25, 0.5),
    )
    
    mock_transport = MagicMock()
    mock_transport.no_auth_loopback = True
    
    # Raw usage structure but without completion_tokens_details -> standard parsing -> mismatched 8+1 != 102
    response_body = {
        "id": "fV8qauqHLY6R9tMPg-uF4QY",
        "model": "google/gemini-3.5-flash",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "hi",
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 1,
            "total_tokens": 102,
        }
    }
    
    import json
    mock_response = TransportResponse(
        status_code=200,
        body_bytes=json.dumps(response_body).encode("utf-8"),
        allowlisted_headers=(("content-type", "application/json"), ("x-request-id", "fV8qauqHLY6R9tMPg-uF4QY")),
        transport_request_id=None,
    )
    mock_transport.send.return_value = mock_response
    
    real_provider = OpenAICompatibleProvider(config, transport=mock_transport)
    
    with patch("socket.socket.connect") as mock_connect:
        with patch("experiments.live.factory.LiveProviderFactory.create_provider", return_value=real_provider):
            exit_code = run_live_probe_cli(tmp_path)
            
            # Since standard parsing fails on total != input + output, it raises ValueError, and exit_code should be 2
            assert exit_code == 2


def test_gateway_probe_validate_response_does_not_call_provider():
    # Construct a FakeProvider with 0 calls initially
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    
    # Executing validate_response must not trigger generate/network call at all
    probe.validate_response(resp, "google/gemini-3.5-flash")
    assert provider.calls == 0


def test_gateway_probe_run_probe_returns_response():
    resp = ModelResponse(
        text="hello",
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15, source="provider"),
        provider_request_id="req-123",
        model="google/gemini-3.5-flash",
        latency_seconds=1.2,
        retry_count=0,
        seed_applied=True,
        sanitized_metadata=(),
        attempt_records=(),
    )
    provider = FakeProvider(resp)
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    
    # Executing run_probe must validate and return the ModelResponse object
    ret_resp = probe.run_probe("google/gemini-3.5-flash")
    assert ret_resp is resp
    assert provider.calls == 1
