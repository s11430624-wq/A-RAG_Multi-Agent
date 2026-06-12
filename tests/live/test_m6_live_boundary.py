from __future__ import annotations

import importlib
from pathlib import Path
import socket

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_importing_m6_cli_opens_no_network(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network opened")))

    module = importlib.import_module("experiments.cli")

    assert hasattr(module, "main")


def test_live_run_fails_closed_without_gateway_opt_in(project_root, monkeypatch, capsys):
    from experiments.cli import main

    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)

    exit_code = main(["live-run", "--repo-root", str(project_root)])

    assert exit_code == 2
    assert "configuration error" in capsys.readouterr().out


def test_dry_run_with_credentials_present_does_not_open_network(project_root, monkeypatch):
    from experiments.cli import main

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-read")
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network opened")))

    assert main(["dry-run", "--repo-root", str(project_root)]) == 0
