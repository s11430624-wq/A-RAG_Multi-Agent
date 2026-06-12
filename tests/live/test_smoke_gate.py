from __future__ import annotations

import json
import hashlib
import pytest
from pathlib import Path
import os
from experiments.live.smoke_gate import SmokeGateReport, SmokeGateAuditor
from tests.live.test_approval import create_smoke_gate_mock_workspace

def test_canonical_json_format_rules(tmp_path):
    report = SmokeGateReport(
        report_version="1.0",
        generated_at="2026-06-11T12:00:00Z",
        smoke_experiment_id="exp-test-smoke",
        model="google/gemini-3.5-flash",
        provider_id="hermes",
        seed=42,
        source_jsonl_relative_path="raw/exp-test-smoke.jsonl",
        source_jsonl_sha256="abc",
        artifact_manifest_set_sha256="def",
        retrieval_log_set_sha256="ghi",
        attempted_runs=3,
        written_runs=3,
        valid_runs=3,
        infra_failures=0,
        schema_valid=True,
        artifacts_valid=True,
        retrieval_logs_valid=True,
        usage_complete=True,
        leakage_free=True,
        resume_verified=True,
        total_input_tokens=100,
        total_output_tokens=50,
        total_provider_calls=6,
        cost_known=False,
        estimated_cost=None,
        automated_gate_passed=True,
        risk_flags=("unknown_cost",),
        rejection_reasons=(),
    )
    
    canonical_bytes = report.to_canonical_json()
    assert canonical_bytes.endswith(b"\n")
    assert canonical_bytes.count(b"\n") == 1
    
    data = json.loads(canonical_bytes.decode("utf-8"))
    re_serialized = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    assert canonical_bytes == re_serialized


def test_smoke_gate_exclusive_create(tmp_path):
    report_file = tmp_path / "smoke_report.json"
    report_file.write_text("existing", encoding="utf-8")
    
    report = SmokeGateReport(
        report_version="1.0",
        generated_at="2026-06-11T12:00:00Z",
        smoke_experiment_id="exp-test-smoke",
        model="google/gemini-3.5-flash",
        provider_id="hermes",
        seed=42,
        source_jsonl_relative_path="raw/exp-test-smoke.jsonl",
        source_jsonl_sha256="abc",
        artifact_manifest_set_sha256="def",
        retrieval_log_set_sha256="ghi",
        attempted_runs=3,
        written_runs=3,
        valid_runs=3,
        infra_failures=0,
        schema_valid=True,
        artifacts_valid=True,
        retrieval_logs_valid=True,
        usage_complete=True,
        leakage_free=True,
        resume_verified=True,
        total_input_tokens=100,
        total_output_tokens=50,
        total_provider_calls=6,
        cost_known=False,
        estimated_cost=None,
        automated_gate_passed=True,
        risk_flags=("unknown_cost",),
        rejection_reasons=(),
    )
    
    with pytest.raises(FileExistsError):
        report.write_to_file(report_file)


def test_auditor_succeeds_on_valid_workspace(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    auditor = SmokeGateAuditor(
        jsonl_path,
        repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )
    report = auditor.audit_smoke_runs()
    assert report.automated_gate_passed is True
    assert report.valid_runs == 3
    assert report.infra_failures == 0
    assert report.cost_known is False
    assert "unknown_cost" in report.risk_flags


def test_auditor_fails_without_evidence(tmp_path):
    repo, _, _, _, _, _, _, _ = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Supply no evidence (default to None)
    auditor = SmokeGateAuditor(jsonl_path, repo)
    report = auditor.audit_smoke_runs()
    assert report.automated_gate_passed is False
    assert report.leakage_free is False
    assert report.resume_verified is False


def test_auditor_rejects_extra_file_in_artifacts(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Write extra artifact directory starting with experiment_id
    extra_dir = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__extra"
    extra_dir.mkdir()
    
    auditor = SmokeGateAuditor(
        jsonl_path,
        repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )
    with pytest.raises(ValueError, match="Extra artifact directory detected"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_extra_file_in_retrieval(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Write extra retrieval log file (prohibited A/C retrieval logs or extra files)
    extra_log = repo / "results" / "raw" / "retrieval" / report_obj.smoke_experiment_id / "extra.jsonl"
    extra_log.write_text("{}", encoding="utf-8")
    
    auditor = SmokeGateAuditor(
        jsonl_path,
        repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )
    with pytest.raises(ValueError, match="Extra retrieval log file detected"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_symlinks(tmp_path):
    # Skip symlink tests on Windows if permissions not available,
    # but we can try to create one or mock os.path.islink
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Mock os.path.islink on the JSONL path to simulate a symlink attack
    import os
    original_islink = os.path.islink
    try:
        os.path.islink = lambda path: True if str(path) == str(jsonl_path) else original_islink(path)
        auditor = SmokeGateAuditor(
            jsonl_path,
            repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )
        with pytest.raises(ValueError, match="Symlink detected"):
            auditor.audit_smoke_runs()
    finally:
        os.path.islink = original_islink


def test_auditor_rejects_invalid_manifest_version(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Modify manifest version in manifest.json for Strategy A
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["manifest_version"] = "m4-artifact-v0"
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Invalid manifest version"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_metadata_mismatch(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["seed"] = 9999  # mismatch!
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Manifest seed mismatch"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_usage_incomplete(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["usage_complete"] = False  # mismatch/invalid!
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Manifest usage_complete is not True"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_unsafe_manifest_paths(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["artifact_files"] = [{"relative_path": "../escape.txt", "sha256": "abc"}]
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Unsafe path in artifact_files"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_duplicate_manifest_paths(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["artifact_files"] = [
        {"relative_path": "test.py", "sha256": "abc"},
        {"relative_path": "test.py", "sha256": "abc"}
    ]
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Duplicate path in artifact_files"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_missing_artifact_file(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Remove physical test.py
    run_dir = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42"
    os.remove(run_dir / "test.py")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Missing expected artifact files"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_extra_artifact_file(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Add an extra file
    run_dir = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42"
    (run_dir / "extra.py").write_text("print('extra')", encoding="utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Extra/untracked artifact files detected"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_hash_mismatch(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Tamper with test.py content
    run_dir = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42"
    (run_dir / "test.py").write_text("print('tampered')", encoding="utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Hash mismatch for test.py"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_token_sum_mismatch(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Change tokens in manifest call_records to mismatch the record's tokens
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["call_records"][0]["input_tokens"] = 999  # mismatch with 100 in result record!
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Input tokens mismatch for run"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_forged_evidence(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # 1. Forge leakage evidence by declaring is_clean=True with invalid audited_files_hash
    from experiments.live.smoke_gate import LeakageEvidence
    forged_leakage = LeakageEvidence(
        smoke_experiment_id=leakage_evidence.smoke_experiment_id,
        source_jsonl_sha256=leakage_evidence.source_jsonl_sha256,
        scanned_files=leakage_evidence.scanned_files,
        is_clean=True,
        audited_files_hash="forged_hash",
        auditor_version="1.0"
    )
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=forged_leakage, resume_evidence=resume_evidence)
    with pytest.raises(ValueError, match="Leakage evidence verification failed"):
        auditor.audit_smoke_runs()
        
    # 2. Forge resume evidence by declaring is_valid=True with invalid audited_files_hash
    from experiments.live.smoke_gate import ResumeEvidence
    forged_resume = ResumeEvidence(
        smoke_experiment_id=resume_evidence.smoke_experiment_id,
        completed_run_ids=resume_evidence.completed_run_ids,
        is_valid=True,
        audited_files_hash="forged_hash",
        auditor_version="1.0",
        source_jsonl_sha256=resume_evidence.source_jsonl_sha256
    )
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=leakage_evidence, resume_evidence=forged_resume)
    with pytest.raises(ValueError, match="Resume evidence verification failed"):
        auditor.audit_smoke_runs()


def test_auditor_rejects_provider_id_mismatch(tmp_path):
    repo, _, _, _, _, report_obj, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    jsonl_path = next((repo / "results" / "raw").glob("*.jsonl"))
    
    # Change provider_id in one of the manifests to create a mismatch
    manifest_file = repo / "results" / "raw" / "artifacts" / f"{report_obj.smoke_experiment_id}__T01__A__rep01__seed42" / "manifest.json"
    data = json.loads(manifest_file.read_text("utf-8"))
    data["provider_id"] = "attacker-provider"
    manifest_file.write_text(json.dumps(data), "utf-8")
    
    # Regenerate evidence because we modified a manifest file on disk!
    from experiments.live.smoke_gate import LeakageAuditor, ResumeAuditor
    leakage_auditor = LeakageAuditor(repo)
    new_leakage = leakage_auditor.audit_leakage(report_obj.smoke_experiment_id, jsonl_path)
    resume_auditor = ResumeAuditor(repo)
    new_resume = resume_auditor.audit_resume(report_obj.smoke_experiment_id, jsonl_path)
    
    auditor = SmokeGateAuditor(jsonl_path, repo, leakage_evidence=new_leakage, resume_evidence=new_resume)
    with pytest.raises(ValueError, match="Provider ID mismatch between manifests"):
        auditor.audit_smoke_runs()
