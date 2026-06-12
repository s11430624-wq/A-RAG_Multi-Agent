from __future__ import annotations

import os
import pytest
import urllib.request
import urllib.parse
from pathlib import Path
from experiments.providers.models import TransportRequest, TransportResponse, ProviderCapabilities
from experiments.live.http_transport import OpenAICompatibleHttpTransport, CredentialProvider, LiveCredential
from experiments.live.factory import LiveProviderFactory, ProviderRuntimeConfig, DummyCredentialProvider
from experiments.runner.config import ExperimentConfig, ExperimentPaths
from tests.live.test_http_transport import MockOpenerDirector, MockHttpResponse


class SpyCredentialProvider(CredentialProvider):
    def __init__(self) -> None:
        self.calls = 0

    def load_for_send(self) -> LiveCredential:
        self.calls += 1
        return LiveCredential(authorization_header="Bearer dummy_token")


def test_no_auth_loopback_sends_no_authorization_header():
    provider = SpyCredentialProvider()
    
    headers_captured = {}
    def callback(req: urllib.request.Request):
        for k, v in req.headers.items():
            headers_captured[k] = v
        return MockHttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body_data=b"ok",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/chat/completions",
        public_headers=(("accept", "application/json"),),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    
    resp = transport.send(req)
    assert resp.status_code == 200
    assert "Authorization" not in headers_captured
    assert "authorization" not in headers_captured


def test_no_auth_loopback_does_not_call_credential_provider():
    provider = SpyCredentialProvider()
    
    def callback(req: urllib.request.Request):
        return MockHttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body_data=b"ok",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    
    transport.send(req)
    assert provider.calls == 0


def test_no_auth_loopback_rejects_caller_authorization_header():
    provider = SpyCredentialProvider()
    
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    # 1. Title case
    req_title = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/chat/completions",
        public_headers=(("Authorization", "Bearer fake"),),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Caller-supplied Authorization header is not allowed"):
        transport.send(req_title)
        
    # 2. Lowercase
    req_lower = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/chat/completions",
        public_headers=(("authorization", "Bearer fake"),),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Caller-supplied Authorization header is not allowed"):
        transport.send(req_lower)


def test_no_auth_loopback_accepts_exact_127_0_0_1_8787_only():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    assert transport.no_auth_loopback is True


def test_no_auth_loopback_rejects_localhost():
    provider = SpyCredentialProvider()
    
    # localhost has self.no_auth_loopback = False. If called without approved credential, it must fail closed.
    transport = OpenAICompatibleHttpTransport(
        api_base="http://localhost:8787/v1",
        credential_provider=DummyCredentialProvider(),
    )
    assert transport.no_auth_loopback is False
    
    req = TransportRequest(
        method="POST",
        url="http://localhost:8787/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Credential load failed"):
        transport.send(req)
        
    # Verify that calling factory with localhost api_base fail closes
    repo_root = Path(__file__).parent.parent.parent.resolve()
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    custom_caps = ProviderCapabilities(supports_seed=True, supports_request_id=True, returns_usage=True)
    custom_runtime_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://localhost:8787/v1",
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime override contains unapproved endpoint"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=custom_runtime_config,
        )


def test_no_auth_loopback_rejects_wrong_port_8000():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8000/v1",
        credential_provider=provider,
    )
    assert transport.no_auth_loopback is False
    
    # Verify that calling factory with 127.0.0.1:8000 (wrong port) fail closes
    repo_root = Path(__file__).parent.parent.parent.resolve()
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    custom_caps = ProviderCapabilities(supports_seed=True, supports_request_id=True, returns_usage=True)
    custom_runtime_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://127.0.0.1:8000/v1",
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime override contains unapproved endpoint"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=custom_runtime_config,
        )


def test_no_auth_loopback_rejects_shared_proxy_8788():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8788/v1",
        credential_provider=provider,
    )
    assert transport.no_auth_loopback is False
    
    # Verify that calling factory with 127.0.0.1:8788 (wrong port) fail closes
    repo_root = Path(__file__).parent.parent.parent.resolve()
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    custom_caps = ProviderCapabilities(supports_seed=True, supports_request_id=True, returns_usage=True)
    custom_runtime_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://127.0.0.1:8788/v1",
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime override contains unapproved endpoint"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=custom_runtime_config,
        )


def test_no_auth_loopback_rejects_trycloudflare():
    provider = SpyCredentialProvider()
    # Trycloudflare is a remote host, which raises ValueError on unsupported localhost host under http, or uses https.
    with pytest.raises(ValueError):
        OpenAICompatibleHttpTransport(
            api_base="http://my-subdomain.trycloudflare.com/v1",
            credential_provider=provider,
        )
        
    # Verify that calling factory with trycloudflare/cloudflare api_base fail closes
    repo_root = Path(__file__).parent.parent.parent.resolve()
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    custom_caps = ProviderCapabilities(supports_seed=True, supports_request_id=True, returns_usage=True)
    custom_runtime_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="https://my-subdomain.trycloudflare.com/v1",
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime override contains unapproved endpoint"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=custom_runtime_config,
        )


def test_factory_uses_models_yaml_127_0_0_1_8787(monkeypatch, tmp_path):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    
    # We will let the factory read our actual configs/models.yaml in the repo.
    # To do this, we need a mock config with paths pointing to the repo root.
    repo_root = Path(__file__).parent.parent.parent.resolve()
    
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    provider = LiveProviderFactory.create_provider(
        config,
        model_id="google/gemini-3.5-flash",
        env={"ARAG_RUN_LIVE_GATEWAY": "1"}
    )
    assert provider.config.api_base == "http://127.0.0.1:8787/v1"
    assert provider.transport.no_auth_loopback is True


def test_factory_ignores_hermes_gateway_api_key_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("HERMES_GATEWAY_API_KEY", "toxic_key")
    
    repo_root = Path(__file__).parent.parent.parent.resolve()
    
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=repo_root / "results" / "raw",
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces",
        artifact_root=repo_root / "results" / "raw" / "artifacts",
        retrieval_log_root=repo_root / "results" / "raw" / "retrieval",
    )
    
    config = ExperimentConfig(
        strategies=("A",),
        repetitions=1,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    # Even with HERMES_GATEWAY_API_KEY set, it should build successfully and set no_auth_loopback=True, meaning it ignores the key.
    provider = LiveProviderFactory.create_provider(
        config,
        model_id="google/gemini-3.5-flash",
        env={"ARAG_RUN_LIVE_GATEWAY": "1", "HERMES_GATEWAY_API_KEY": "toxic_key"}
    )
    assert provider.transport.no_auth_loopback is True


def test_security_contract_redacts_service_account_path():
    contract_path = Path(__file__).parent.parent.parent.resolve() / "docs" / "security" / "hermes-gateway-credential-contract.md"
    content = contract_path.read_text(encoding="utf-8")
    
    # 1. Contains redacted path placeholder
    assert "C:\\secrets\\[REDACTED].json" in content or "C:/secrets/[REDACTED].json" in content
    # 2. Must not contain the specific river-formula service account filename
    assert "river-formula" not in content


def test_security_contract_contains_no_secret_values():
    contract_path = Path(__file__).parent.parent.parent.resolve() / "docs" / "security" / "hermes-gateway-credential-contract.md"
    content = contract_path.read_text(encoding="utf-8")
    
    assert "trycloudflare.com" not in content
    assert "SHARE_API_KEY" not in content
    assert "mpCLvGSoTlJY" not in content
    assert "river-formula-495601-i5-1a7c2f8c0c65.json" not in content


def test_no_auth_loopback_rejects_v10_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v10/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Invalid path: must start with /v1 namespace"):
        transport.send(req)


def test_no_auth_loopback_rejects_v1evil_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1evil/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Invalid path: must start with /v1 namespace"):
        transport.send(req)


def test_no_auth_loopback_accepts_exact_v1_path():
    provider = SpyCredentialProvider()
    
    def callback(req: urllib.request.Request):
        return MockHttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body_data=b"ok",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    resp = transport.send(req)
    assert resp.status_code == 200


def test_no_auth_loopback_accepts_v1_child_path():
    provider = SpyCredentialProvider()
    
    def callback(req: urllib.request.Request):
        return MockHttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body_data=b"ok",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    resp = transport.send(req)
    assert resp.status_code == 200


def test_no_auth_loopback_rejects_v1_parent_dotdot_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/../evil",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Path traversal or backslash characters detected"):
        transport.send(req)


def test_no_auth_loopback_rejects_v1_current_dot_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/./chat",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Path traversal or backslash characters detected"):
        transport.send(req)


def test_no_auth_loopback_rejects_encoded_dotdot_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    # 1. Lowercase %2e%2e
    req1 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%2e%2e/evil",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req1)

    # 2. Uppercase %2E%2E
    req2 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%2E%2E/evil",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req2)


def test_no_auth_loopback_rejects_encoded_dot_path():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    # 1. Lowercase %2e
    req1 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%2e/chat",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req1)

    # 2. Uppercase %2E
    req2 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%2E/chat",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req2)


def test_no_auth_loopback_rejects_encoded_slash_confusion():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    # 1. /v1/%2f/evil
    req1 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%2f/evil",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req1)

    # 2. /v1%2fchat
    req2 = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1%2fchat",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req2)


def test_no_auth_loopback_rejects_encoded_backslash_confusion():
    provider = SpyCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://127.0.0.1:8787/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://127.0.0.1:8787/v1/%5c/evil",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    with pytest.raises(ValueError, match="Prohibited path pattern detected"):
        transport.send(req)
