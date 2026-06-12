from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from experiments.retrieval.chunking import chunk_file_text, count_lines, normalize_text
from experiments.retrieval.guards import assert_corpus_path_allowed, assert_resolved_under_base
from experiments.retrieval.models import (
    CorpusDecodeError,
    CorpusFile,
    CorpusPathError,
    FrozenCorpus,
    RetrievalTaskSpec,
    SnapshotIntegrityError,
)

MAX_CORPUS_FILE_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CorpusBuilder:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.snapshot_path = self.repo_root / "student_system" / "SNAPSHOT.json"

    def build(self, spec: RetrievalTaskSpec) -> FrozenCorpus:
        if not isinstance(spec, RetrievalTaskSpec):
            raise CorpusPathError("CorpusBuilder requires RetrievalTaskSpec")
        if not spec.allowed_corpus:
            raise CorpusPathError("allowed_corpus must not be empty")
        if len(set(spec.allowed_corpus)) != len(spec.allowed_corpus):
            raise CorpusPathError("allowed_corpus must not contain duplicate paths")

        snapshot = self._load_snapshot()
        snapshot_id = snapshot["snapshot_id"]
        snapshot_files = self._snapshot_file_map(snapshot)

        corpus_files: list[CorpusFile] = []
        all_chunks = []
        for rel_path in sorted(spec.allowed_corpus):
            normalized_path = assert_corpus_path_allowed(rel_path)
            if normalized_path not in snapshot_files:
                raise CorpusPathError(f"allowed corpus file is not snapshot tracked: {normalized_path}")
            target = self.repo_root / normalized_path
            assert_resolved_under_base(target, self.repo_root)
            raw = target.read_bytes()
            if len(raw) > MAX_CORPUS_FILE_BYTES:
                raise CorpusPathError(f"corpus file exceeds 1 MiB: {normalized_path}")
            snapshot_sha256 = hashlib.sha256(raw).hexdigest()
            expected_sha256 = snapshot_files[normalized_path]
            if snapshot_sha256 != expected_sha256:
                raise SnapshotIntegrityError(f"snapshot hash mismatch for {normalized_path}")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CorpusDecodeError(f"corpus file is not valid UTF-8: {normalized_path}") from exc
            normalized_text = normalize_text(text)
            normalized_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
            corpus_file = CorpusFile(
                file_path=normalized_path,
                snapshot_sha256=snapshot_sha256,
                normalized_sha256=normalized_sha256,
                text=normalized_text,
                byte_length=len(raw),
                line_count=count_lines(normalized_text),
            )
            corpus_files.append(corpus_file)
            all_chunks.extend(chunk_file_text(normalized_path, normalized_text))

        return FrozenCorpus(
            task_id=spec.task_id,
            snapshot_id=snapshot_id,
            files=tuple(corpus_files),
            chunks=tuple(all_chunks),
            corpus_hash=_canonical_corpus_hash(corpus_files),
        )

    def _load_snapshot(self) -> dict:
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception as exc:
            raise SnapshotIntegrityError(f"failed to load snapshot: {exc}") from exc
        if not isinstance(snapshot, dict) or "snapshot_id" not in snapshot or "files" not in snapshot:
            raise SnapshotIntegrityError("snapshot missing required top-level fields")
        if not isinstance(snapshot["files"], list):
            raise SnapshotIntegrityError("snapshot files must be a list")
        return snapshot

    def _snapshot_file_map(self, snapshot: dict) -> dict[str, str]:
        seen: dict[str, str] = {}
        for item in snapshot["files"]:
            if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
                raise SnapshotIntegrityError("snapshot file entry missing path or sha256")
            rel_path = str(item["path"]).replace("\\", "/")
            digest = str(item["sha256"])
            if rel_path in seen:
                raise SnapshotIntegrityError(f"duplicate snapshot path: {rel_path}")
            if not SHA256_RE.match(digest):
                raise SnapshotIntegrityError(f"illegal snapshot sha256 for {rel_path}")
            seen[rel_path] = digest
        return seen


def _canonical_corpus_hash(files: list[CorpusFile]) -> str:
    entries = []
    for item in sorted(files, key=lambda corpus_file: corpus_file.file_path):
        entries.append(
            json.dumps(
                {
                    "file_path": item.file_path,
                    "normalized_sha256": item.normalized_sha256,
                    "snapshot_sha256": item.snapshot_sha256,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    payload = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
