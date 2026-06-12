import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_task_repo(tmp_path: Path):
    root = tmp_path / "repo"
    source = root / "student_system" / "src" / "main.py"
    source.parent.mkdir(parents=True)
    raw = b"def value():\n    return 1\n"
    source.write_bytes(raw)
    snapshot = {
        "snapshot_id": "synthetic",
        "files": [
            {
                "path": "student_system/src/main.py",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
    }
    (root / "student_system" / "SNAPSHOT.json").write_text(
        json.dumps(snapshot),
        encoding="utf-8",
    )
    task = {
        "task_id": "T01",
        "task_description": "visible task",
        "starter_files": ["student_system/src/main.py"],
        "files_to_modify": ["student_system/src/main.py"],
        "expected_behavior": ["works"],
        "forbidden_behaviors": ["no hardcode"],
        "allowed_corpus": ["SECRET_ALLOWED_CORPUS"],
        "required_evidence": ["SECRET_REQUIRED_EVIDENCE"],
        "grading": {"secret": "SECRET_GRADING"},
        "hidden_test_id": "SECRET_HIDDEN",
        "public_test_paths": ["SECRET_PUBLIC_PATH"],
        "private_audit": "SECRET_PRIVATE_AUDIT",
    }
    return root, task
