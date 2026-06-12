import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from experiments.strategies.models import ModelVisibleTask
from experiments.strategies.visibility import ModelVisibleTaskFactory, VisibilityError


def test_projection_exposes_only_model_visible_fields(synthetic_task_repo):
    root, task = synthetic_task_repo

    visible = ModelVisibleTaskFactory.from_task_record(task, repo_root=root)

    assert isinstance(visible, ModelVisibleTask)
    assert visible.task_id == "T01"
    serialized = repr(visible)
    for secret in (
        "SECRET_ALLOWED_CORPUS",
        "SECRET_REQUIRED_EVIDENCE",
        "SECRET_GRADING",
        "SECRET_HIDDEN",
        "SECRET_PUBLIC_PATH",
        "SECRET_PRIVATE_AUDIT",
    ):
        assert secret not in serialized
    with pytest.raises(FrozenInstanceError):
        visible.task_id = "T02"


def test_all_strategies_can_share_the_exact_same_visible_task(synthetic_task_repo):
    root, task = synthetic_task_repo
    projected = tuple(
        ModelVisibleTaskFactory.from_task_record(task, repo_root=root)
        for _strategy in ("A", "C", "E")
    )
    assert projected[0] == projected[1] == projected[2]


@pytest.mark.parametrize(
    "mutation",
    ["hash", "duplicate", "untracked", "traversal", "absolute", "utf8"],
)
def test_starter_file_attacks_fail_closed(synthetic_task_repo, mutation):
    root, task = synthetic_task_repo
    snapshot_path = root / "student_system" / "SNAPSHOT.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if mutation == "hash":
        snapshot["files"][0]["sha256"] = "0" * 64
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    elif mutation == "duplicate":
        task["starter_files"].append(task["starter_files"][0])
    elif mutation == "untracked":
        task["starter_files"] = ["student_system/src/other.py"]
    elif mutation == "traversal":
        task["starter_files"] = ["../outside.py"]
    elif mutation == "absolute":
        task["starter_files"] = [str((root / "student_system/src/main.py").resolve())]
    elif mutation == "utf8":
        raw = b"\xff"
        path = root / "student_system/src/main.py"
        path.write_bytes(raw)
        snapshot["files"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(VisibilityError):
        ModelVisibleTaskFactory.from_task_record(task, repo_root=root)
