import hashlib
import json
from pathlib import Path

import pytest

from experiments.retrieval.models import RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def retrieval_log_schema(repo_root):
    with open(repo_root / "contracts/retrieval-log.schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def retrieval_log_path(tmp_path):
    return tmp_path / "retrieval.jsonl"


@pytest.fixture
def approved_log_root(tmp_path):
    root = tmp_path / "results" / "raw" / "retrieval"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def full_task_with_secret_sentinel():
    sentinel = "SECRET_SENTINEL_REQUIRED_EVIDENCE_HIDDEN_GRADING"
    return {
        "task_id": "T01",
        "allowed_corpus": ["student_system/API_SPEC.md"],
        "required_evidence": [sentinel],
        "grading": {"secret": sentinel},
        "hidden_test_id": sentinel,
        "secret_sentinel": sentinel,
    }


@pytest.fixture
def retrieval_task_spec(full_task_with_secret_sentinel):
    return RetrievalTaskSpec(
        task_id=full_task_with_secret_sentinel["task_id"],
        allowed_corpus=tuple(full_task_with_secret_sentinel["allowed_corpus"]),
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_synthetic_repo(root: Path, *, newline: str = "\n", extra_files: dict[str, bytes] | None = None) -> Path:
    files = {
        "student_system/API_SPEC.md": f"# API{newline}{newline}calculate_pass_rate course grade lookup{newline}".encode("utf-8"),
        "student_system/STYLE_GUIDE.md": f"# Style{newline}Use clear validation logic.{newline}".encode("utf-8"),
        "student_system/src/result_formatter.py": b"def format_result(value):\n    return str(value)\n",
        "student_system/docs/runtime_notes.md": b"# Runtime\nworkspace isolation notes\n",
    }
    if extra_files:
        files.update(extra_files)

    root.mkdir(parents=True, exist_ok=True)
    snapshot_files = []
    for rel_path, data in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        snapshot_files.append({"path": rel_path, "sha256": _sha256_bytes(data)})

    snapshot = {
        "snapshot_id": "synthetic_snap",
        "created_at": "2026-06-11T00:00:00Z",
        "files": sorted(snapshot_files, key=lambda item: item["path"]),
    }
    snapshot_path = root / "student_system" / "SNAPSHOT.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


@pytest.fixture
def synthetic_repo_root(tmp_path):
    return build_synthetic_repo(tmp_path / "synthetic_repo")


@pytest.fixture(name="build_synthetic_repo")
def build_synthetic_repo_fixture():
    return build_synthetic_repo


@pytest.fixture
def synthetic_retrieval_task_spec():
    return RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))


@pytest.fixture
def strategy_e_store(retrieval_task_spec, repo_root):
    return RetrievalFacade().build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")


@pytest.fixture
def strategy_e_session(strategy_e_store):
    return RetrievalFacade().create_session(
        run_id="run_t01",
        strategy="E",
        agent_role="Planner",
        store=strategy_e_store,
    )
