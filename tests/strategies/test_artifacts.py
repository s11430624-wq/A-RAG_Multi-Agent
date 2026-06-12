import hashlib
import json
from pathlib import Path

import pytest

from experiments.strategies.artifacts import ArtifactBundleWriter, ArtifactWriteError
from experiments.strategies.metrics import StrategyMetricsCollector
from experiments.providers.models import ModelResponse, ProviderAttemptRecord, Usage


def _response(call_index, usage, metadata=()):
    attempt = ProviderAttemptRecord(call_index, 1, 0.2, 0.0, "response", None)
    return ModelResponse("ok", "stop", usage, f"p-{call_index}", "m", 0.2, 0, True, metadata, (attempt,))


def test_staged_prompt_bytes_are_exact_and_manifest_is_written_last(tmp_path: Path):
    root = tmp_path / "approved"
    writer = ArtifactBundleWriter(
        root,
        run_id="run-1",
        task_id="T01",
        strategy="A",
        model="m",
        provider_id="provider-1",
        seed=42,
    )
    prompt = "exact prompt".encode("utf-8")
    writer.stage_bytes("prompts/0001_single.txt", prompt)

    assert (root / "run-1/prompts/0001_single.txt").read_bytes() == prompt
    assert not (root / "run-1/manifest.json").exists()
    finalization = writer.finalize(StrategyMetricsCollector(retrieval_success=None).snapshot())

    manifest_path = root / "run-1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["provider_id"] == "provider-1"
    assert finalization.manifest_sha256 == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert "manifest.json" not in {item["relative_path"] for item in manifest["artifact_files"]}
    assert finalization.artifact_path == "run-1"
    assert {
        "template_hashes",
        "rendered_prompt_hashes",
        "response_hashes",
        "patch_hashes",
        "provider_request_ids",
        "retrieval_log_relative_path",
    } <= set(manifest)


def test_manifest_finalize_is_exclusive_and_existing_bytes_fail_closed(tmp_path: Path):
    root = tmp_path / "approved"
    first = ArtifactBundleWriter(
        root,
        run_id="run",
        task_id="T01",
        strategy="A",
        model="m",
        provider_id="provider-1",
        seed=42,
    )
    first.stage_bytes("responses/0001.txt", b"response")
    finalization = first.finalize(
        StrategyMetricsCollector(retrieval_success=None).snapshot()
    )
    manifest_path = root / "run/manifest.json"
    finalized_bytes = manifest_path.read_bytes()

    second = ArtifactBundleWriter(
        root,
        run_id="run",
        task_id="T01",
        strategy="A",
        model="m",
        provider_id="provider-1",
        seed=42,
    )
    with pytest.raises(ArtifactWriteError, match="manifest write failed"):
        second.finalize(StrategyMetricsCollector(retrieval_success=None).snapshot())

    assert manifest_path.read_bytes() == finalized_bytes
    assert hashlib.sha256(finalized_bytes).hexdigest() == finalization.manifest_sha256


def test_stage_is_exclusive_and_rejects_path_escape(tmp_path: Path):
    writer = ArtifactBundleWriter(tmp_path / "approved", run_id="run", task_id="T01", strategy="A", model="m", provider_id="provider", seed=1)
    writer.stage_bytes("patches/initial.diff", b"x")
    with pytest.raises(ArtifactWriteError):
        writer.stage_bytes("patches/initial.diff", b"y")
    with pytest.raises(ArtifactWriteError):
        writer.stage_bytes("../escape.txt", b"x")


def test_close_without_finalize_rolls_back_staged_bundle(tmp_path: Path):
    root = tmp_path / "approved"
    writer = ArtifactBundleWriter(root, run_id="run", task_id="T01", strategy="A", model="m", provider_id="provider", seed=1)
    writer.stage_bytes("responses/0001.txt", b"response")

    writer.close()

    assert not (root / "run").exists()


def test_finalize_is_write_once_and_close_preserves_finalized_bundle(tmp_path: Path):
    root = tmp_path / "approved"
    writer = ArtifactBundleWriter(root, run_id="run", task_id="T01", strategy="A", model="m", provider_id="provider", seed=1)
    writer.stage_bytes("patches/initial.diff", b"patch")
    writer.finalize(StrategyMetricsCollector(retrieval_success=None).snapshot())
    with pytest.raises(ArtifactWriteError):
        writer.finalize(StrategyMetricsCollector(retrieval_success=None).snapshot())
    writer.close()
    assert (root / "run/manifest.json").exists()


# M7-C.2 ModelCallRecord in manifest preserves audit_metadata test

def test_manifest_includes_usage_audit_metadata_in_call_records(tmp_path: Path):
    root = tmp_path / "approved"
    writer = ArtifactBundleWriter(root, run_id="run-norm", task_id="T01", strategy="C", model="google/gemini-3.5-flash", provider_id="hermes_vertex_gateway", seed=42)
    
    # We must ensure run_root directory is created since normally stage_bytes creates it
    writer.run_root.mkdir(parents=True, exist_ok=True)
    
    # 1. Simulate a normalized provider call response
    audit_meta = (
        ("normalization_rule", "google_vertex_reasoning_accumulation"),
        ("normalized_output_tokens", "94"),
        ("raw_completion_tokens", "1"),
        ("reasoning_tokens", "93"),
        ("usage_source", "provider_normalized"),
    )
    
    collector = StrategyMetricsCollector(retrieval_success=None)
    collector.record_response(
        _response(1, Usage(8, 94, 102, "provider_normalized"), metadata=audit_meta),
        role="Planner",
        phase="initial",
        template_name="planner.txt",
        template_hash="a",
        rendered_prompt_hash="b",
        response_hash="c",
    )
    
    # Finalize writes the manifest.json
    writer.finalize(collector.snapshot())
    
    manifest_path = root / "run-norm/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    # The generated call_records inside manifest must preserve audit_metadata
    call_records = manifest["call_records"]
    assert len(call_records) == 1
    record = call_records[0]
    assert record["input_tokens"] == 8
    assert record["output_tokens"] == 94
    assert record["audit_metadata"] == [
        ["normalization_rule", "google_vertex_reasoning_accumulation"],
        ["normalized_output_tokens", "94"],
        ["raw_completion_tokens", "1"],
        ["reasoning_tokens", "93"],
        ["usage_source", "provider_normalized"],
    ]
