from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from experiments.live.budget import BudgetLimits
from experiments.live.factory import LiveProviderFactory, ProviderRuntimeConfig
from experiments.live.http_transport import AttemptReservingTransport
from experiments.live.smoke_executor import (
    ProviderAttemptHooks,
    SmokeExecutionRequest,
    validate_smoke_execution_request,
)
from experiments.live.smoke_scheduler import build_smoke_scheduler_plan
from experiments.providers.config import load_provider_config
from experiments.providers.openai_compatible import OpenAICompatibleProvider
from experiments.runner.config import (
    ExperimentConfig,
    ExperimentPaths,
    load_experiment_config,
)
from experiments.runner.scheduler import PlannedRun


APPROVED_PROVIDER_ID = "openai_compatible_gateway"
APPROVED_MODEL = "GPT5.4"
APPROVED_API_BASE = "http://127.0.0.1:8787/v1"


@dataclass(frozen=True)
class LiveSmokeComposition:
    request: SmokeExecutionRequest
    config: ExperimentConfig
    runs: tuple[PlannedRun, ...]
    providers: tuple[OpenAICompatibleProvider, ...]


def build_live_smoke_provider_factory(
    config: ExperimentConfig,
    *,
    env: Mapping[str, str],
    provider_runtime_config: ProviderRuntimeConfig | None = None,
):
    if provider_runtime_config is not None:
        raise ValueError("live smoke composition forbids provider runtime overrides")
    _validate_live_config(config, env)

    def provider_factory(run: PlannedRun, hooks: ProviderAttemptHooks):
        if run.identity.seed != config.seed:
            raise ValueError("planned run seed does not match live smoke config")
        provider = LiveProviderFactory.create_provider(
            config,
            model_id=config.model,
            env=env,
            credential_provider=None,
            attempt_reservation=hooks.reserve_provider_attempt,
            limiter=getattr(hooks, "limiter", None),
        )
        _validate_composed_provider(provider, config)
        return provider

    return provider_factory


def build_live_smoke_request(
    *,
    repo_root: Path,
    experiment_id: str,
    human_approval: str,
    raw_jsonl_path: Path,
    artifact_root: Path,
    retrieval_log_root: Path,
    smoke_report_path: Path,
    budget_limits: BudgetLimits,
    env: Mapping[str, str],
) -> SmokeExecutionRequest:
    root = Path(repo_root).resolve()
    if env.get("ARAG_ALLOW_SMOKE_RUN") != "1":
        raise ValueError("live smoke composition requires ARAG_ALLOW_SMOKE_RUN=1")
    if human_approval != "SMOKE_RUN":
        raise ValueError("live smoke composition requires human approval SMOKE_RUN")
    _validate_budget(budget_limits)
    config = _load_live_config(root, env, raw_jsonl_path, artifact_root, retrieval_log_root, experiment_id)
    request = SmokeExecutionRequest(
        experiment_id=experiment_id,
        repo_root=root,
        raw_jsonl_path=Path(raw_jsonl_path),
        artifact_root=Path(artifact_root),
        retrieval_log_root=Path(retrieval_log_root),
        smoke_report_path=Path(smoke_report_path),
        budget_limits=budget_limits,
        provider_factory=build_live_smoke_provider_factory(config, env=env),
    )
    validate_smoke_execution_request(request)
    return request


def validate_live_smoke_composition(
    request: SmokeExecutionRequest,
    *,
    env: Mapping[str, str],
    config_override: ExperimentConfig | None = None,
) -> LiveSmokeComposition:
    root = validate_smoke_execution_request(request)
    config = config_override or _load_live_config(
        root,
        env,
        request.raw_jsonl_path,
        request.artifact_root,
        request.retrieval_log_root,
        request.experiment_id,
    )
    if env.get("ARAG_ALLOW_SMOKE_RUN") != "1":
        raise ValueError("live smoke composition requires ARAG_ALLOW_SMOKE_RUN=1")
    _validate_live_config(config, env)
    plan = build_smoke_scheduler_plan(
        config,
        repo_root=root,
        today=request.experiment_id[len("m7d_smoke_") : len("m7d_smoke_") + 8],
    )
    hooks = ProviderAttemptHooks(lambda: None)
    providers = tuple(request.provider_factory(run, hooks) for run in plan.runs)
    if len(providers) != 3 or len({id(provider) for provider in providers}) != 3:
        raise ValueError("live smoke composition requires three independent providers")
    return LiveSmokeComposition(request, config, plan.runs, providers)


def _load_live_config(
    repo_root: Path,
    env: Mapping[str, str],
    raw_jsonl_path: Path,
    artifact_root: Path,
    retrieval_log_root: Path,
    experiment_id: str,
) -> ExperimentConfig:
    config = load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=repo_root / "configs" / "models.yaml",
        repo_root=repo_root,
        mode="live",
        env=env,
    )
    paths = ExperimentPaths(
        tasks_definition=repo_root / "experiments" / "tasks.json",
        raw_results_dir=Path(raw_jsonl_path).resolve().parent,
        derived_results_dir=repo_root / "results" / "derived",
        reviews_dir=repo_root / "results" / "reviews",
        workspace_base_dir=repo_root / "workspaces" / experiment_id,
        artifact_root=Path(artifact_root).resolve(),
        retrieval_log_root=Path(retrieval_log_root).resolve(),
    )
    config = replace(config, repetitions=1, paths=paths)
    _validate_live_config(config, env)
    provider_config = load_provider_config(
        repo_root / "configs" / "models.yaml",
        repo_root / "configs" / "experiment.yaml",
    )
    if (
        provider_config.provider_id != config.model_provider_id
        or provider_config.parameters.model != config.model
        or provider_config.parameters.seed != config.seed
        or provider_config.api_base != APPROVED_API_BASE
    ):
        raise ValueError("provider/model/api_base must exactly match validated configuration")
    return config


def _validate_live_config(config: ExperimentConfig, env: Mapping[str, str]) -> None:
    if config.mode != "live" or not config.live_opt_in:
        raise ValueError("live smoke composition requires live mode")
    if env.get("ARAG_RUN_LIVE_GATEWAY") != "1":
        raise ValueError("live smoke composition requires ARAG_RUN_LIVE_GATEWAY=1")
    if config.model_provider_id != APPROVED_PROVIDER_ID:
        raise ValueError("unapproved live smoke provider")
    if config.model != APPROVED_MODEL:
        raise ValueError("unapproved live smoke model")
    if config.seed != 42:
        raise ValueError("unapproved live smoke seed")
    if set(config.strategies) != {"A", "C", "E"} or len(config.strategies) != 3:
        raise ValueError("live smoke requires exactly A/C/E")


def _validate_composed_provider(provider, config: ExperimentConfig) -> None:
    if provider.config.provider_id != APPROVED_PROVIDER_ID:
        raise ValueError("composed provider id mismatch")
    if provider.config.api_base != APPROVED_API_BASE:
        raise ValueError("composed provider endpoint mismatch")
    if provider.config.parameters.model != config.model:
        raise ValueError("composed provider model mismatch")
    if provider.config.parameters.seed != config.seed:
        raise ValueError("composed provider seed mismatch")
    if not isinstance(provider.transport, AttemptReservingTransport):
        raise ValueError("composed provider lacks attempt reservation transport")
    if not provider.transport.no_auth_loopback:
        raise ValueError("composed provider must use no_auth_loopback transport")
    if provider.transport.inner.credential_provider is not None:
        raise ValueError("no_auth_loopback transport must not load credentials")


def _validate_budget(limits: BudgetLimits) -> None:
    approved = (
        limits.max_total_calls == 22
        and limits.max_total_input_tokens == 120000
        and limits.max_total_output_tokens == 48000
        and limits.max_wall_clock_seconds == 1800
        and limits.max_consecutive_infra_failures == 2
    )
    if not approved:
        raise ValueError("live smoke budget must equal the approved fixed tuple")
