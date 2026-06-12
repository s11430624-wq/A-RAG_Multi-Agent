import hashlib
from pathlib import Path

from experiments.providers.fake import FakeProvider
from experiments.providers.models import ModelParameters, Usage
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.models import ModelVisibleTask, SanitizedPublicFeedback, StarterFile
from experiments.strategies.multi_agent import MultiAgentStrategySession

PLAN = '{"files_to_modify":["student_system/src/main.py"],"implementation_steps":["change"],"risks":[]}'
DIFF = "--- a/student_system/src/main.py\n+++ b/student_system/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"
REVIEW_PASS = '{"issues":[],"verdict":"pass"}'
REVIEW_FAIL = '{"issues":[{"category":"correctness","evidence_chunk_ids":[],"message":"check edge"}],"verdict":"fail"}'


def _task():
    return ModelVisibleTask(
        "T01",
        "change",
        (StarterFile("student_system/src/main.py", "old\n", "a" * 64),),
        ("student_system/src/main.py",),
        ("new",),
        (),
    )


def _feedback(index):
    text = f"failure {index}"
    return SanitizedPublicFeedback(index, text, hashlib.sha256(text.encode()).hexdigest())


def _session(tmp_path: Path, responses):
    provider = FakeProvider(responses=responses, usage=Usage(1, 1, 2, "provider"))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-c", task_id="T01", strategy="C", model="m", provider_id="provider", seed=42)
    session = MultiAgentStrategySession(
        run_id="run-c",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
    )
    return session, provider


def test_strategy_c_fixed_initial_order_and_patch_identity(tmp_path):
    session, provider = _session(tmp_path, (PLAN, DIFF, REVIEW_PASS))

    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.reviewer_verdict.verdict == "PASS"
    assert [record.role for record in output.metrics.call_records] == ["Planner", "Coder", "Reviewer"]
    assert [request.call_index for request in provider.requests] == [1, 2, 3]
    assert output.metrics.tool_calls == 0


def test_reviewer_fail_does_not_trigger_pretest_coder_regeneration(tmp_path):
    session, provider = _session(tmp_path, (PLAN, DIFF, REVIEW_FAIL))
    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.reviewer_verdict.verdict == "FAIL"
    assert len(provider.requests) == 3


def test_repairs_are_coder_only_and_total_schedule_is_five(tmp_path):
    session, provider = _session(tmp_path, (PLAN, DIFF, REVIEW_FAIL, DIFF, DIFF))
    initial = session.generate_initial_patch()
    repair1 = session.generate_repair_patch(_feedback(1), initial.patch)
    repair2 = session.generate_repair_patch(_feedback(2), repair1.patch)

    assert [record.role for record in repair2.metrics.call_records] == [
        "Planner",
        "Coder",
        "Reviewer",
        "Coder",
        "Coder",
    ]
    assert len(provider.requests) == 5


def test_strategy_c_module_has_no_retrieval_dependency():
    import experiments.strategies.multi_agent as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "RetrievalFacade" not in source
    assert "RetrievalSession" not in source
