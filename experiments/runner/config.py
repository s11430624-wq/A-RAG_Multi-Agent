from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

from experiments.runner.errors import ExperimentConfigError


StrategyName = Literal["A", "C", "E"]
RunMode = Literal["dry_run", "mock_run", "live"]
_STRATEGIES = ("A", "C", "E")
_FORBIDDEN_KEYS = {"api_key", "token", "credential", "authorization", "secret"}


@dataclass(frozen=True)
class ExperimentPaths:
    tasks_definition: Path
    raw_results_dir: Path
    derived_results_dir: Path
    reviews_dir: Path
    workspace_base_dir: Path
    artifact_root: Path
    retrieval_log_root: Path


@dataclass(frozen=True)
class ExperimentConfig:
    strategies: tuple[StrategyName, ...]
    repetitions: int
    max_repair_rounds: int
    seed: int
    agent_timeout_seconds: float
    unit_test_timeout_seconds: float
    total_run_timeout_seconds: float
    paths: ExperimentPaths
    model_provider_id: str
    model: str
    mode: RunMode
    live_opt_in: bool


def load_experiment_config(
    *,
    experiment_path: Path,
    models_path: Path,
    repo_root: Path,
    mode: RunMode = "mock_run",
    env: Mapping[str, str] | None = None,
) -> ExperimentConfig:
    root = Path(repo_root).resolve()
    if mode not in ("dry_run", "mock_run", "live"):
        raise ExperimentConfigError("invalid run mode")
    gate_env = env or {}
    live_opt_in = mode == "live" and gate_env.get("ARAG_RUN_LIVE_GATEWAY") == "1"
    if mode == "live" and not live_opt_in:
        raise ExperimentConfigError("live mode requires ARAG_RUN_LIVE_GATEWAY=1")

    experiment = _load_yaml_mapping(experiment_path)
    models = _load_yaml_mapping(models_path)
    _reject_secret_keys(experiment)
    _reject_secret_keys(models)

    strategies = _strategies(experiment.get("strategies"))
    repetitions = _int_range(experiment.get("repetitions"), "repetitions", minimum=1)
    max_repair_rounds = _int_range(experiment.get("max_repair_rounds"), "max_repair_rounds", minimum=0, maximum=2)
    seed = _int_range(experiment.get("seed"), "seed")
    timeouts = _mapping(experiment.get("timeout"), "timeout")
    paths = _paths(_mapping(experiment.get("paths"), "paths"), root)

    provider_id = _string(models.get("default_provider"), "default_provider")
    model_id = _string(models.get("default_model"), "default_model")
    providers = _mapping(models.get("providers"), "providers")
    provider = _mapping(providers.get(provider_id), f"providers.{provider_id}")
    known_models = _list(provider.get("models"), f"providers.{provider_id}.models")
    if model_id not in {_mapping(item, "model").get("id") for item in known_models}:
        raise ExperimentConfigError("default model is not declared by default provider")

    return ExperimentConfig(
        strategies=strategies,
        repetitions=repetitions,
        max_repair_rounds=max_repair_rounds,
        seed=seed,
        agent_timeout_seconds=_positive_number(timeouts.get("agent_response"), "timeout.agent_response"),
        unit_test_timeout_seconds=_positive_number(timeouts.get("unit_test"), "timeout.unit_test"),
        total_run_timeout_seconds=_positive_number(timeouts.get("total_run"), "timeout.total_run"),
        paths=paths,
        model_provider_id=provider_id,
        model=model_id,
        mode=mode,
        live_opt_in=live_opt_in,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExperimentConfigError(f"cannot read config: {path}") from exc
    if not isinstance(value, dict):
        raise ExperimentConfigError("config must be a mapping")
    return value


def _paths(value: dict[str, Any], root: Path) -> ExperimentPaths:
    forbidden = {"artifact_root", "retrieval_log_root"}
    if forbidden.intersection(value):
        raise ExperimentConfigError("artifact_root and retrieval_log_root are derived, not configurable")
    raw = _resolve_under_root(root, _string(value.get("raw_results_dir"), "paths.raw_results_dir"))
    derived = _resolve_under_root(root, _string(value.get("derived_results_dir"), "paths.derived_results_dir"))
    return ExperimentPaths(
        tasks_definition=_resolve_under_root(root, _string(value.get("tasks_definition"), "paths.tasks_definition")),
        raw_results_dir=raw,
        derived_results_dir=derived,
        reviews_dir=_resolve_under_root(root, _string(value.get("reviews_dir"), "paths.reviews_dir")),
        workspace_base_dir=_resolve_under_root(root, _string(value.get("workspace_base_dir"), "paths.workspace_base_dir")),
        artifact_root=(raw / "artifacts").resolve(),
        retrieval_log_root=(raw / "retrieval").resolve(),
    )


def _resolve_under_root(root: Path, raw: str) -> Path:
    path = (root / raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExperimentConfigError(f"path escapes repo root: {raw}") from exc
    return path


def _strategies(value: Any) -> tuple[StrategyName, ...]:
    items = _list(value, "strategies")
    if not items or any(item not in _STRATEGIES for item in items):
        raise ExperimentConfigError("strategies must contain only A, C, E")
    if len(set(items)) != len(items):
        raise ExperimentConfigError("strategies must not contain duplicates")
    return tuple(items)  # type: ignore[return-value]


def _int_range(value: Any, name: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExperimentConfigError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ExperimentConfigError(f"{name} is too small")
    if maximum is not None and value > maximum:
        raise ExperimentConfigError(f"{name} is too large")
    return value


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ExperimentConfigError(f"{name} must be positive")
    return float(value)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentConfigError(f"{name} must be a mapping")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ExperimentConfigError(f"{name} must be a list")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExperimentConfigError(f"{name} must be a non-empty string")
    return value


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered in _FORBIDDEN_KEYS or lowered.endswith("_api_key") or lowered.endswith("_secret"):
                raise ExperimentConfigError("credential-like key is forbidden")
            _reject_secret_keys(child)
    elif isinstance(value, list):
        for item in value:
            _reject_secret_keys(item)
