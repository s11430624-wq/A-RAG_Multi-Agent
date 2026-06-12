from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

from experiments.strategies.models import ArtifactFileHash, StrategyFinalization, StrategyMetrics


class ArtifactWriteError(RuntimeError):
    pass


class ArtifactBundleWriter:
    def __init__(
        self,
        approved_root: Path,
        *,
        run_id: str,
        task_id: str,
        strategy: str,
        model: str,
        provider_id: str,
        seed: int,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
            raise ArtifactWriteError("run_id is unsafe")
        if not isinstance(provider_id, str) or not provider_id:
            raise ArtifactWriteError("provider_id is required")
        self.approved_root = Path(approved_root).resolve()
        self.run_root = (self.approved_root / run_id).resolve()
        self._assert_under_root(self.run_root)
        self.run_id = run_id
        self.task_id = task_id
        self.strategy = strategy
        self.model = model
        self.provider_id = provider_id
        self.seed = seed
        self._files: dict[str, str] = {}
        self._finalized = False
        self._closed = False

    def stage_bytes(self, relative_path: str, content: bytes) -> None:
        if self._closed or self._finalized:
            raise ArtifactWriteError("artifact bundle is closed or finalized")
        normalized = Path(relative_path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts or normalized.as_posix() == "manifest.json":
            raise ArtifactWriteError("unsafe artifact path")
        target = (self.run_root / normalized).resolve()
        self._assert_under_root(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as handle:
                handle.write(content)
                handle.flush()
        except OSError as exc:
            raise ArtifactWriteError(f"artifact stage failed: {exc}") from exc
        self._files[normalized.as_posix()] = hashlib.sha256(content).hexdigest()

    def finalize(self, metrics: StrategyMetrics) -> StrategyFinalization:
        if self._closed or self._finalized:
            raise ArtifactWriteError("artifact bundle cannot be finalized again")
        files: list[ArtifactFileHash] = []
        for relative_path, expected in sorted(self._files.items()):
            target = self.run_root / relative_path
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ArtifactWriteError(f"artifact hash mismatch: {relative_path}")
            files.append(ArtifactFileHash(relative_path, expected))
        manifest = {
            "manifest_version": "m5-artifact-v1",
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "run_id": self.run_id,
            "task_id": self.task_id,
            "strategy": self.strategy,
            "model": self.model,
            "provider_id": self.provider_id,
            "seed": self.seed,
            "template_hashes": sorted(
                {item.template_name: item.template_hash for item in metrics.call_records}.items()
            ),
            "rendered_prompt_hashes": [
                [item.call_index, item.rendered_prompt_hash] for item in metrics.call_records
            ],
            "response_hashes": [
                [item.call_index, item.response_hash] for item in metrics.call_records
            ],
            "patch_hashes": [
                [item.relative_path, item.sha256]
                for item in files
                if item.relative_path.startswith("patches/")
            ],
            "provider_request_ids": [
                [item.call_index, item.provider_request_id] for item in metrics.call_records
            ],
            "call_records": [asdict(item) for item in metrics.call_records],
            "attempt_records": [asdict(item) for item in metrics.attempt_records],
            "failure_audit_records": [asdict(item) for item in metrics.failure_audit_records],
            "usage_complete": metrics.input_tokens is not None and metrics.output_tokens is not None,
            "retry_count": sum(item.retry_count for item in metrics.call_records),
            "provider_attempt_count": metrics.provider_attempt_count,
            "failed_provider_call_count": metrics.failed_provider_call_count,
            "retrieval_log_relative_path": None,
            "artifact_files": [asdict(item) for item in files],
        }
        data = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        manifest_path = self.run_root / "manifest.json"
        try:
            with manifest_path.open("xb") as handle:
                handle.write(data)
                handle.flush()
        except OSError as exc:
            raise ArtifactWriteError(f"manifest write failed: {exc}") from exc
        self._finalized = True
        return StrategyFinalization(
            metrics=metrics,
            artifact_path=self.run_id,
            manifest_sha256=hashlib.sha256(data).hexdigest(),
        )

    def close(self) -> None:
        if self._closed:
            return
        if not self._finalized and self.run_root.exists():
            self._assert_under_root(self.run_root)
            try:
                shutil.rmtree(self.run_root)
            except OSError as exc:
                raise ArtifactWriteError(f"artifact rollback failed; artifact_integrity_unknown=True: {exc}") from exc
        self._closed = True

    def _assert_under_root(self, target: Path) -> None:
        try:
            target.relative_to(self.approved_root)
        except ValueError as exc:
            raise ArtifactWriteError("artifact path escapes approved root") from exc
