import hashlib
from pathlib import Path

import pytest

from experiments.providers.fake import FakeProvider
from experiments.providers.models import ModelParameters, Usage
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.models import (
    ModelVisibleTask,
    SanitizedPublicFeedback,
    StarterFile,
)
from experiments.strategies.single_llm import SingleLLMStrategySession
from experiments.strategies.base import (
    StrategyFinalizationError,
    StrategySessionClosedError,
    StrategySessionSealedError,
)

DIFF = "--- a/student_system/src/main.py\n+++ b/student_system/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"


def _task():
    return ModelVisibleTask(
        "T01",
        "change main",
        (StarterFile("student_system/src/main.py", "old\n", "a" * 64),),
        ("student_system/src/main.py",),
        ("new",),
        (),
    )


def _feedback(round_index):
    text = f"public failure {round_index}"
    return SanitizedPublicFeedback(round_index, text, hashlib.sha256(text.encode()).hexdigest())


def _session(tmp_path: Path, responses=(DIFF, DIFF, DIFF)):
    provider = FakeProvider(responses=responses, usage=Usage(2, 3, 5, "provider"))
    writer = ArtifactBundleWriter(
        tmp_path / "artifacts",
        run_id="run-a",
        task_id="T01",
        strategy="A",
        model="m",
        provider_id="provider",
        seed=42,
    )
    session = SingleLLMStrategySession(
        run_id="run-a",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0.0, 0.95, 128, 5.0, 42),
        artifact_writer=writer,
    )
    return session, provider, writer


def test_strategy_a_initial_and_repairs_use_exact_schedule(tmp_path):
    session, provider, _writer = _session(tmp_path)

    initial = session.generate_initial_patch()
    repair1 = session.generate_repair_patch(_feedback(1), initial.patch)
    repair2 = session.generate_repair_patch(_feedback(2), repair1.patch)

    assert initial.patch == repair1.patch == repair2.patch == DIFF
    assert [request.call_index for request in provider.requests] == [1, 2, 3]
    assert all(request.system_prompt == "" for request in provider.requests)
    assert repair2.metrics.model_call_count == 3
    assert repair2.metrics.tool_calls == 0
    with pytest.raises(StrategySessionClosedError):
        session.generate_repair_patch(_feedback(3), repair2.patch)


def test_generate_stages_without_manifest_then_finalize_seals(tmp_path):
    session, _provider, _writer = _session(tmp_path, responses=(DIFF,))
    output = session.generate_initial_patch()

    run_root = tmp_path / "artifacts/run-a"
    assert output.metrics.model_call_count == 1
    assert not hasattr(output, "artifact_path")
    assert not (run_root / "manifest.json").exists()
    finalization = session.finalize()
    assert finalization.artifact_path == "run-a"
    assert (run_root / "manifest.json").exists()
    with pytest.raises(StrategySessionSealedError):
        session.finalize()
    with pytest.raises(StrategySessionSealedError):
        session.generate_initial_patch()


def test_finalize_before_initial_fails_and_close_rolls_back(tmp_path):
    session, _provider, _writer = _session(tmp_path, responses=(DIFF,))
    with pytest.raises(StrategyFinalizationError):
        session.finalize()
    session.close()
    assert not (tmp_path / "artifacts/run-a").exists()
    with pytest.raises(StrategySessionClosedError):
        session.generate_initial_patch()


def test_repair_rejects_non_sanitized_feedback(tmp_path):
    session, _provider, _writer = _session(tmp_path, responses=(DIFF,))
    initial = session.generate_initial_patch()
    with pytest.raises(TypeError):
        session.generate_repair_patch({"round_index": 1}, initial.patch)


def test_finalize_during_active_provider_call_fails_without_sealing(tmp_path):
    session_holder = {}

    class ReentrantProvider:
        calls = 0

        def generate(self, request):
            self.calls += 1
            if self.calls == 2:
                with pytest.raises(StrategyFinalizationError):
                    session_holder["session"].finalize()
            return FakeProvider(responses=(DIFF,), usage=Usage(1, 1, 2, "provider")).generate(request)

    writer = ArtifactBundleWriter(
        tmp_path / "artifacts",
        run_id="run-active",
        task_id="T01",
        strategy="A",
        model="m",
        provider_id="provider",
        seed=42,
    )
    session = SingleLLMStrategySession(
        run_id="run-active",
        task=_task(),
        provider=ReentrantProvider(),
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
    )
    session_holder["session"] = session

    initial = session.generate_initial_patch()
    assert session.generate_repair_patch(_feedback(1), initial.patch).patch == DIFF
    assert session.finalize().artifact_path == "run-active"
