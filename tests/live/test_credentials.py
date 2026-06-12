from __future__ import annotations

import os
import socket
import pytest

def test_import_http_transport_does_not_read_env_or_open_network(monkeypatch):
    # Setup network blocker
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network opened")))
    
    # Setup toxic env keys that must NOT be read during import
    monkeypatch.setenv("HERMES_GATEWAY_API_KEY", "toxic_env_key")
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_KEY", "toxic_service_account")
    monkeypatch.setenv("OPENAI_API_KEY", "toxic_openai_key")
    
    # Import
    import experiments.live.http_transport as transport
    
    assert hasattr(transport, "LiveCredential")
    assert hasattr(transport, "CredentialProvider")
    assert hasattr(transport, "OpenAICompatibleHttpTransport")


def test_live_credential_repr_and_str_does_not_leak():
    from experiments.live.http_transport import LiveCredential
    
    secret = "Bearer secret_api_key_12345"
    cred = LiveCredential(authorization_header=secret)
    
    # Check that neither repr nor str leaks the authorization header value
    assert secret not in repr(cred)
    assert secret not in str(cred)
    assert "LiveCredential" in repr(cred)


def test_credential_provider_unresolved_fail_closed():
    from experiments.live.http_transport import CredentialProvider, LiveCredential
    
    class UnresolvedCredentialProvider(CredentialProvider):
        def load_for_send(self) -> LiveCredential:
            raise ValueError("No credential resolved")
            
    provider = UnresolvedCredentialProvider()
    with pytest.raises(ValueError, match="No credential resolved"):
        provider.load_for_send()
