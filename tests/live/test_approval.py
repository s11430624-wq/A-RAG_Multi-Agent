from __future__ import annotations

import json
import hashlib
import pytest
from pathlib import Path
from experiments.live.smoke_gate import SmokeGateReport, FullRunApproval, FullRunApprovalValidator, SmokeGateAuditor

def create_smoke_gate_mock_workspace(
    tmp_path: Path,
    experiment_id: str = "m7d_smoke_20260611T123000Z",
) -> tuple[Path, bytes, bytes, bytes, bytes, SmokeGateReport]:
    repo = tmp_path / "repo"
    repo.mkdir()
    
    # 1. Write contracts
    contracts_dir = repo / "contracts"
    contracts_dir.mkdir()
    import shutil
    shutil.copytree(Path(__file__).resolve().parents[2] / "configs", repo / "configs")
    (repo / "experiments").mkdir(exist_ok=True)
    shutil.copy(Path(__file__).resolve().parents[2] / "experiments" / "tasks.json", repo / "experiments" / "tasks.json")
    
    # Copy or create skeleton result.schema.json and retrieval-log.schema.json
    result_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["run_id", "task_id", "strategy", "valid_run", "infra_error", "artifact_path", "input_tokens", "output_tokens"],
        "properties": {
            "run_id": {"type": "string"},
            "task_id": {"type": "string"},
            "strategy": {"type": "string", "enum": ["A", "C", "E"]},
            "valid_run": {"type": "boolean"},
            "infra_error": {"type": "boolean"},
            "artifact_path": {"type": "string"},
            "input_tokens": {"type": "integer"},
            "output_tokens": {"type": "integer"},
            "tool_calls": {"type": "integer"},
            "model": {"type": "string"},
            "seed": {"type": "integer"}
        }
    }
    retrieval_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["run_id", "task_id", "strategy", "token_count"],
        "properties": {
            "run_id": {"type": "string"},
            "task_id": {"type": "string"},
            "strategy": {"type": "string"},
            "token_count": {"type": "integer"}
        }
    }
    
    (contracts_dir / "result.schema.json").write_text(json.dumps(result_schema), encoding="utf-8")
    (contracts_dir / "retrieval-log.schema.json").write_text(json.dumps(retrieval_schema), encoding="utf-8")
    
    # 2. Write smoke results JSONL
    results_raw_dir = repo / "results" / "raw"
    results_raw_dir.mkdir(parents=True)
    
    raw_jsonl_path = results_raw_dir / f"{experiment_id}.jsonl"
    
    run_id_a = f"{experiment_id}__T01__A__rep01__seed42"
    run_id_c = f"{experiment_id}__T01__C__rep01__seed42"
    run_id_e = f"{experiment_id}__T01__E__rep01__seed42"
    
    records = [
        {
            "run_id": run_id_a,
            "task_id": "T01",
            "strategy": "A",
            "valid_run": True,
            "infra_error": False,
            "artifact_path": run_id_a,
            "input_tokens": 100,
            "output_tokens": 50,
            "tool_calls": 0,
            "model": "GPT5.4",
            "seed": 42
        },
        {
            "run_id": run_id_c,
            "task_id": "T01",
            "strategy": "C",
            "valid_run": True,
            "infra_error": False,
            "artifact_path": run_id_c,
            "input_tokens": 150,
            "output_tokens": 70,
            "tool_calls": 0,
            "model": "GPT5.4",
            "seed": 42
        },
        {
            "run_id": run_id_e,
            "task_id": "T01",
            "strategy": "E",
            "valid_run": True,
            "infra_error": False,
            "artifact_path": run_id_e,
            "input_tokens": 200,
            "output_tokens": 90,
            "tool_calls": 2,
            "model": "GPT5.4",
            "seed": 42
        }
    ]
    raw_jsonl_bytes = ("\n".join(json.dumps(r) for r in records) + "\n").encode("utf-8")
    raw_jsonl_path.write_bytes(raw_jsonl_bytes)
    
    # 3. Write artifact manifests
    artifacts_dir = results_raw_dir / "artifacts"
    artifacts_dir.mkdir()
    
    # We must match the input/output tokens in records:
    # A: input=100, output=50, strategy=A
    # C: input=150, output=70, strategy=C
    # E: input=200, output=90, strategy=E
    tokens_map = {
        run_id_a: (100, 50, "A"),
        run_id_c: (150, 70, "C"),
        run_id_e: (200, 90, "E"),
    }
    
    manifest_items = []
    for run_id in (run_id_a, run_id_c, run_id_e):
        in_t, out_t, strat = tokens_map[run_id]
        art_path = artifacts_dir / run_id
        art_path.mkdir()
        
        # Write physical file test.py
        file_content = b"print('hello')"
        (art_path / "test.py").write_bytes(file_content)
        file_sha = hashlib.sha256(file_content).hexdigest()
        
        manifest_data = {
            "manifest_version": "m5-artifact-v1",
            "created_at": "2026-06-11T12:00:00Z",
            "run_id": run_id,
            "task_id": "T01",
            "strategy": strat,
            "model": "GPT5.4",
            "provider_id": "openai_compatible_gateway",
            "seed": 42,
            "usage_complete": True,
            "failed_provider_call_count": 0,
            "call_records": [
                {
                    "call_index": 0,
                    "role": "Single",
                    "phase": "initial",
                    "template_name": "prompt_template",
                    "template_hash": "hash1",
                    "rendered_prompt_hash": "hash2",
                    "response_hash": "hash3",
                    "provider_request_id": "req1",
                    "input_tokens": in_t,
                    "output_tokens": out_t,
                    "model_latency_seconds": 1.5,
                    "retry_count": 0,
                    "finish_reason": "stop",
                    "seed_applied": True
                }
            ],
            "artifact_files": [
                {
                    "relative_path": "test.py",
                    "sha256": file_sha
                }
            ]
        }
        
        m_bytes = json.dumps(manifest_data, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        manifest_file = art_path / "manifest.json"
        manifest_file.write_bytes(m_bytes)
        
        m_sha = hashlib.sha256(m_bytes).hexdigest()
        rel_path = manifest_file.relative_to(repo).as_posix()
        manifest_items.append({"path": rel_path, "sha256": m_sha})
        
    manifest_items.sort(key=lambda x: x["path"])
    manifest_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in manifest_items]
    manifest_set_bytes = "\n".join(manifest_lines).encode("utf-8")
    
    # 4. Write Strategy E retrieval log
    retrieval_dir = results_raw_dir / "retrieval" / experiment_id
    retrieval_dir.mkdir(parents=True)
    
    retrieval_file = retrieval_dir / f"{run_id_e}.jsonl"
    retrieval_log_bytes = (json.dumps({"run_id": run_id_e, "task_id": "T01", "strategy": "E", "token_count": 50}) + "\n").encode("utf-8")
    retrieval_file.write_bytes(retrieval_log_bytes)
    
    ret_rel_path = retrieval_file.relative_to(repo).as_posix()
    ret_sha = hashlib.sha256(retrieval_log_bytes).hexdigest()
    ret_items = [{"path": ret_rel_path, "sha256": ret_sha}]
    retrieval_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in ret_items]
    retrieval_log_set_bytes = "\n".join(retrieval_lines).encode("utf-8")
    
    from experiments.live.smoke_gate import LeakageAuditor, ResumeAuditor
    leakage_auditor = LeakageAuditor(repo)
    leakage_evidence = leakage_auditor.audit_leakage(experiment_id, raw_jsonl_path)
    
    resume_auditor = ResumeAuditor(repo)
    resume_evidence = resume_auditor.audit_resume(experiment_id, raw_jsonl_path)
    
    # Generate report
    auditor = SmokeGateAuditor(
        raw_jsonl_path,
        repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )
    report = auditor.audit_smoke_runs()
    
    report_gates_dir = repo / "results" / "raw" / "gates"
    report_gates_dir.mkdir(parents=True, exist_ok=True)
    report_file_path = report_gates_dir / f"{experiment_id}.json"
    report_file_path.write_bytes(report.to_canonical_json())
    
    return repo, report.to_canonical_json(), raw_jsonl_bytes, manifest_set_bytes, retrieval_log_set_bytes, report, leakage_evidence, resume_evidence


def test_approval_validates_successfully(tmp_path):
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    
    # Re-reading and validating should succeed
    FullRunApprovalValidator.validate_approval(
        report_bytes=report_bytes,
        approval=approval,
        repo_root=repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )


def test_approval_accepts_alternate_canonical_smoke_id(tmp_path):
    experiment_id = "m7d_smoke_20260613T020000Z"
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(
        tmp_path,
        experiment_id=experiment_id,
    )

    report_sha = hashlib.sha256(report_bytes).hexdigest()

    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260613T021500Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )

    FullRunApprovalValidator.validate_approval(
        report_bytes=report_bytes,
        approval=approval,
        repo_root=repo,
        leakage_evidence=leakage_evidence,
        resume_evidence=resume_evidence,
    )


def test_approval_tamper_detection(tmp_path):
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    
    # 1. Tamper report bytes
    tampered_report = report_bytes + b" "
    with pytest.raises(ValueError, match="Report hash mismatch"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=tampered_report,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )
        
    # 2. Tamper physical JSONL file content
    raw_path = repo / "results" / "raw" / f"{report.smoke_experiment_id}.jsonl"
    original_jsonl = raw_path.read_bytes()
    raw_path.write_bytes(original_jsonl + b"\n# extra comment")
    
    with pytest.raises(ValueError, match="Source JSONL tampered"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )
    
    # Restore JSONL
    raw_path.write_bytes(original_jsonl)


def test_approval_id_collision_detection(tmp_path):
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id=report.smoke_experiment_id,  # Same smoke and full experiment ID!
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    
    with pytest.raises(ValueError, match="Smoke and Full experiment IDs must be different"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )


def test_approval_budget_exceeds_hard_cap(tmp_path):
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    # Input budget exceeds hard cap!
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=9999999, # Too high!
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    
    with pytest.raises(ValueError, match="Input budget exceeds hard cap"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            hard_cap_input_tokens=1000000,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )


def test_approval_rejects_invalid_types(tmp_path):
    repo, report_bytes, _, _, _, report, leakage_evidence, resume_evidence = create_smoke_gate_mock_workspace(tmp_path)
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    # 1. approved_token_budget_input as a boolean (True)
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=True, # invalid bool!
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    with pytest.raises(ValueError, match="approved_token_budget_input must be a positive integer"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )

    # 2. approved_token_budget_output as a float (5000.5)
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000.5, # invalid float!
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    with pytest.raises(ValueError, match="approved_token_budget_output must be a positive integer"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )

    # 3. approved_wall_clock_seconds as a boolean
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=True, # invalid bool!
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    with pytest.raises(ValueError, match="approved_wall_clock_seconds must be a positive number"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )

    # 4. allow_unknown_cost as non-boolean (integer 1)
    approval = FullRunApproval(
        approved_smoke_report_path=str(repo / "results" / "raw" / "gates" / f"{report.smoke_experiment_id}.json"),
        smoke_report_sha256=report_sha,
        smoke_experiment_id=report.smoke_experiment_id,
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=10000,
        approved_token_budget_output=5000,
        approved_wall_clock_seconds=600.0,
        allow_unknown_cost=1, # invalid non-bool!
        human_approval="FULL_RUN",
    )
    with pytest.raises(ValueError, match="allow_unknown_cost must be a boolean"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=report_bytes,
            approval=approval,
            repo_root=repo,
            leakage_evidence=leakage_evidence,
            resume_evidence=resume_evidence,
        )
