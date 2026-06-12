from __future__ import annotations

import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import urllib.request

import pytest

from experiments.cli import main
from experiments.live.budget import BudgetExceededError, BudgetLimits, LiveBudgetTracker
from experiments.live.http_transport import AttemptReservingTransport
from experiments.live.factory import ProviderRuntimeConfig
from experiments.live.smoke_composition import (
    build_live_smoke_request,
    validate_live_smoke_composition,
)
from experiments.live.smoke_executor import SmokeExecutor
from experiments.providers.models import (
    ModelRequest,
    ProviderCapabilities,
    ProviderConfigError,
    TransportResponse,
)
from experiments.runner.errors import ExperimentConfigError


EXPERIMENT_ID = "m7d_smoke_20260611T120000Z"
LIVE_ENV = {
    "ARAG_RUN_LIVE_GATEWAY": "1",
    "ARAG_ALLOW_SMOKE_RUN": "1",
}


def _fixture_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    repo = tmp_path / "repo"
    shutil.copytree(source / "configs", repo / "configs")
    (repo / "experiments").mkdir(parents=True)
    shutil.copy2(source / "experiments" / "tasks.json", repo / "experiments" / "tasks.json")
    return repo


def _limits() -> BudgetLimits:
    return BudgetLimits(
        max_total_input_tokens=120000,
        max_total_output_tokens=48000,
        max_total_calls=22,
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=1800,
    )


def _request(repo: Path):
    raw = repo / "results" / "raw"
    return build_live_smoke_request(
        repo_root=repo,
        experiment_id=EXPERIMENT_ID,
        human_approval="SMOKE_RUN",
        raw_jsonl_path=raw / f"{EXPERIMENT_ID}.jsonl",
        artifact_root=raw / "artifacts" / EXPERIMENT_ID,
        retrieval_log_root=raw / "retrieval" / EXPERIMENT_ID,
        smoke_report_path=raw / "gates" / f"{EXPERIMENT_ID}.json",
        budget_limits=_limits(),
        env=LIVE_ENV,
    )


def _cli_args(repo: Path) -> list[str]:
    request = _request(repo)
    return [
        "live-smoke",
        "--repo-root",
        str(repo),
        "--experiment-id",
        EXPERIMENT_ID,
        "--human-approval",
        "SMOKE_RUN",
        "--raw-jsonl",
        str(request.raw_jsonl_path),
        "--artifact-root",
        str(request.artifact_root),
        "--retrieval-log-root",
        str(request.retrieval_log_root),
        "--smoke-report",
        str(request.smoke_report_path),
        "--max-provider-calls",
        "22",
        "--max-input-tokens",
        "120000",
        "--max-output-tokens",
        "48000",
        "--max-wall-clock-seconds",
        "1800",
        "--consecutive-infra-failure-threshold",
        "2",
    ]


def _model_request(provider, call_index: int = 1) -> ModelRequest:
    return ModelRequest(
        call_index,
        f"request-{call_index}",
        "",
        "prompt",
        provider.config.parameters,
        None,
    )


class ScriptedSender:
    no_auth_loopback = True
    credential_provider = None

    def __init__(self, outcomes, reservations):
        self.outcomes = list(outcomes)
        self.reservations = reservations
        self.calls = []

    def send(self, request, *, cancellation=None):
        self.calls.append((request, len(self.reservations)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _response(status: int = 200) -> TransportResponse:
    body = {
        "id": "offline",
        "model": "google/gemini-3.5-flash",
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    return TransportResponse(status, json.dumps(body).encode(), (), "offline")


def test_live_smoke_composition_builds_three_independent_run_providers(tmp_path):
    repo = _fixture_repo(tmp_path)
    composition = validate_live_smoke_composition(_request(repo), env=LIVE_ENV)

    assert [run.identity.strategy for run in composition.runs] == ["A", "C", "E"]
    assert len({id(provider) for provider in composition.providers}) == 3
    assert {provider.config.provider_id for provider in composition.providers} == {
        "hermes_vertex_gateway"
    }
    assert {provider.config.parameters.model for provider in composition.providers} == {
        "google/gemini-3.5-flash"
    }
    assert {provider.config.parameters.seed for provider in composition.providers} == {42}
    assert all(provider.transport.no_auth_loopback for provider in composition.providers)
    assert all(provider.transport.inner.credential_provider is None for provider in composition.providers)


def test_attempt_reservation_happens_before_each_retry_send(tmp_path):
    repo = _fixture_repo(tmp_path)
    composition = validate_live_smoke_composition(_request(repo), env=LIVE_ENV)
    provider = composition.providers[0]
    reservations = []
    sender = ScriptedSender([OSError("one"), OSError("two"), _response()], reservations)
    provider.transport = AttemptReservingTransport(
        sender,
        lambda: reservations.append("reserved"),
    )
    provider._sleeper = lambda _seconds: None

    response = provider.generate(_model_request(provider))

    assert response.retry_count == 2
    assert [count for _request, count in sender.calls] == [1, 2, 3]
    assert len(reservations) == 3
    assert all(
        key.casefold() != "authorization"
        for request, _count in sender.calls
        for key, _value in request.public_headers
    )


def test_attempt_23_is_blocked_before_underlying_sender(tmp_path):
    repo = _fixture_repo(tmp_path)
    composition = validate_live_smoke_composition(_request(repo), env=LIVE_ENV)
    provider = composition.providers[0]
    tracker = LiveBudgetTracker(_limits())
    for _ in range(22):
        tracker.reserve_provider_attempt()
    sender = ScriptedSender([_response()], [])
    provider.transport = AttemptReservingTransport(
        sender,
        tracker.reserve_provider_attempt,
    )

    with pytest.raises(BudgetExceededError):
        provider.generate(_model_request(provider))

    assert sender.calls == []
    assert tracker.provider_attempt_count == 22


def test_attempt_wrapper_does_not_swallow_base_exception():
    class StopNow(BaseException):
        pass

    sender = ScriptedSender([StopNow()], [])
    transport = AttemptReservingTransport(sender, lambda: None)

    with pytest.raises(StopNow):
        transport.send(object())


def test_cli_validates_composition_without_executor_or_network(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo = _fixture_repo(tmp_path)
    args = _cli_args(repo)
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    monkeypatch.setattr(
        SmokeExecutor,
        "execute",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("executor called")
        ),
    )
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("socket opened")
        ),
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("urlopen called")
        ),
    )
    monkeypatch.setattr(
        "experiments.live.http_transport.OpenAICompatibleHttpTransport.send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("transport send called")
        ),
    )

    assert main(args) == 2
    assert (
        "live-smoke composition validated, execution requires M7-D.2 approval."
        in capsys.readouterr().out
    )
    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()


def test_cli_does_not_swallow_base_exception(tmp_path, monkeypatch):
    class StopNow(BaseException):
        pass

    repo = _fixture_repo(tmp_path)
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    monkeypatch.setattr(
        "experiments.live.smoke_composition.validate_live_smoke_composition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(StopNow()),
    )

    with pytest.raises(StopNow):
        main(_cli_args(repo))


def test_cli_script_entrypoint_validates_composition_and_returns_code_2(tmp_path):
    repo = _fixture_repo(tmp_path)
    project_root = Path(__file__).resolve().parents[2]
    args = _cli_args(repo)
    completed = subprocess.run(
        [sys.executable, "-B", str(project_root / "experiments" / "cli.py"), *args],
        cwd=project_root,
        env={
            "ARAG_RUN_LIVE_GATEWAY": "1",
            "ARAG_ALLOW_SMOKE_RUN": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert (
        "live-smoke composition validated, execution requires M7-D.2 approval."
        in completed.stdout
    )
    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        ("http://127.0.0.1:8787/v1", "http://localhost:8787/v1"),
        ("http://127.0.0.1:8787/v1", "http://127.0.0.1:8788/v1"),
        ("http://127.0.0.1:8787/v1", "https://example.trycloudflare.com/v1"),
        ("hermes_vertex_gateway", "other_provider"),
        ("google/gemini-3.5-flash", "other/model"),
    ],
)
def test_composition_rejects_models_yaml_mismatch(
    tmp_path,
    needle,
    replacement,
):
    repo = _fixture_repo(tmp_path)
    models_path = repo / "configs" / "models.yaml"
    models_path.write_text(
        models_path.read_text(encoding="utf-8").replace(needle, replacement),
        encoding="utf-8",
    )

    with pytest.raises((ValueError, ProviderConfigError, ExperimentConfigError)):
        _request(repo)

    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()


def test_composition_revalidates_both_environment_opt_ins(tmp_path):
    repo = _fixture_repo(tmp_path)
    request = _request(repo)

    with pytest.raises(ValueError, match="ARAG_RUN_LIVE_GATEWAY"):
        validate_live_smoke_composition(
            request,
            env={"ARAG_ALLOW_SMOKE_RUN": "1"},
        )
    with pytest.raises(ValueError, match="ARAG_ALLOW_SMOKE_RUN"):
        validate_live_smoke_composition(
            request,
            env={"ARAG_RUN_LIVE_GATEWAY": "1"},
        )

    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()


def test_composition_rejects_authorization_in_config(tmp_path):
    repo = _fixture_repo(tmp_path)
    models_path = repo / "configs" / "models.yaml"
    models_path.write_text(
        models_path.read_text(encoding="utf-8")
        + '\nauthorization: "Bearer forbidden"\n',
        encoding="utf-8",
    )

    with pytest.raises((ProviderConfigError, ExperimentConfigError)):
        _request(repo)

    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()


def test_composition_rejects_provider_runtime_override(tmp_path):
    repo = _fixture_repo(tmp_path)
    config = validate_live_smoke_composition(
        _request(repo),
        env=LIVE_ENV,
    ).config
    runtime_override = ProviderRuntimeConfig(
        provider_id="hermes_vertex_gateway",
        api_base="http://127.0.0.1:8787/v1",
        capabilities=ProviderCapabilities(True, True, True),
    )

    with pytest.raises(ValueError, match="forbids provider runtime overrides"):
        from experiments.live.smoke_composition import build_live_smoke_provider_factory

        build_live_smoke_provider_factory(
            config,
            env=LIVE_ENV,
            provider_runtime_config=runtime_override,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_provider_id", "other"),
        ("model", "other/model"),
        ("mode", "mock_run"),
    ],
)
def test_composition_rejects_mismatched_live_config(tmp_path, field, value):
    from dataclasses import replace

    repo = _fixture_repo(tmp_path)
    request = _request(repo)
    config = validate_live_smoke_composition(request, env=LIVE_ENV).config

    with pytest.raises(ValueError):
        validate_live_smoke_composition(
            request,
            env=LIVE_ENV,
            config_override=replace(config, **{field: value}),
        )

    assert not (repo / "results").exists()
    assert not (repo / "workspaces").exists()
