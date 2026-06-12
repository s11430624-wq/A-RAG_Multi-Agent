from __future__ import annotations

import pytest
import re
import json
from pathlib import Path
from experiments.live.http_transport import LiveCredential, OpenAICompatibleHttpTransport
from experiments.providers.models import TransportRequest, ProviderTransportError
from tests.live.test_http_transport import MockOpenerDirector, MockHttpResponse

def test_leakage_audit_structure_rules():
    # 1. Verify credential repr and string never print the actual token
    secret = "SUPER_SECRET_KEY_12345"
    cred = LiveCredential(authorization_header=f"Bearer {secret}")
    
    assert secret not in repr(cred)
    assert secret not in str(cred)
    assert "Authorization" not in repr(cred)
    assert "Authorization" not in str(cred)


def test_leakage_exception_redaction():
    # 2. Verify exception messages from transport never leak the token or Authorization headers
    secret = "Bearer SENSITIVE_TOKEN_ABC"
    
    def failing_sender(req):
        raise OSError(f"Failed to open connection using token {secret}")
        
    opener = MockOpenerDirector(failing_sender)
    
    class FailingProvider:
        def load_for_send(self):
            return LiveCredential(authorization_header=secret)
            
    transport = OpenAICompatibleHttpTransport(
        api_base="https://localhost:8000/v1",
        credential_provider=FailingProvider(),
        opener=opener,
    )
    
    req = TransportRequest(
        method="POST",
        url="https://localhost:8000/v1",
        public_headers=(),
        json_body=b"{}",
        timeout_seconds=30.0,
        client_request_id="test",
    )
    
    with pytest.raises(ProviderTransportError) as exc_info:
        transport.send(req)
        
    err_msg = str(exc_info.value)
    assert "SENSITIVE_TOKEN_ABC" not in err_msg
    assert "Authorization" not in err_msg
    assert "Bearer" not in err_msg


def test_leakage_provenance_structural_scanning():
    # 3. Verify that we can scan requests for hidden test metadata or patches structurally (not just blind string matching)
    def check_request_provenance(request_body: bytes) -> bool:
        try:
            data = json.loads(request_body.decode("utf-8"))
        except Exception:
            return True
            
        prompt = ""
        if isinstance(data, dict):
            messages = data.get("messages", [])
            for m in messages:
                prompt += m.get("content", "")
        
        # Reference patches usually contain unified diff headers
        if "--- a/" in prompt or "+++ b/" in prompt:
            return False
            
        if "evaluation/reference_patches" in prompt:
            return False
            
        return True

    # Attack: request containing reference patch structure
    attack_body_1 = json.dumps({
        "messages": [
            {"role": "user", "content": "Here is the patch:\n--- a/student_system/solution.py\n+++ b/student_system/solution.py"}
        ]
    }).encode("utf-8")
    
    # Attack: request containing hidden tests path
    attack_body_2 = json.dumps({
        "messages": [
            {"role": "user", "content": "Please read evaluation/reference_patches/T01.diff"}
        ]
    }).encode("utf-8")

    # Safe request
    safe_body = json.dumps({
        "messages": [
            {"role": "user", "content": "Hello, how do I write a budget tracker?"}
        ]
    }).encode("utf-8")

    assert check_request_provenance(attack_body_1) is False
    assert check_request_provenance(attack_body_2) is False
    assert check_request_provenance(safe_body) is True
