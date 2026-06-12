from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from experiments.providers.models import (
    ModelParameters,
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigError,
)

_FORBIDDEN_KEYS = {"api_key", "token", "credential", "authorization", "secret"}


def load_provider_config(models_path: Path, experiment_path: Path) -> ProviderConfig:
    try:
        models = yaml.safe_load(Path(models_path).read_text(encoding="utf-8"))
        experiment = yaml.safe_load(Path(experiment_path).read_text(encoding="utf-8"))
        _reject_secret_keys(models)
        _reject_secret_keys(experiment)
        if not isinstance(models, dict) or not isinstance(experiment, dict):
            raise ValueError("configuration roots must be mappings")
        provider_id = _required_string(models, "default_provider")
        model_id = _required_string(models, "default_model")
        providers = models.get("providers")
        if not isinstance(providers, dict) or provider_id not in providers:
            raise ValueError("default provider is not configured")
        provider = providers[provider_id]
        if not isinstance(provider, dict):
            raise ValueError("provider configuration must be a mapping")
        api_base = _required_string(provider, "api_base")
        configured_models = provider.get("models")
        if not isinstance(configured_models, list):
            raise ValueError("provider models must be a list")
        matches = [item for item in configured_models if isinstance(item, dict) and item.get("id") == model_id]
        if len(matches) != 1:
            raise ValueError("default model must appear exactly once")
        model = matches[0]
        timeout = experiment.get("timeout")
        if not isinstance(timeout, dict):
            raise ValueError("experiment timeout must be a mapping")
        parameters = ModelParameters(
            model=model_id,
            temperature=model.get("temperature"),
            top_p=model.get("top_p"),
            max_output_tokens=model.get("max_output_tokens"),
            timeout_seconds=timeout.get("agent_response"),
            seed=experiment.get("seed"),
        )
        return ProviderConfig(
            provider_id=provider_id,
            api_base=api_base,
            parameters=parameters,
            capabilities=ProviderCapabilities(True, True, True),
            max_attempts=3,
            retry_backoff_seconds=(0.25, 0.5),
        )
    except ProviderConfigError:
        raise
    except Exception as exc:
        raise ProviderConfigError(f"invalid provider configuration: {exc}") from exc


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in _FORBIDDEN_KEYS:
                raise ValueError(f"credential-like key is forbidden: {key}")
            _reject_secret_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_secret_keys(item)
