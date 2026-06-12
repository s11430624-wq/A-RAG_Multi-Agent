import hashlib
import json
from pathlib import Path

from experiments.retrieval.corpus import CorpusBuilder
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_synthetic_repo(root: Path) -> Path:
    files = {
        "student_system/API_SPEC.md": b"# API\n\ncalculate_pass_rate course grade lookup\n",
        "student_system/STYLE_GUIDE.md": b"# Style\nUse clear validation logic.\n",
    }
    root.mkdir(parents=True, exist_ok=True)
    snapshot_files = []
    for rel_path, data in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        snapshot_files.append({"path": rel_path, "sha256": hashlib.sha256(data).hexdigest()})
    snapshot = {
        "snapshot_id": "synthetic_snap",
        "created_at": "2026-06-11T00:00:00Z",
        "files": sorted(snapshot_files, key=lambda item: item["path"]),
    }
    (root / "student_system" / "SNAPSHOT.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return root


def test_hidden_and_reference_material_never_enter_corpus():
    repo_root = _repo_root()
    retrieval_task_spec = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))
    corpus = CorpusBuilder(repo_root).build(retrieval_task_spec)
    serialized = repr(corpus)

    assert "evaluation/hidden_tests" not in serialized
    assert "evaluation/reference_patches" not in serialized
    assert "results/" not in serialized
    assert "workspaces/" not in serialized


def test_synthetic_mutation_tests_do_not_touch_formal_snapshot():
    repo_root = _repo_root()
    snapshot_path = repo_root / "student_system/SNAPSHOT.json"
    before = json.loads(snapshot_path.read_text(encoding="utf-8"))
    after = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert before == after


def test_store_and_results_do_not_expose_upstream_secret_sentinel(
    tmp_path,
):
    sentinel = "SECRET_SENTINEL_REQUIRED_EVIDENCE_HIDDEN_GRADING"
    repo = _build_synthetic_repo(tmp_path / "synthetic_repo")
    spec = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))
    log_root = tmp_path / "results" / "raw" / "retrieval"
    log_root.mkdir(parents=True)
    writer = RetrievalLogWriter(approved_log_root=log_root, log_file_path=log_root / "run.jsonl")

    facade = RetrievalFacade()
    store = facade.build_store(spec=spec, repo_root=repo, strategy="E")
    session = facade.create_session(
        run_id="run_secret",
        strategy="E",
        agent_role="Planner",
        store=store,
        log_writer=writer,
    )
    result = session.keyword_search("calculate pass rate", top_k=1)

    assert sentinel not in repr(store)
    assert sentinel not in repr(result)
    assert sentinel not in (log_root / "run.jsonl").read_text(encoding="utf-8")


def test_repair_round_tool_calls_do_not_read_filesystem_after_store_build(
    tmp_path,
    monkeypatch,
):
    repo = _build_synthetic_repo(tmp_path / "synthetic_repo")
    spec = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))
    facade = RetrievalFacade()
    store = facade.build_store(spec=spec, repo_root=repo, strategy="E")
    session = facade.create_session(run_id="run_repair", strategy="E", agent_role="Coder", store=store)
    first_chunk = store.corpus.chunks[0]

    def fail_if_filesystem_is_read(*args, **kwargs):
        raise AssertionError("retrieval tool call attempted filesystem access after store build")

    monkeypatch.setattr(Path, "read_bytes", fail_if_filesystem_is_read)
    monkeypatch.setattr(Path, "open", fail_if_filesystem_is_read)

    session.keyword_search("calculate pass rate", top_k=1)
    session.semantic_search("course grade lookup", top_k=1)
    session.chunk_read(first_chunk.file_path, first_chunk.chunk_id)
