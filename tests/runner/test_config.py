from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from experiments.runner.config import ExperimentConfigError, load_experiment_config


def test_loads_existing_configs_into_frozen_experiment_config(project_root):
    config = load_experiment_config(
        experiment_path=project_root / "configs/experiment.yaml",
        models_path=project_root / "configs/models.yaml",
        repo_root=project_root,
        mode="mock_run",
        env={},
    )

    assert config.strategies == ("A", "C", "E")
    assert config.repetitions == 3
    assert config.max_repair_rounds == 2
    assert config.seed == 42
    assert config.model == "GPT5.4"
    assert config.model_provider_id == "openai_compatible_gateway"
    assert config.mode == "mock_run"
    assert config.live_opt_in is False
    assert config.paths.artifact_root == config.paths.raw_results_dir / "artifacts"
    assert config.paths.retrieval_log_root == config.paths.raw_results_dir / "retrieval"
    with pytest.raises(FrozenInstanceError):
        config.seed = 7


def test_config_rejects_unsafe_or_missing_values(tmp_path, project_root):
    bad_experiment = tmp_path / "experiment.yaml"
    bad_models = tmp_path / "models.yaml"
    bad_experiment.write_text(
        "strategies: [A, B]\nrepetitions: 0\nmax_repair_rounds: 3\n"
        "seed: true\ntimeout: {agent_response: 1, unit_test: 1, total_run: 1}\n"
        "paths: {tasks_definition: experiments/tasks.json, raw_results_dir: ../escape, "
        "derived_results_dir: results/derived, reviews_dir: results/reviews, workspace_base_dir: workspaces}\n",
        encoding="utf-8",
    )
    bad_models.write_text("default_provider: missing\ndefault_model: m\nproviders: {}\n", encoding="utf-8")

    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=bad_experiment,
            models_path=bad_models,
            repo_root=project_root,
            mode="mock_run",
            env={},
        )


def test_config_rejects_artifact_and_retrieval_log_path_overrides(tmp_path, project_root):
    experiment = tmp_path / "experiment.yaml"
    experiment.write_text(
        "strategies: [A]\nrepetitions: 1\nmax_repair_rounds: 1\nseed: 42\n"
        "timeout: {agent_response: 1, unit_test: 1, total_run: 10}\n"
        "paths: {tasks_definition: experiments/tasks.json, raw_results_dir: results/raw, "
        "derived_results_dir: results/derived, reviews_dir: results/reviews, "
        "workspace_base_dir: workspaces, artifact_root: elsewhere, retrieval_log_root: elsewhere}\n",
        encoding="utf-8",
    )

    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=experiment,
            models_path=project_root / "configs/models.yaml",
            repo_root=project_root,
            mode="mock_run",
            env={},
        )


def test_mock_and_dry_run_do_not_read_credential_environment(project_root):
    env = {
        "ARAG_RUN_LIVE_GATEWAY": "1",
        "API_KEY": "SECRET_SHOULD_NOT_BE_READ",
        "TOKEN": "SECRET_SHOULD_NOT_BE_READ",
        "GOOGLE_APPLICATION_CREDENTIALS": "SECRET_SHOULD_NOT_BE_READ",
    }

    for mode in ("mock_run", "dry_run"):
        config = load_experiment_config(
            experiment_path=project_root / "configs/experiment.yaml",
            models_path=project_root / "configs/models.yaml",
            repo_root=project_root,
            mode=mode,
            env=env,
        )
        assert config.live_opt_in is False


def test_live_mode_requires_explicit_gate(project_root):
    with pytest.raises(ExperimentConfigError):
        load_experiment_config(
            experiment_path=project_root / "configs/experiment.yaml",
            models_path=project_root / "configs/models.yaml",
            repo_root=project_root,
            mode="live",
            env={},
        )

    config = load_experiment_config(
        experiment_path=project_root / "configs/experiment.yaml",
        models_path=project_root / "configs/models.yaml",
        repo_root=project_root,
        mode="live",
        env={"ARAG_RUN_LIVE_GATEWAY": "1", "API_KEY": "SECRET_SHOULD_NOT_BE_READ"},
    )
    assert config.live_opt_in is True
