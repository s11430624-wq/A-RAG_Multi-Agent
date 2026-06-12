from __future__ import annotations

import os
from pathlib import Path
from experiments.providers.models import ModelRequest, ModelParameters, TransportRequest, ModelResponse

APPROVED_ALIAS_MAP = {
    "GPT5.4": "GPT5.4",
}


class GatewayProbe:
    def __init__(self, provider: object, *, supports_request_id: bool = True, supports_seed: bool = True) -> None:
        self.provider = provider
        self.supports_request_id = supports_request_id
        self.supports_seed = supports_seed

    def validate_response(self, response: ModelResponse, model: str) -> None:
        # 1. Finish Reason stop check
        if response.finish_reason != "stop":
            raise ValueError(f"Gateway response finish reason is not 'stop': {response.finish_reason}")

        # 2. Model Identity Verification
        response_model = response.model
        expected_model = APPROVED_ALIAS_MAP.get(model, model)
        if response_model != expected_model:
            raise ValueError(f"Model identity mismatch: expected {expected_model}, got {response_model}")

        # 3. Token Usage Consistency check
        usage = response.usage
        if usage is None or usage.input_tokens is None or usage.output_tokens is None or usage.total_tokens is None:
            raise ValueError("Token usage is incomplete or missing")
            
        if usage.input_tokens < 0 or usage.output_tokens < 0 or usage.total_tokens < 0:
            raise ValueError("Token usage contains negative integers")

        if usage.input_tokens + usage.output_tokens != usage.total_tokens:
            raise ValueError(
                f"Token usage inconsistent: input({usage.input_tokens}) + output({usage.output_tokens}) != total({usage.total_tokens})"
            )

        # Audit metadata validation for normalized usage
        if usage.source == "provider_normalized":
            # Must verify normalized audit metadata is fully present and non-empty
            meta_dict = dict(response.sanitized_metadata)
            required_meta = ["normalization_rule", "normalized_output_tokens", "raw_completion_tokens", "reasoning_tokens", "usage_source"]
            for field in required_meta:
                if field not in meta_dict or not meta_dict[field]:
                    raise ValueError(f"Normalized usage is missing audit metadata field: {field}")
            
            # Check reasoning_tokens and raw_completion_tokens validity in metadata
            try:
                raw_c = int(meta_dict["raw_completion_tokens"])
                reas = int(meta_dict["reasoning_tokens"])
                norm_o = int(meta_dict["normalized_output_tokens"])
                if reas <= 0:
                    raise ValueError("reasoning_tokens must be positive integer")
                if raw_c < 0 or norm_o < 0:
                    raise ValueError("metadata values must be non-negative")
                if norm_o != raw_c + reas:
                    raise ValueError("normalized_output_tokens != raw_completion_tokens + reasoning_tokens")
            except Exception as exc:
                raise ValueError(f"Normalized usage has malformed audit metadata: {exc}") from exc

        # 4. Request ID Check
        if self.supports_request_id and not response.provider_request_id:
            raise ValueError("Request ID is missing but supports_request_id is True")

        # 5. Seed Verification
        if self.supports_seed and not response.seed_applied:
            raise ValueError("Seed applied check failed but supports_seed is True")

    def run_probe(self, model: str) -> ModelResponse:
        params = ModelParameters(
            model=model,
            temperature=0.0,
            max_output_tokens=100,
            top_p=0.95,
            seed=42 if self.supports_seed else 0,
            timeout_seconds=30.0,
        )
        request = ModelRequest(
            call_index=1,
            request_id="probe-request-id",
            system_prompt="",
            user_prompt="hello",
            parameters=params,
            cancellation=None,
        )
        
        response = self.provider.generate(request)
        self.validate_response(response, model)
        return response


def run_live_probe_cli(repo_root: Path) -> int:
    # Check env opt-in
    if os.environ.get("ARAG_RUN_LIVE_GATEWAY") != "1" or os.environ.get("ARAG_ALLOW_SINGLE_PROBE") != "1":
        print("Error: Live probe requires explicit opt-in via env variables:")
        print("  ARAG_RUN_LIVE_GATEWAY=1")
        print("  ARAG_ALLOW_SINGLE_PROBE=1")
        return 2

    print("=== M7-C Local OpenAI-Compatible Proxy Live Probe ===")
    print("Step 1: Readiness check...")
    
    # 1. Check configs/models.yaml
    import yaml
    models_path = repo_root / "configs" / "models.yaml"
    if not models_path.exists():
        print(f"Error: models.yaml not found at {models_path}")
        return 2
        
    with open(models_path, "r", encoding="utf-8") as f:
        models_data = yaml.safe_load(f)
        
    default_model = models_data.get("default_model")
    if default_model != "GPT5.4":
        print(f"Error: default_model must be 'GPT5.4', got '{default_model}'")
        return 2
        
    providers = models_data.get("providers", {})
    if "openai_compatible_gateway" not in providers:
        print("Error: openai_compatible_gateway provider not found in models.yaml")
        return 2
        
    gateway_info = providers["openai_compatible_gateway"]
    api_base = gateway_info.get("api_base")
    if api_base != "http://127.0.0.1:8787/v1":
        print(f"Error: api_base must be 'http://127.0.0.1:8787/v1', got '{api_base}'")
        return 2
        
    supported_models = [m.get("id") for m in gateway_info.get("models", []) if m.get("id")]
    if "GPT5.4" not in supported_models:
        print("Error: GPT5.4 not listed under supported models")
        return 2
        
    print("  [OK] models.yaml configuration is correct.")
    
    # 2. Port check
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect(("127.0.0.1", 8787))
        s.close()
    except Exception as exc:
        print("Error: Local OpenAI-Compatible Proxy is not listening on 127.0.0.1:8787.")
        print("Please start the Local OpenAI-Compatible Proxy using start-openai-proxy.ps1.")
        return 2
        
    print("  [OK] Local OpenAI-Compatible Proxy is listening on 127.0.0.1:8787.")
    
    # 3. Transport and Provider build
    from experiments.live.factory import LiveProviderFactory
    from experiments.runner.config import load_experiment_config
    
    config = load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=models_path,
        repo_root=repo_root,
        mode="live",
        env=os.environ,
    )
    
    provider = LiveProviderFactory.create_provider(
        config=config,
        model_id="GPT5.4",
        env=os.environ,
    )
    
    if not getattr(provider.transport, "no_auth_loopback", False):
        print("Error: M7-B loopback safety profile is not active on the transport.")
        return 2
        
    print("  [OK] M7-B loopback transport validated (No Auth, no Authorization header, origin restricted).")
    
    print("Step 2: Sending single live probe request...")
    
    # Run the probe using the robust OpenAICompatibleProvider.generate and GatewayProbe boundary,
    # which internally utilizes the OpenAICompatibleHttpTransport and the new normalization system.
    probe = GatewayProbe(provider, supports_request_id=True, supports_seed=True)
    
    try:
        # Create a ModelRequest
        params = ModelParameters(
            model="GPT5.4",
            temperature=0.0,
            max_output_tokens=100,
            top_p=0.95,
            seed=42,
            timeout_seconds=30.0,
        )
        request = ModelRequest(
            call_index=1,
            request_id="probe-request-id-123",
            system_prompt="",
            user_prompt="hello, reply with exactly 'hi'",
            parameters=params,
            cancellation=None,
        )
        
        # We explicitly execute generate exactly once
        response = provider.generate(request)
        
        # Execute GatewayProbe validation contract on the same response object, avoiding redundant network request
        probe.validate_response(response, "GPT5.4")
        
    except Exception as exc:
        print(f"\n=== CRITICAL CAPABILITY MISMATCH BLOCKERS DETECTED ===")
        print(f" - [BLOCKER] Gateway validation contract failed: {exc}")
        print("======================================================")
        print("Result: FAIL CLOSED (Capability Mismatch Blockers present)")
        return 2
        
    print("  [OK] HTTP request succeeded.")
    
    # Print out raw and normalized usage summary for user reporting
    meta_dict = dict(response.sanitized_metadata)
    print("\n--- Probe Response Analysis ---")
    print(f"Response Model: {response.model}")
    print(f"Finish Reason: {response.finish_reason}")
    print(f"Content: '{response.text}'")
    print(f"Provider Request ID: {response.provider_request_id}")
    print(f"Usage Object (Normalized): input_tokens={response.usage.input_tokens}, output_tokens={response.usage.output_tokens}, total_tokens={response.usage.total_tokens}, source={response.usage.source}")
    
    if response.usage.source == "provider_normalized":
        print(f"  [Audit Metadata] normalization_rule: {meta_dict.get('normalization_rule')}")
        print(f"  [Audit Metadata] raw_completion_tokens: {meta_dict.get('raw_completion_tokens')}")
        print(f"  [Audit Metadata] reasoning_tokens: {meta_dict.get('reasoning_tokens')}")
        print(f"  [Audit Metadata] normalized_output_tokens: {meta_dict.get('normalized_output_tokens')}")
        print(f"  [Audit Metadata] usage_source: {meta_dict.get('usage_source')}")
    
    print(f"Seed support: Checked (applied seed=42 in request).")
    
    print("\n[SUCCESS] Single live probe passed all checks!")
    return 0
