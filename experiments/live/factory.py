from __future__ import annotations

import time
import yaml
from dataclasses import dataclass
from typing import Callable, Mapping
from experiments.runner.config import ExperimentConfig
from experiments.providers.openai_compatible import OpenAICompatibleProvider
from experiments.providers.models import ProviderConfig, ProviderCapabilities, ModelParameters
from experiments.live.http_transport import (
    AttemptReservingTransport,
    OpenAICompatibleHttpTransport,
    CredentialProvider,
    LiveCredential,
)


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_id: str
    api_base: str
    capabilities: ProviderCapabilities
    max_attempts: int = 3
    retry_backoff_seconds: tuple[float, ...] = (0.25, 0.5)


class DummyCredentialProvider(CredentialProvider):
    def load_for_send(self) -> LiveCredential:
        raise ValueError("Credential unresolved in M7-A/M7-B")


class LiveProviderFactory:
    @staticmethod
    def create_provider(
        config: ExperimentConfig,
        model_id: str,
        env: Mapping[str, str],
        *,
        credential_provider: CredentialProvider | None = None,
        provider_runtime_config: ProviderRuntimeConfig | None = None,
        attempt_reservation: Callable[[], None] | None = None,
        limiter: object | None = None,
    ) -> OpenAICompatibleProvider:
        if config.mode == "live":
            if env.get("ARAG_RUN_LIVE_GATEWAY") != "1":
                raise ValueError("Live mode is not approved by env")
            
            # Find repo root and read models.yaml dynamically
            repo_root = config.paths.raw_results_dir.parent.parent
            models_path = repo_root / "configs" / "models.yaml"
            with open(models_path, "r", encoding="utf-8") as f:
                models_data = yaml.safe_load(f)
            
            provider_id = config.model_provider_id
            providers = models_data.get("providers", {})
            if provider_id not in providers:
                raise ValueError(f"Provider {provider_id} not found in models.yaml")
            provider_info = providers[provider_id]
            
            # Load model parameters from models.yaml
            model_info = None
            for m in provider_info.get("models", []):
                if m.get("id") == model_id:
                    model_info = m
                    break
            if not model_info:
                raise ValueError(f"Model {model_id} not found under provider {provider_id} in models.yaml")
                
            # Determine parameters dynamically
            params = ModelParameters(
                model=model_id,
                temperature=model_info.get("temperature", 0.0),
                top_p=model_info.get("top_p", 0.95),
                max_output_tokens=model_info.get("max_output_tokens", 4096),
                timeout_seconds=config.agent_timeout_seconds,
                seed=config.seed,
            )
            
            # Determine api_base, capabilities, max_attempts, retry_backoff_seconds
            if provider_runtime_config is not None:
                if provider_runtime_config.provider_id != config.model_provider_id:
                    raise ValueError(f"Runtime provider override mismatch: config={config.model_provider_id}, runtime={provider_runtime_config.provider_id}")
                for other_prov_id, other_prov_info in models_data.get("providers", {}).items():
                    if other_prov_id != config.model_provider_id:
                        other_api_base = other_prov_info.get("api_base")
                        if other_api_base and provider_runtime_config.api_base == other_api_base:
                            raise ValueError(f"Runtime endpoint override mixes provider endpoint: {provider_runtime_config.api_base} belongs to {other_prov_id}")
                
                # Check for invalid overrides on openai_compatible_gateway
                if config.model_provider_id == "openai_compatible_gateway":
                    url_lower = provider_runtime_config.api_base.lower()
                    # Reject localhost, 8788, trycloudflare (or cloudflare), and any other invalid endpoints
                    if "localhost" in url_lower or "8788" in url_lower or "cloudflare" in url_lower or url_lower != "http://127.0.0.1:8787/v1":
                        raise ValueError(f"Runtime override contains unapproved endpoint: {provider_runtime_config.api_base}")

                api_base = provider_runtime_config.api_base
                capabilities = provider_runtime_config.capabilities
                max_attempts = provider_runtime_config.max_attempts
                retry_backoff_seconds = provider_runtime_config.retry_backoff_seconds
            else:
                api_base = provider_info.get("api_base")
                if not api_base:
                    raise ValueError(f"api_base not configured for provider {provider_id}")
                capabilities = ProviderCapabilities(supports_seed=True, supports_request_id=True, returns_usage=True)
                max_attempts = 3
                retry_backoff_seconds = (0.25, 0.5)
            
            # Construct ProviderConfig
            provider_config = ProviderConfig(
                provider_id=provider_id,
                api_base=api_base,
                parameters=params,
                capabilities=capabilities,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            
            transport = OpenAICompatibleHttpTransport(
                api_base=api_base,
                credential_provider=credential_provider,
                timeout_seconds=config.agent_timeout_seconds,
            )
            if attempt_reservation is not None:
                transport = AttemptReservingTransport(transport, attempt_reservation, limiter=limiter)
            
            return OpenAICompatibleProvider(
                provider_config,
                transport=transport,
                clock=limiter.clock if limiter is not None and hasattr(limiter, "clock") else time.monotonic,
                epoch_clock=limiter.epoch_clock if limiter is not None and hasattr(limiter, "epoch_clock") else time.time,
                retry_delay_resolver=limiter.resolve_retry_delay if limiter is not None and hasattr(limiter, "resolve_retry_delay") else None,
            )
        else:
            raise ValueError(f"Unsupported mode: {config.mode}")
