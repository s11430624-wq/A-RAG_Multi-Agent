from __future__ import annotations

import json
import hashlib
import os
import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from jsonschema import validate, ValidationError

@dataclass(frozen=True)
class SmokeGateReport:
    report_version: str
    generated_at: str
    smoke_experiment_id: str
    model: str
    provider_id: str
    seed: int
    source_jsonl_relative_path: str
    source_jsonl_sha256: str
    artifact_manifest_set_sha256: str
    retrieval_log_set_sha256: str
    attempted_runs: int
    written_runs: int
    valid_runs: int
    infra_failures: int
    schema_valid: bool
    artifacts_valid: bool
    retrieval_logs_valid: bool
    usage_complete: bool
    leakage_free: bool
    resume_verified: bool
    total_input_tokens: int
    total_output_tokens: int
    total_provider_calls: int
    cost_known: bool
    estimated_cost: float | None
    automated_gate_passed: bool
    risk_flags: tuple[str, ...]
    rejection_reasons: tuple[str, ...]

    def to_canonical_json(self) -> bytes:
        """Serializes with canonical UTF-8 JSON, sorted keys, compact separators, final LF."""
        data = {}
        for k, v in self.__dict__.items():
            if isinstance(v, tuple):
                data[k] = list(v)
            else:
                data[k] = v
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return (json_str + "\n").encode("utf-8")

    def write_to_file(self, path: Path) -> None:
        """Writes report using exclusive-create (x mode) to prevent overwrite."""
        canonical_bytes = self.to_canonical_json()
        with open(path, "xb") as f:
            f.write(canonical_bytes)


@dataclass(frozen=True)
class LeakageEvidence:
    smoke_experiment_id: str
    source_jsonl_sha256: str
    scanned_files: tuple[str, ...]
    is_clean: bool
    audited_files_hash: str
    auditor_version: str


@dataclass(frozen=True)
class ResumeEvidence:
    smoke_experiment_id: str
    completed_run_ids: tuple[str, ...]
    is_valid: bool
    audited_files_hash: str
    auditor_version: str
    source_jsonl_sha256: str


@dataclass(frozen=True)
class FullRunApproval:
    approved_smoke_report_path: str = ""
    smoke_report_sha256: str = ""
    smoke_experiment_id: str = ""
    full_experiment_id: str = ""
    approved_token_budget_input: int = 0
    approved_token_budget_output: int = 0
    approved_wall_clock_seconds: float = 0.0
    allow_unknown_cost: bool = False
    human_approval: str = "FULL_RUN"






def check_symlinks_and_escapes(path: Path, root: Path) -> None:
    # 1. Path escape check
    try:
        resolved_path = Path(path).resolve()
        resolved_root = Path(root).resolve()
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path escape detected: {path} is outside {root}") from exc

    # 2. Symlink check in all components from path down to root
    curr = Path(path).absolute()
    root_abs = Path(root).absolute()
    while curr != curr.parent:
        # Check if the directory/file itself is a symlink
        if os.path.islink(curr):
            raise ValueError(f"Symlink detected in path: {curr}")
        if curr == root_abs:
            break
        curr = curr.parent


class LeakageAuditor:
    def __init__(
        self,
        repo_root: Path,
        auditor_version: str = "1.0",
        *,
        artifact_root: Path | None = None,
        retrieval_log_root: Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.auditor_version = auditor_version
        self.artifact_root = (
            Path(artifact_root).resolve()
            if artifact_root is not None
            else self.repo_root / "results" / "raw" / "artifacts"
        )
        self.retrieval_log_root = (
            Path(retrieval_log_root).resolve()
            if retrieval_log_root is not None
            else self.repo_root / "results" / "raw" / "retrieval" / "__experiment__"
        )

    def audit_leakage(self, smoke_experiment_id: str, raw_jsonl_path: Path) -> LeakageEvidence:
        raw_jsonl_path = Path(raw_jsonl_path).resolve()
        check_symlinks_and_escapes(raw_jsonl_path, self.repo_root)
        
        # 1. Get raw jsonl hash
        jsonl_bytes = raw_jsonl_path.read_bytes()
        jsonl_sha = hashlib.sha256(jsonl_bytes).hexdigest()
        
        # 2. Find all physical artifact files for this experiment
        artifacts_dir = self.artifact_root
        check_symlinks_and_escapes(artifacts_dir, self.repo_root)
        
        scanned_paths = [raw_jsonl_path]
        if artifacts_dir.exists():
            candidate_dirs = (
                tuple(item for item in artifacts_dir.iterdir() if item.is_dir() and item.name.startswith(smoke_experiment_id))
                if artifacts_dir.name != smoke_experiment_id
                else tuple(item for item in artifacts_dir.iterdir() if item.is_dir())
            )
            for item in candidate_dirs:
                check_symlinks_and_escapes(item, artifacts_dir)
                    
                def collect_files(d: Path) -> list[Path]:
                    files = []
                    for entry in os.scandir(d):
                        entry_path = Path(entry.path)
                        check_symlinks_and_escapes(entry_path, d)
                        if entry.is_symlink():
                            raise ValueError(f"Symlink/junction detected: {entry.path}")
                        if entry.is_file():
                            files.append(entry_path)
                        elif entry.is_dir():
                            files.extend(collect_files(entry_path))
                    return files
                    
                scanned_paths.extend(collect_files(item))

        retrieval_root = self.retrieval_log_root
        if retrieval_root.name == "__experiment__":
            retrieval_root = retrieval_root.parent / smoke_experiment_id
        check_symlinks_and_escapes(retrieval_root, self.repo_root)
        if retrieval_root.exists():
            for item in retrieval_root.iterdir():
                if item.is_file():
                    check_symlinks_and_escapes(item, retrieval_root)
                    scanned_paths.append(item)
        
        # Convert to relative posix paths
        scanned_files = []
        for p in scanned_paths:
            rel = p.relative_to(self.repo_root).as_posix()
            scanned_files.append(rel)
        scanned_files = tuple(sorted(set(scanned_files)))
        
        if not scanned_files:
            raise ValueError("scanned_files cannot be empty")
            
        # 3. Check for leakage in all files
        is_clean = True
        leakage_patterns = [
            re.compile(rb"--- a/"),
            re.compile(rb"\+\+\+ b/"),
            re.compile(rb"evaluation/reference_patches"),
            re.compile(rb"(?i)authorization\s*[:=]\s*bearer"),
            re.compile(rb"(?i)(api[_-]?key|credential|secret)\s*[:=]"),
            re.compile(rb"(?i)(tests[/\\]hidden|hidden[/\\]tests)"),
        ]
        
        file_hashes = {}
        for rel_path in scanned_files:
            full_path = self.repo_root / rel_path
            content = full_path.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            file_hashes[rel_path] = sha
            
            # Check leakage
            for pattern in leakage_patterns:
                if pattern.search(content):
                    is_clean = False
                    
        # 4. Compute audited_files_hash
        canonical_data = {
            "smoke_experiment_id": smoke_experiment_id,
            "source_jsonl_sha256": jsonl_sha,
            "scanned_files": scanned_files,
            "is_clean": is_clean,
            "auditor_version": self.auditor_version,
            "file_hashes": [file_hashes[k] for k in sorted(file_hashes.keys())]
        }
        canonical_str = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
        audited_files_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        
        return LeakageEvidence(
            smoke_experiment_id=smoke_experiment_id,
            source_jsonl_sha256=jsonl_sha,
            scanned_files=scanned_files,
            is_clean=is_clean,
            audited_files_hash=audited_files_hash,
            auditor_version=self.auditor_version,
        )


class ResumeAuditor:
    def __init__(
        self,
        repo_root: Path,
        auditor_version: str = "1.0",
        *,
        artifact_root: Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.auditor_version = auditor_version
        self.artifact_root = (
            Path(artifact_root).resolve()
            if artifact_root is not None
            else self.repo_root / "results" / "raw" / "artifacts"
        )

    def audit_resume(self, smoke_experiment_id: str, raw_jsonl_path: Path) -> ResumeEvidence:
        raw_jsonl_path = Path(raw_jsonl_path).resolve()
        check_symlinks_and_escapes(raw_jsonl_path, self.repo_root)
        
        # 1. Get raw jsonl hash
        jsonl_bytes = raw_jsonl_path.read_bytes()
        jsonl_sha = hashlib.sha256(jsonl_bytes).hexdigest()
        
        # 2. Read raw jsonl lines to find completed run IDs
        completed_run_ids = []
        is_valid = True
        try:
            lines = jsonl_bytes.decode("utf-8").splitlines()
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                data = json.loads(line_str)
                run_id = data.get("run_id")
                if run_id:
                    completed_run_ids.append(run_id)
        except Exception:
            is_valid = False
            
        completed_run_ids = tuple(sorted(completed_run_ids))
        
        # 3. Verify that each run's artifact directory and manifest exist
        artifacts_dir = self.artifact_root
        check_symlinks_and_escapes(artifacts_dir, self.repo_root)
        
        audited_paths = [raw_jsonl_path]
        for run_id in completed_run_ids:
            run_dir = artifacts_dir / run_id
            manifest_file = run_dir / "manifest.json"
            if not manifest_file.is_file():
                is_valid = False
            else:
                try:
                    check_symlinks_and_escapes(manifest_file, artifacts_dir)
                    audited_paths.append(manifest_file)
                except Exception:
                    is_valid = False
                    
        # Sort audited paths and compute relative paths
        scanned_files = []
        for p in audited_paths:
            rel = p.relative_to(self.repo_root).as_posix()
            scanned_files.append(rel)
        scanned_files = tuple(sorted(set(scanned_files)))
        
        # 4. Compute file hashes for canonical hash
        file_hashes = {}
        for rel_path in scanned_files:
            full_path = self.repo_root / rel_path
            if full_path.is_file():
                file_sha = hashlib.sha256(full_path.read_bytes()).hexdigest()
            else:
                file_sha = ""
                is_valid = False
            file_hashes[rel_path] = file_sha
            
        # Compute audited_files_hash
        canonical_data = {
            "smoke_experiment_id": smoke_experiment_id,
            "source_jsonl_sha256": jsonl_sha,
            "completed_run_ids": completed_run_ids,
            "is_valid": is_valid,
            "auditor_version": self.auditor_version,
            "file_hashes": [file_hashes[k] for k in sorted(file_hashes.keys())]
        }
        canonical_str = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
        audited_files_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        
        return ResumeEvidence(
            smoke_experiment_id=smoke_experiment_id,
            completed_run_ids=completed_run_ids,
            is_valid=is_valid,
            audited_files_hash=audited_files_hash,
            auditor_version=self.auditor_version,
            source_jsonl_sha256=jsonl_sha,
        )


class SmokeGateAuditor:
    def __init__(
        self,
        raw_jsonl_path: Path,
        repo_root: Path,
        *,
        artifact_root: Path | None = None,
        retrieval_log_root: Path | None = None,
        leakage_evidence: LeakageEvidence | None = None,
        resume_evidence: ResumeEvidence | None = None,
    ) -> None:
        self.raw_jsonl_path = Path(raw_jsonl_path).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.artifact_root = Path(artifact_root).resolve() if artifact_root is not None else None
        self.retrieval_log_root = Path(retrieval_log_root).resolve() if retrieval_log_root is not None else None
        self.leakage_evidence = leakage_evidence
        self.resume_evidence = resume_evidence

    def calculate_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def audit_smoke_runs(self) -> SmokeGateReport:
        # 1. Verify JSONL path safety and check symlinks
        check_symlinks_and_escapes(self.raw_jsonl_path, self.repo_root)

        if not self.raw_jsonl_path.is_file():
            raise ValueError(f"JSONL is not a file or is missing: {self.raw_jsonl_path}")

        jsonl_bytes = self.raw_jsonl_path.read_bytes()
        jsonl_sha = hashlib.sha256(jsonl_bytes).hexdigest()

        # Parse JSONL records
        lines = jsonl_bytes.decode("utf-8").splitlines()
        records = []
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
                records.append(rec)
            except Exception as exc:
                raise ValueError(f"Invalid JSON at line {idx+1}: {exc}") from exc

        # Verify exactly 3 records
        if len(records) != 3:
            raise ValueError(f"Expected exactly 3 runs in smoke JSONL, found {len(records)}")

        # Load result schema
        result_schema_path = self.repo_root / "contracts" / "result.schema.json"
        check_symlinks_and_escapes(result_schema_path, self.repo_root)
        with open(result_schema_path, "r", encoding="utf-8") as f:
            result_schema = json.load(f)

        # Validate schema, valid_run, infra_error
        schema_valid = True
        rejection_reasons = []
        strategies_seen = set()
        model = None
        seed = None
        smoke_experiment_id = None
        total_input_tokens = 0
        total_output_tokens = 0
        total_provider_calls = 0
        valid_runs_count = 0
        infra_failures_count = 0
        usage_complete = True

        for idx, rec in enumerate(records):
            # Schema check
            try:
                validate(instance=rec, schema=result_schema)
            except ValidationError as exc:
                schema_valid = False
                rejection_reasons.append(f"Record {idx} schema validation failed: {exc.message}")

            # Check task ID must be T01
            task_id = rec.get("task_id")
            if task_id != "T01":
                raise ValueError(f"Expected task_id T01, got {task_id}")

            # Check Strategy
            strategy = rec.get("strategy")
            if strategy in strategies_seen:
                raise ValueError(f"Duplicate strategy {strategy} in smoke runs")
            if strategy not in ("A", "C", "E"):
                raise ValueError(f"Unexpected strategy {strategy} in smoke runs")
            strategies_seen.add(strategy)

            # Check consistency of model and seed
            rec_model = rec.get("model")
            if model is None:
                model = rec_model
            elif rec_model != model:
                raise ValueError("Model mismatch between runs")

            rec_seed = rec.get("seed")
            if seed is None:
                seed = rec_seed
            elif rec_seed != seed:
                raise ValueError("Seed mismatch between runs")
            if rec_model != "google/gemini-3.5-flash":
                raise ValueError(f"Unexpected smoke model: {rec_model}")
            if rec_seed != 42:
                raise ValueError(f"Unexpected smoke seed: {rec_seed}")

            # Parse run ID parts
            run_id = rec.get("run_id")
            parts = run_id.split("__")
            if len(parts) < 3:
                raise ValueError(f"Invalid run_id structure: {run_id}")
            rec_exp_id = parts[0]
            if smoke_experiment_id is None:
                smoke_experiment_id = rec_exp_id
            elif rec_exp_id != smoke_experiment_id:
                raise ValueError("Experiment ID mismatch between runs")

            # Check valid_run and infra_error
            if rec.get("valid_run") is True:
                valid_runs_count += 1
            else:
                infra_failures_count += 1

            if rec.get("infra_error") is True:
                infra_failures_count += 1

            # Check token usage
            input_tok = rec.get("input_tokens")
            output_tok = rec.get("output_tokens")
            if not isinstance(input_tok, int) or not isinstance(output_tok, int) or input_tok <= 0 or output_tok <= 0:
                usage_complete = False
            else:
                total_input_tokens += input_tok
                total_output_tokens += output_tok

            tool_calls = rec.get("tool_calls")
            if strategy in ("A", "C") and tool_calls != 0:
                raise ValueError(f"Strategy {strategy} must have zero retrieval tool calls")
            if strategy == "E" and (not isinstance(tool_calls, int) or tool_calls <= 0):
                raise ValueError("Strategy E requires retrieval tool calls")

        if strategies_seen != {"A", "C", "E"}:
            raise ValueError(f"Expected strategies {{'A', 'C', 'E'}}, got {strategies_seen}")

        # Scan artifact directories (check for duplicates, extras, escapes, symlinks)
        artifacts_dir = self.artifact_root or self.repo_root / "results" / "raw" / "artifacts"
        check_symlinks_and_escapes(artifacts_dir, self.repo_root)

        expected_artifact_paths = {rec["artifact_path"] for rec in records if rec.get("artifact_path")}
        if len(expected_artifact_paths) != 3:
            raise ValueError("Missing artifact paths in raw results")

        # Find actual directories under artifacts_dir starting with smoke_experiment_id
        actual_dirs = []
        if artifacts_dir.exists():
            for item in artifacts_dir.iterdir():
                if item.is_dir() and item.name.startswith(smoke_experiment_id):
                    check_symlinks_and_escapes(item, artifacts_dir)
                    actual_dirs.append(item.name)

        # Enforce exact artifact file set (no extra, no missing)
        if set(actual_dirs) != expected_artifact_paths:
            extra = set(actual_dirs) - expected_artifact_paths
            missing = expected_artifact_paths - set(actual_dirs)
            if extra:
                raise ValueError(f"Extra artifact directory detected: {extra}")
            if missing:
                raise ValueError(f"Missing expected artifact directory: {missing}")

        # Validate manifest files
        manifest_items = []
        artifacts_valid = True
        manifest_provider_id = None
        for rec in records:
            art_path = rec["artifact_path"]
            manifest_file = artifacts_dir / art_path / "manifest.json"
            check_symlinks_and_escapes(manifest_file, artifacts_dir)
            if not manifest_file.is_file():
                artifacts_valid = False
                rejection_reasons.append(f"Missing manifest.json for run {rec['run_id']}")
                continue

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception as exc:
                artifacts_valid = False
                rejection_reasons.append(f"Invalid JSON in manifest.json for run {rec['run_id']}: {exc}")
                continue

            rec_provider_id = manifest_data.get("provider_id")
            if not rec_provider_id:
                raise ValueError("Manifest missing provider_id")
            if manifest_provider_id is None:
                manifest_provider_id = rec_provider_id
            elif rec_provider_id != manifest_provider_id:
                raise ValueError(f"Provider ID mismatch between manifests: {rec_provider_id} vs {manifest_provider_id}")

            # Strict manifest verification
            if manifest_data.get("manifest_version") != "m5-artifact-v1":
                raise ValueError(f"Invalid manifest version: {manifest_data.get('manifest_version')}")

            if manifest_data.get("run_id") != rec.get("run_id"):
                raise ValueError("Manifest run_id mismatch")
            if manifest_data.get("task_id") != rec.get("task_id"):
                raise ValueError("Manifest task_id mismatch")
            if manifest_data.get("strategy") != rec.get("strategy"):
                raise ValueError("Manifest strategy mismatch")
            if manifest_data.get("model") != rec.get("model"):
                raise ValueError("Manifest model mismatch")
            if manifest_data.get("seed") != rec.get("seed"):
                raise ValueError("Manifest seed mismatch")

            if manifest_data.get("usage_complete") is not True:
                raise ValueError("Manifest usage_complete is not True")

            artifact_files = manifest_data.get("artifact_files")
            if not isinstance(artifact_files, list):
                raise ValueError("Manifest artifact_files must be a list")

            seen_paths = set()
            for f_info in artifact_files:
                if not isinstance(f_info, dict):
                    raise ValueError("artifact_files entry must be a dictionary")
                rel_path = f_info.get("relative_path")
                sha = f_info.get("sha256")
                if not isinstance(rel_path, str) or not isinstance(sha, str):
                    raise ValueError("relative_path and sha256 in artifact_files must be strings")
                if Path(rel_path).is_absolute() or ".." in Path(rel_path).parts:
                    raise ValueError(f"Unsafe path in artifact_files: {rel_path}")
                if rel_path in seen_paths:
                    raise ValueError(f"Duplicate path in artifact_files: {rel_path}")
                seen_paths.add(rel_path)

            # Walk directory physically and check for symlinks/escapes/extra/missing files
            run_artifact_dir = artifacts_dir / art_path
            check_symlinks_and_escapes(run_artifact_dir, artifacts_dir)

            def scan_directory(dir_path: Path, root_path: Path) -> set[Path]:
                found_files = set()
                for entry in os.scandir(dir_path):
                    entry_path = Path(entry.path)
                    check_symlinks_and_escapes(entry_path, root_path)
                    if entry.is_symlink():
                        raise ValueError(f"Symlink/junction detected: {entry.path}")
                    if entry.is_file():
                        found_files.add(entry_path)
                    elif entry.is_dir():
                        found_files.update(scan_directory(entry_path, root_path))
                return found_files

            physical_files = scan_directory(run_artifact_dir, run_artifact_dir)
            manifest_json_path = (run_artifact_dir / "manifest.json").resolve()
            
            resolved_physical = set()
            for p in physical_files:
                resolved_p = p.resolve()
                if resolved_p != manifest_json_path:
                    resolved_physical.add(resolved_p)

            expected_physical_paths = set()
            for f_info in artifact_files:
                rel_path = f_info["relative_path"]
                full_path = (run_artifact_dir / rel_path).resolve()
                check_symlinks_and_escapes(full_path, run_artifact_dir)
                expected_physical_paths.add(full_path)

            if resolved_physical != expected_physical_paths:
                missing = expected_physical_paths - resolved_physical
                extra = resolved_physical - expected_physical_paths
                if missing:
                    raise ValueError(f"Missing expected artifact files: {missing}")
                if extra:
                    raise ValueError(f"Extra/untracked artifact files detected: {extra}")

            # Verify file SHA-256
            for f_info in artifact_files:
                rel_path = f_info["relative_path"]
                full_path = (run_artifact_dir / rel_path).resolve()
                actual_sha = self.calculate_sha256(full_path)
                if actual_sha != f_info["sha256"]:
                    raise ValueError(f"Hash mismatch for {rel_path}: expected {f_info['sha256']}, got {actual_sha}")

            # Calculate provider calls
            calls_in_manifest = len(manifest_data.get("call_records", [])) + manifest_data.get("failed_provider_call_count", 0)
            total_provider_calls += calls_in_manifest

            # Verify token usage summation
            manifest_input_tokens = 0
            manifest_output_tokens = 0
            for call in manifest_data.get("call_records", []):
                in_tok = call.get("input_tokens")
                out_tok = call.get("output_tokens")
                if not isinstance(in_tok, int) or not isinstance(out_tok, int) or in_tok <= 0 or out_tok <= 0:
                    raise ValueError(f"Token count in call record is None for run {rec['run_id']}")
                manifest_input_tokens += in_tok
                manifest_output_tokens += out_tok
                metadata = dict(call.get("audit_metadata", ()))
                required_metadata = {
                    "normalized_output_tokens",
                    "raw_completion_tokens",
                    "reasoning_tokens",
                    "usage_source",
                }
                if manifest_data.get("provider_id") == "offline_scripted_provider" and not required_metadata.issubset(metadata):
                    raise ValueError("Offline smoke call missing normalization audit metadata")
                if required_metadata.issubset(metadata):
                    try:
                        normalized = int(metadata["normalized_output_tokens"])
                        raw_completion = int(metadata["raw_completion_tokens"])
                        reasoning = int(metadata["reasoning_tokens"])
                    except (TypeError, ValueError) as exc:
                        raise ValueError("Normalization audit metadata must contain integer strings") from exc
                    if normalized != raw_completion + reasoning or normalized != out_tok:
                        raise ValueError("Normalized token invariant failed")
                    if metadata["usage_source"] != "provider_normalized":
                        raise ValueError("Unexpected usage_source in normalization metadata")

            if manifest_input_tokens != rec.get("input_tokens"):
                raise ValueError(f"Input tokens mismatch for run {rec['run_id']}: manifest={manifest_input_tokens}, record={rec.get('input_tokens')}")
            if manifest_output_tokens != rec.get("output_tokens"):
                raise ValueError(f"Output tokens mismatch for run {rec['run_id']}: manifest={manifest_output_tokens}, record={rec.get('output_tokens')}")

            m_bytes = manifest_file.read_bytes()
            m_sha = hashlib.sha256(m_bytes).hexdigest()
            rel_posix_path = manifest_file.relative_to(self.repo_root).as_posix()
            manifest_items.append({"path": rel_posix_path, "sha256": m_sha})

        # Sort and construct manifest set hash
        manifest_items.sort(key=lambda x: x["path"])
        manifest_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in manifest_items]
        manifest_set_bytes = "\n".join(manifest_lines).encode("utf-8")
        artifact_manifest_set_sha256 = hashlib.sha256(manifest_set_bytes).hexdigest()

        # Scan retrieval log files
        retrieval_dir = (
            self.retrieval_log_root.parent
            if self.retrieval_log_root is not None
            else self.repo_root / "results" / "raw" / "retrieval"
        )
        check_symlinks_and_escapes(retrieval_dir, self.repo_root)

        exp_retrieval_dir = self.retrieval_log_root or retrieval_dir / smoke_experiment_id
        strategy_e_run = next(rec for rec in records if rec["strategy"] == "E")
        expected_retrieval_files = {f"{strategy_e_run['run_id']}.jsonl"}

        actual_retrieval_files = set()
        if exp_retrieval_dir.exists():
            check_symlinks_and_escapes(exp_retrieval_dir, retrieval_dir)
            for item in exp_retrieval_dir.iterdir():
                if item.is_file():
                    check_symlinks_and_escapes(item, exp_retrieval_dir)
                    actual_retrieval_files.add(item.name)

        # Enforce exact retrieval file set: A/C must have NO retrieval logs, E must have exactly 1
        if actual_retrieval_files != expected_retrieval_files:
            extra = actual_retrieval_files - expected_retrieval_files
            missing = expected_retrieval_files - actual_retrieval_files
            if extra:
                raise ValueError(f"Extra retrieval log file detected (A/C must have zero logs): {extra}")
            if missing:
                raise ValueError(f"Missing expected retrieval log file: {missing}")

        # Validate Strategy E retrieval log
        retrieval_logs_valid = True
        retrieval_log_file = exp_retrieval_dir / f"{strategy_e_run['run_id']}.jsonl"
        check_symlinks_and_escapes(retrieval_log_file, exp_retrieval_dir)

        # Load retrieval schema
        retrieval_schema_path = self.repo_root / "contracts" / "retrieval-log.schema.json"
        check_symlinks_and_escapes(retrieval_schema_path, self.repo_root)
        with open(retrieval_schema_path, "r", encoding="utf-8") as f:
            retrieval_log_schema = json.load(f)

        retrieval_bytes = retrieval_log_file.read_bytes()
        r_lines = retrieval_bytes.decode("utf-8").splitlines()
        for idx, line in enumerate(r_lines):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                log_rec = json.loads(line_str)
                validate(instance=log_rec, schema=retrieval_log_schema)
            except Exception as exc:
                retrieval_logs_valid = False
                rejection_reasons.append(f"Retrieval log line {idx+1} schema validation failed: {exc}")

        # Compute retrieval log set hash
        retrieval_sha = hashlib.sha256(retrieval_bytes).hexdigest()
        retrieval_rel_posix_path = retrieval_log_file.relative_to(self.repo_root).as_posix()
        retrieval_items = [{"path": retrieval_rel_posix_path, "sha256": retrieval_sha}]
        retrieval_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in retrieval_items]
        retrieval_set_bytes = "\n".join(retrieval_lines).encode("utf-8")
        retrieval_log_set_sha256 = hashlib.sha256(retrieval_set_bytes).hexdigest()

        # Leakage free validation using physical LeakageAuditor
        leakage_free = False
        if self.leakage_evidence is not None:
            if not isinstance(self.leakage_evidence, LeakageEvidence):
                raise ValueError("leakage_evidence must be a LeakageEvidence instance")
            leakage_auditor = LeakageAuditor(
                self.repo_root,
                artifact_root=artifacts_dir,
                retrieval_log_root=exp_retrieval_dir,
            )
            recalculated_leakage = leakage_auditor.audit_leakage(smoke_experiment_id, self.raw_jsonl_path)
            
            if recalculated_leakage != self.leakage_evidence:
                raise ValueError("Leakage evidence verification failed (forged/mismatched evidence)")
                
            expected_scanned = {self.raw_jsonl_path.relative_to(self.repo_root).as_posix()}
            for rec in records:
                art_path = rec["artifact_path"]
                run_dir = artifacts_dir / art_path
                expected_scanned.add((run_dir / "manifest.json").relative_to(self.repo_root).as_posix())
                
                manifest_file = run_dir / "manifest.json"
                if manifest_file.is_file():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            m_data = json.load(f)
                        for f_info in m_data.get("artifact_files", []):
                            rel_path = f_info["relative_path"]
                            expected_scanned.add((run_dir / rel_path).relative_to(self.repo_root).as_posix())
                    except Exception:
                        pass
            if exp_retrieval_dir.exists():
                for item in exp_retrieval_dir.iterdir():
                    if item.is_file():
                        expected_scanned.add(item.relative_to(self.repo_root).as_posix())
                        
            if set(self.leakage_evidence.scanned_files) != expected_scanned:
                raise ValueError("Leakage evidence scanned_files mismatch with expected files")
                
            if self.leakage_evidence.is_clean is True:
                leakage_free = True

        # Resume verified validation using physical ResumeAuditor
        resume_verified = False
        if self.resume_evidence is not None:
            if not isinstance(self.resume_evidence, ResumeEvidence):
                raise ValueError("resume_evidence must be a ResumeEvidence instance")
            resume_auditor = ResumeAuditor(self.repo_root, artifact_root=artifacts_dir)
            recalculated_resume = resume_auditor.audit_resume(smoke_experiment_id, self.raw_jsonl_path)
            
            if recalculated_resume != self.resume_evidence:
                raise ValueError("Resume evidence verification failed (forged/mismatched evidence)")
                
            record_run_ids = {rec["run_id"] for rec in records}
            if set(self.resume_evidence.completed_run_ids) == record_run_ids:
                if self.resume_evidence.is_valid is True:
                    resume_verified = True

        # Determine automated gate passed (cost unknown does NOT make it false)
        automated_gate_passed = (
            schema_valid
            and artifacts_valid
            and retrieval_logs_valid
            and usage_complete
            and valid_runs_count == 3
            and infra_failures_count == 0
            and leakage_free
            and resume_verified
        )

        return SmokeGateReport(
            report_version="1.0",
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            smoke_experiment_id=smoke_experiment_id,
            model=model,
            provider_id=manifest_provider_id,
            seed=seed,
            source_jsonl_relative_path=self.raw_jsonl_path.relative_to(self.repo_root).as_posix(),
            source_jsonl_sha256=jsonl_sha,
            artifact_manifest_set_sha256=artifact_manifest_set_sha256,
            retrieval_log_set_sha256=retrieval_log_set_sha256,
            attempted_runs=3,
            written_runs=3,
            valid_runs=valid_runs_count,
            infra_failures=infra_failures_count,
            schema_valid=schema_valid,
            artifacts_valid=artifacts_valid,
            retrieval_logs_valid=retrieval_logs_valid,
            usage_complete=usage_complete,
            leakage_free=leakage_free,
            resume_verified=resume_verified,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_provider_calls=total_provider_calls,
            cost_known=False,
            estimated_cost=None,
            automated_gate_passed=automated_gate_passed,
            risk_flags=("unknown_cost",),
            rejection_reasons=tuple(rejection_reasons),
        )


class FullRunApprovalValidator:
    @staticmethod
    def validate_approval(
        report_bytes: bytes | None,
        approval: FullRunApproval,
        repo_root: Path,
        *,
        leakage_evidence: LeakageEvidence | None = None,
        resume_evidence: ResumeEvidence | None = None,
        hard_cap_input_tokens: int = 1000000,
        hard_cap_output_tokens: int = 500000,
        hard_cap_wall_clock: float = 5400.0,
        is_resume: bool = False,
    ) -> None:
        # Enforce path safety
        check_symlinks_and_escapes(repo_root, repo_root)

        # 1. Credentials scan on approval string fields
        for field_name, val in approval.__dict__.items():
            if isinstance(val, str):
                for pattern in [
                    re.compile(r"(?i)bearer\s+"),
                    re.compile(r"(?i)(api[_-]?key|secret|credential)[:=]\s*\w+"),
                ]:
                    if pattern.search(val):
                        raise ValueError(f"Plaintext credential detected in approval field: {field_name}")

        # 2. Verify approved_smoke_report_path exists and containment
        if not approval.approved_smoke_report_path:
            raise ValueError("approved_smoke_report_path must be specified")
        
        report_path = Path(approval.approved_smoke_report_path).resolve()
        gates_root = (repo_root / "results" / "raw" / "gates").resolve()
        try:
            report_path.relative_to(gates_root)
        except ValueError as exc:
            raise ValueError(f"approved_smoke_report_path must be located under {gates_root}") from exc
        if not report_path.is_file():
            raise ValueError("approved_smoke_report_path does not exist or is not a file")

        # Read physical report bytes
        physical_report_bytes = report_path.read_bytes()
        physical_report_sha256 = hashlib.sha256(physical_report_bytes).hexdigest()

        # 3. Verify approved_smoke_sha256 format
        if not re.match(r"^[a-fA-F0-9]{64}$", approval.smoke_report_sha256):
            raise ValueError("approved_smoke_sha256 must be a 64-character hex string")

        # 4. Verify report hash
        if report_bytes is not None:
            report_sha = hashlib.sha256(report_bytes).hexdigest()
            if report_sha != approval.smoke_report_sha256:
                raise ValueError("Report hash mismatch")
            if report_bytes != physical_report_bytes:
                raise ValueError("Report bytes mismatch")

        if physical_report_sha256 != approval.smoke_report_sha256:
            raise ValueError("Report hash mismatch")

        report_data = json.loads(physical_report_bytes.decode("utf-8"))

        if report_data.get("smoke_experiment_id") != "m7d_smoke_20260611T123000Z":
            raise ValueError("smoke_experiment_id must be m7d_smoke_20260611T123000Z")
        if report_data.get("smoke_experiment_id") != approval.smoke_experiment_id:
            raise ValueError("Smoke experiment ID mismatch")

        # 5. Check automated gate passed
        if not report_data.get("automated_gate_passed"):
            raise ValueError("Automated gate did not pass in smoke report")

        # 6. Read raw JSONL and manifest set and retrieval logs from the physical files
        source_jsonl_relative_path = report_data.get("source_jsonl_relative_path")
        if not source_jsonl_relative_path:
            raise ValueError("Missing source_jsonl_relative_path in report")
        
        raw_jsonl_path = repo_root / source_jsonl_relative_path
        check_symlinks_and_escapes(raw_jsonl_path, repo_root)
        if not raw_jsonl_path.is_file():
            raise ValueError("Source JSONL is missing")
        
        raw_jsonl_bytes = raw_jsonl_path.read_bytes()
        jsonl_sha = hashlib.sha256(raw_jsonl_bytes).hexdigest()
        if jsonl_sha != report_data.get("source_jsonl_sha256"):
            raise ValueError("Source JSONL tampered")

        # Determine roots based on layout
        smoke_id = report_data.get("smoke_experiment_id")
        nested_art_root = repo_root / "results" / "raw" / "artifacts" / smoke_id
        if nested_art_root.is_dir():
            art_root = nested_art_root
        else:
            art_root = repo_root / "results" / "raw" / "artifacts"

        nested_ret_root = repo_root / "results" / "raw" / "retrieval" / smoke_id
        if nested_ret_root.is_dir():
            ret_root = nested_ret_root
        else:
            ret_root = repo_root / "results" / "raw" / "retrieval"

        # Auto-generate evidence if None
        if leakage_evidence is None:
            leakage_auditor = LeakageAuditor(
                repo_root,
                artifact_root=art_root,
                retrieval_log_root=ret_root,
            )
            leakage_evidence = leakage_auditor.audit_leakage(approval.smoke_experiment_id, raw_jsonl_path)
        if resume_evidence is None:
            resume_auditor = ResumeAuditor(
                repo_root,
                artifact_root=art_root,
            )
            resume_evidence = resume_auditor.audit_resume(approval.smoke_experiment_id, raw_jsonl_path)

        # Auditor performs full revalidation, checking files directly on the filesystem
        auditor = SmokeGateAuditor(
            raw_jsonl_path,
            repo_root,
            artifact_root=art_root,
            retrieval_log_root=ret_root,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )
        recalculated_report = auditor.audit_smoke_runs()

        # Verify recalculated hashes match report
        if recalculated_report.source_jsonl_sha256 != report_data.get("source_jsonl_sha256"):
            raise ValueError("Source JSONL tampered")
        if recalculated_report.artifact_manifest_set_sha256 != report_data.get("artifact_manifest_set_sha256"):
            raise ValueError("Artifact manifest set tampered")
        if recalculated_report.retrieval_log_set_sha256 != report_data.get("retrieval_log_set_sha256"):
            raise ValueError("Retrieval log set tampered")

        # Verify expected exact file set, model, provider, seed, IDs
        if approval.smoke_experiment_id == approval.full_experiment_id:
            raise ValueError("Smoke and Full experiment IDs must be different")
        if not re.match(r"^m7e_full_[0-9]{8}T[0-9]{6}Z$", approval.full_experiment_id):
            raise ValueError("full_experiment_id must match format ^m7e_full_[0-9]{8}T[0-9]{6}Z$")
        
        if report_data.get("model") != recalculated_report.model:
            raise ValueError("Model identity mismatch")
        if report_data.get("seed") != recalculated_report.seed:
            raise ValueError("Seed mismatch")
        if report_data.get("provider_id") != recalculated_report.provider_id:
            raise ValueError("Provider ID mismatch")

        # Verify scheduler plan parameters for the full run
        from experiments.runner.config import load_experiment_config
        from experiments.runner.scheduler import build_scheduler_plan
        
        try:
            config = load_experiment_config(
                experiment_path=repo_root / "configs" / "experiment.yaml",
                models_path=repo_root / "configs" / "models.yaml",
                repo_root=repo_root,
                mode="live",
                env={"ARAG_RUN_LIVE_GATEWAY": "1"},
            )
        except Exception as exc:
            raise ValueError(f"Failed to load experiment config: {exc}")

        # Provider/model/seed policy must match
        if config.model != "google/gemini-3.5-flash":
            raise ValueError(f"Expected model google/gemini-3.5-flash, got {config.model}")
        if config.model_provider_id != "hermes_vertex_gateway":
            raise ValueError(f"Expected provider hermes_vertex_gateway, got {config.model_provider_id}")
        if config.seed != 42:
            raise ValueError(f"Expected seed 42, got {config.seed}")
        if config.repetitions != 3:
            raise ValueError(f"Expected repetitions 3, got {config.repetitions}")
        if set(config.strategies) != {"A", "C", "E"}:
            raise ValueError(f"Expected strategies A, C, E, got {config.strategies}")

        # Build scheduler plan to verify counts and tasks
        plan = build_scheduler_plan(config=config, repo_root=repo_root, today="20260611")
        if len(plan.runs) != 45:
            raise ValueError(f"Expected 45 planned runs, got {len(plan.runs)}")
        
        tasks_seen = {run.identity.task_id for run in plan.runs}
        if tasks_seen != {"T01", "T02", "T03", "T04", "T05"}:
            raise ValueError(f"Expected tasks T01-T05, got {tasks_seen}")

        # Budgets check: must be positive and not exceed hard caps
        if isinstance(approval.approved_token_budget_input, bool) or not isinstance(approval.approved_token_budget_input, int) or approval.approved_token_budget_input <= 0:
            raise ValueError("approved_token_budget_input must be a positive integer")
        if isinstance(approval.approved_token_budget_output, bool) or not isinstance(approval.approved_token_budget_output, int) or approval.approved_token_budget_output <= 0:
            raise ValueError("approved_token_budget_output must be a positive integer")
        if isinstance(approval.approved_wall_clock_seconds, bool) or not isinstance(approval.approved_wall_clock_seconds, (int, float)) or approval.approved_wall_clock_seconds <= 0:
            raise ValueError("approved_wall_clock_seconds must be a positive number")
        if not isinstance(approval.allow_unknown_cost, bool):
            raise ValueError("allow_unknown_cost must be a boolean")
        if approval.allow_unknown_cost is not True:
            raise ValueError("allow_unknown_cost must be explicitly True")

        # Validate hard cap types and positivity
        if isinstance(hard_cap_input_tokens, bool) or not isinstance(hard_cap_input_tokens, int) or hard_cap_input_tokens <= 0:
            raise ValueError("hard_cap_input_tokens must be a positive integer")
        if isinstance(hard_cap_output_tokens, bool) or not isinstance(hard_cap_output_tokens, int) or hard_cap_output_tokens <= 0:
            raise ValueError("hard_cap_output_tokens must be a positive integer")
        if isinstance(hard_cap_wall_clock, bool) or not isinstance(hard_cap_wall_clock, (int, float)) or hard_cap_wall_clock <= 0:
            raise ValueError("hard_cap_wall_clock must be a positive number")

        if approval.approved_token_budget_input > hard_cap_input_tokens:
            raise ValueError("Input budget exceeds hard cap")
        if approval.approved_token_budget_output > hard_cap_output_tokens:
            raise ValueError("Output budget exceeds hard cap")
        if approval.approved_wall_clock_seconds > hard_cap_wall_clock:
            raise ValueError("Wall clock budget exceeds hard cap")

        # Verify human approval token
        if approval.human_approval != "FULL_RUN":
            raise ValueError("human_approval must be FULL_RUN")

        # Future output paths preflight
        full_id = approval.full_experiment_id
        future_paths = [
            repo_root / "results" / "raw" / f"{full_id}.jsonl",
            repo_root / "results" / "raw" / "artifacts" / full_id,
            repo_root / "results" / "raw" / "retrieval" / full_id,
            repo_root / "results" / "derived" / f"{full_id}.csv",
            repo_root / "results" / "derived" / f"{full_id}_summary.md",
        ]
        for path in future_paths:
            if path.exists() and not is_resume:
                raise ValueError(f"Preflight check failed: target output path already exists: {path}")
