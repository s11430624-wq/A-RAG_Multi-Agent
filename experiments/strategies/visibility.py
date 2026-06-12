from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.strategies.models import ModelVisibleTask, StarterFile

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


class VisibilityError(ValueError):
    pass


class ModelVisibleTaskFactory:
    @staticmethod
    def from_task_record(
        task_record: Mapping[str, Any],
        *,
        repo_root: Path,
    ) -> ModelVisibleTask:
        if not isinstance(task_record, Mapping):
            raise VisibilityError("task_record must be a mapping")
        root = Path(repo_root).resolve()
        snapshot_path = root / "student_system" / "SNAPSHOT.json"
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot_files = snapshot["files"]
        except Exception as exc:
            raise VisibilityError(f"invalid Snapshot: {exc}") from exc
        if not isinstance(snapshot_files, list):
            raise VisibilityError("Snapshot files must be a list")
        tracked: dict[str, str] = {}
        for item in snapshot_files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
                raise VisibilityError("invalid Snapshot file entry")
            normalized = item["path"].replace("\\", "/")
            if normalized in tracked:
                raise VisibilityError(f"duplicate Snapshot path: {normalized}")
            tracked[normalized] = item["sha256"]

        starter_paths = task_record.get("starter_files")
        if not isinstance(starter_paths, list) or not starter_paths:
            raise VisibilityError("starter_files must be a non-empty list")
        if len(starter_paths) != len(set(starter_paths)):
            raise VisibilityError("starter_files must not contain duplicates")

        starters: list[StarterFile] = []
        for value in starter_paths:
            if not isinstance(value, str):
                raise VisibilityError("starter path must be a string")
            normalized = value.replace("\\", "/")
            _assert_relative_safe(normalized)
            if normalized not in tracked:
                raise VisibilityError(f"starter file is not Snapshot tracked: {normalized}")
            target = (root / normalized).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise VisibilityError(f"starter path escapes repo: {normalized}") from exc
            try:
                raw = target.read_bytes()
            except OSError as exc:
                raise VisibilityError(f"starter file cannot be read: {normalized}") from exc
            digest = hashlib.sha256(raw).hexdigest()
            if digest != tracked[normalized]:
                raise VisibilityError(f"Snapshot hash mismatch: {normalized}")
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise VisibilityError(f"starter file is not UTF-8: {normalized}") from exc
            starters.append(StarterFile(normalized, content, digest))

        return ModelVisibleTask(
            task_id=_required_string(task_record, "task_id"),
            task_description=_required_string(task_record, "task_description"),
            starter_files=tuple(starters),
            files_to_modify=_string_tuple(task_record, "files_to_modify"),
            expected_behavior=_string_tuple(task_record, "expected_behavior"),
            forbidden_behaviors=_string_tuple(task_record, "forbidden_behaviors"),
        )


def _assert_relative_safe(path: str) -> None:
    parts = tuple(part for part in path.split("/") if part not in ("", "."))
    if path.startswith("/") or _WINDOWS_ABSOLUTE.match(path) or ".." in parts:
        raise VisibilityError(f"unsafe starter path: {path}")


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise VisibilityError(f"{key} must be a non-empty string")
    return value


def _string_tuple(mapping: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise VisibilityError(f"{key} must be a list of strings")
    return tuple(value)
