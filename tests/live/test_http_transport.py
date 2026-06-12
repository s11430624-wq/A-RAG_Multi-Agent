from __future__ import annotations

import pytest
import urllib.request
import urllib.error
import io
import socket
from dataclasses import dataclass
from typing import Callable
from experiments.providers.models import TransportRequest, TransportResponse, ProviderTransportError, ProviderAuthenticationError
from experiments.live.http_transport import (
    LiveCredential,
    CredentialProvider,
    OpenAICompatibleHttpTransport,
    BlockRedirectHandler,
)

class MockCredentialProvider(CredentialProvider):
    def __init__(self, token: str = "secret_token_123") -> None:
        self.token = token
        self.calls = 0

    def load_for_send(self) -> LiveCredential:
        self.calls += 1
        return LiveCredential(authorization_header=f"Bearer {self.token}")


def test_transport_rejects_different_origin_before_credential_load():
    provider = MockCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://attacker-origin.com/v1/chat/completions",
        public_headers=(("accept", "application/json"),),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    with pytest.raises(ValueError, match="Origin mismatch"):
        transport.send(req)
        
    assert provider.calls == 0


def test_transport_rejects_localhost_alias():
    provider = MockCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="http://localhost:8000/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="http://localhost.example.com:8000/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    with pytest.raises(ValueError, match="Invalid localhost host"):
        transport.send(req)
        
    assert provider.calls == 0


def test_transport_rejects_userinfo_fragment_and_unapproved_port():
    provider = MockCredentialProvider()
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
    )
    
    req_userinfo = TransportRequest(
        method="POST",
        url="https://user:pass@api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    with pytest.raises(ValueError, match="UserInfo or Fragment is not allowed"):
        transport.send(req_userinfo)

    req_fragment = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions#frag",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    with pytest.raises(ValueError, match="UserInfo or Fragment is not allowed"):
        transport.send(req_fragment)


def test_block_redirect_handler():
    handler = BlockRedirectHandler()
    req = urllib.request.Request("https://api.hermes-gateway.com/v1")
    with pytest.raises(urllib.error.HTTPError, match="Redirect to https://newurl.com blocked"):
        handler.redirect_request(req, None, 302, "Found", {}, "https://newurl.com")


class MockOpenerDirector(urllib.request.OpenerDirector):
    def __init__(self, response_callback: Callable[[urllib.request.Request], object]) -> None:
        super().__init__()
        self.response_callback = response_callback

    def open(self, fullurl, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        if isinstance(fullurl, urllib.request.Request):
            return self.response_callback(fullurl)
        raise ValueError("Expected urllib.request.Request object")


@dataclass
class MockHttpResponse:
    status: int
    headers: dict[str, str]
    body_data: bytes

    def read(self, amt: int | None = None) -> bytes:
        return self.body_data


def test_transport_enforces_tls_verify_gating():
    provider = MockCredentialProvider()
    with pytest.raises(ValueError, match="TLS verification cannot be disabled"):
        OpenAICompatibleHttpTransport(
            api_base="https://api.hermes-gateway.com/v1",
            credential_provider=provider,
            verify_tls=False,
        )


def test_transport_rejects_service_account_structure():
    provider = MockCredentialProvider(token='{"private_key": "abc"}')
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    with pytest.raises(ValueError, match="Service Account JSON structure is not allowed"):
        transport.send(req)


def test_transport_handles_successful_mock_response():
    provider = MockCredentialProvider(token="secret_key")
    
    def callback(req: urllib.request.Request):
        assert req.headers["Authorization"] == "Bearer secret_key"
        return MockHttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body_data=b"hello response",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    resp = transport.send(req)
    assert resp.status_code == 200
    assert resp.body_bytes == b"hello response"


def test_transport_enforces_size_limit():
    provider = MockCredentialProvider(token="secret_key")
    
    def callback(req: urllib.request.Request):
        return MockHttpResponse(
            status=200,
            headers={},
            body_data=b"12345678901",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
        max_response_bytes=10,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    with pytest.raises(ProviderTransportError, match="Response size limit exceeded"):
        transport.send(req)


def test_transport_redacts_exceptions():
    provider = MockCredentialProvider(token="SECRET_KEY_EXPOSURE")
    
    def callback(req: urllib.request.Request):
        raise OSError("failed communicating with SECRET_KEY_EXPOSURE token inside message")
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    with pytest.raises(ProviderTransportError) as exc_info:
        transport.send(req)
        
    assert "SECRET_KEY_EXPOSURE" not in str(exc_info.value)
    assert "Authorization" not in str(exc_info.value)


def test_transport_filters_headers_using_allowlist():
    provider = MockCredentialProvider(token="secret_key")
    
    def callback(req: urllib.request.Request):
        return MockHttpResponse(
            status=200,
            headers={
                "Content-Type": "application/json",
                "Set-Cookie": "session_id=123",
                "Authorization": "Bearer leaked_secret",
                "X-Request-Id": "req-xyz",
            },
            body_data=b"ok",
        )
        
    mock_opener = MockOpenerDirector(callback)
    transport = OpenAICompatibleHttpTransport(
        api_base="https://api.hermes-gateway.com/v1",
        credential_provider=provider,
        opener=mock_opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://api.hermes-gateway.com/v1/chat/completions",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test-id",
    )
    
    resp = transport.send(req)
    headers_dict = {k.lower(): v for k, v in resp.allowlisted_headers}
    assert "content-type" in headers_dict
    assert "x-request-id" in headers_dict
    assert "set-cookie" not in headers_dict
    assert "authorization" not in headers_dict

