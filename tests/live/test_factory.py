from __future__ import annotations

import pytest
from experiments.runner.config import ExperimentConfig, ExperimentPaths
from experiments.live.factory import LiveProviderFactory

def test_factory_fails_closed_on_live_without_env_flag(monkeypatch, tmp_path):
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    
    paths = ExperimentPaths(
        tasks_definition=tmp_path / "tasks.json",
        raw_results_dir=tmp_path / "raw",
        derived_results_dir=tmp_path / "derived",
        reviews_dir=tmp_path / "reviews",
        workspace_base_dir=tmp_path / "workspaces",
        artifact_root=tmp_path / "raw" / "artifacts",
        retrieval_log_root=tmp_path / "raw" / "retrieval",
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
        live_opt_in=False, # Set to False since no env flag
    )
    
    with pytest.raises(ValueError, match="Live mode is not approved by env"):
        LiveProviderFactory.create_provider(config, model_id="google/gemini-3.5-flash", env={})


def test_factory_loads_from_models_yaml_and_runtime_config(monkeypatch, tmp_path):
    import yaml
    from experiments.providers.models import ProviderCapabilities
    from experiments.live.factory import ProviderRuntimeConfig
    
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    
    # 1. Setup repo structure
    repo_root = tmp_path
    configs_dir = repo_root / "configs"
    configs_dir.mkdir(parents=True)
    
    # Write models.yaml
    models_content = {
        "default_model": "google/gemini-3.5-flash",
        "default_provider": "hermes_vertex_gateway",
        "providers": {
            "hermes_vertex_gateway": {
                "name": "Hermes Vertex Gateway",
                "api_base": "http://127.0.0.1:8787/v1",
                "models": [
                    {
                        "id": "google/gemini-3.5-flash",
                        "temperature": 0.123,
                        "max_output_tokens": 1024,
                        "top_p": 0.88,
                    }
                ]
            }
        }
    }
    (configs_dir / "models.yaml").write_text(yaml.dump(models_content), encoding="utf-8")
    
    # Paths for config
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
    
    # Case A: Fallback to models.yaml parsing (no explicit provider_runtime_config)
    provider_a = LiveProviderFactory.create_provider(
        config,
        model_id="google/gemini-3.5-flash",
        env={"ARAG_RUN_LIVE_GATEWAY": "1"}
    )
    assert provider_a.config.api_base == "http://127.0.0.1:8787/v1"
    assert provider_a.config.parameters.temperature == 0.123
    assert provider_a.config.parameters.max_output_tokens == 1024
    assert provider_a.config.parameters.top_p == 0.88
    
    # Case B: Injecting explicit ProviderRuntimeConfig
    custom_caps = ProviderCapabilities(supports_seed=False, supports_request_id=False, returns_usage=True)
    custom_runtime_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://127.0.0.1:8787/v1",
        capabilities=custom_caps,
    )
    provider_b = LiveProviderFactory.create_provider(
        config,
        model_id="google/gemini-3.5-flash",
        env={"ARAG_RUN_LIVE_GATEWAY": "1"},
        provider_runtime_config=custom_runtime_config,
    )
    assert provider_b.config.api_base == "http://127.0.0.1:8787/v1"
    assert provider_b.config.capabilities.supports_seed is False
    assert provider_b.config.capabilities.supports_request_id is False


def test_factory_rejects_attacker_provider_overrides(monkeypatch, tmp_path):
    import yaml
    from experiments.providers.models import ProviderCapabilities
    from experiments.live.factory import ProviderRuntimeConfig
    
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    repo_root = tmp_path
    configs_dir = repo_root / "configs"
    configs_dir.mkdir(parents=True)
    
    # Write models.yaml with two providers
    models_content = {
        "default_model": "google/gemini-3.5-flash",
        "default_provider": "hermes_vertex_gateway",
        "providers": {
            "hermes_vertex_gateway": {
                "name": "Hermes Vertex Gateway",
                "api_base": "http://127.0.0.1:8787/v1",
                "models": [{"id": "google/gemini-3.5-flash"}]
            },
            "attacker_provider": {
                "name": "Attacker Gateway",
                "api_base": "https://malicious-attacker-endpoint/v1",
                "models": [{"id": "google/gemini-3.5-flash"}]
            }
        }
    }
    (configs_dir / "models.yaml").write_text(yaml.dump(models_content), encoding="utf-8")
    
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
    
    # 1. Reject provider_id mismatch
    mismatched_runtime_config = ProviderRuntimeConfig(
        provider_id="attacker_provider", # Mismatched with config.model_provider_id
        api_base="https://custom-gateway:443/v1",
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime provider override mismatch"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=mismatched_runtime_config,
        )
        
    # 2. Reject api_base mixing with another provider's endpoint in models.yaml
    mixed_endpoint_config = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway", # Matches config.model_provider_id
        api_base="https://malicious-attacker-endpoint/v1", # Mapped to attacker_provider in models.yaml!
        capabilities=custom_caps,
    )
    with pytest.raises(ValueError, match="Runtime endpoint override mixes provider endpoint"):
        LiveProviderFactory.create_provider(
            config,
            model_id="google/gemini-3.5-flash",
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            provider_runtime_config=mixed_endpoint_config,
        )
