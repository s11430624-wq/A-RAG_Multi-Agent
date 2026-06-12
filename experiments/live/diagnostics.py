from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from experiments.runner.config import ExperimentConfig
from experiments.runner.scheduler import PlannedRun
from experiments.providers.models import ProviderAttemptRecord, ProviderError


@dataclass(frozen=True)
class AbortDiagnosticRecord:
    experiment_id: str
    run_id: str
    role: str
    error_type: str
    error_message: str
    response_sha256: str
    created_at: str
    relative_path: str


class AbortDiagnosticWriter:
    def __init__(self, approved_root: Path) -> None:
        self.approved_root = Path(approved_root).resolve()
        self.diagnostics_root = (self.approved_root / "results" / "raw" / "diagnostics").resolve()

    def write_raw_response(
        self,
        *,
        experiment_id: str,
        run_id: str,
        role: str,
        error_type: str,
        error_message: str,
        raw_response: str,
    ) -> AbortDiagnosticRecord:
        # Validate inputs for path traversal characters
        for val, name in [
            (experiment_id, "experiment_id"),
            (run_id, "run_id"),
            (role, "role"),
            (error_type, "error_type"),
        ]:
            if any(char in val for char in ("/", "\\", "..", ":")):
                raise ValueError(f"Invalid {name}: contains path traversal characters")

        # Security Denylist Check
        denylist = [
            "evaluation/hidden_tests",
            "evaluation\\hidden_tests",
            "evaluation/reference_patches",
            "evaluation\\reference_patches",
        ]
        for pattern in denylist:
            if pattern in raw_response:
                raise ValueError(f"Security Blocker: denylisted pattern '{pattern}' found in raw_response")
            if pattern in error_message:
                raise ValueError(f"Security Blocker: denylisted pattern '{pattern}' found in error_message")

        # Resolve target paths
        target_dir = (self.diagnostics_root / experiment_id / run_id).resolve()

        # Strict path containment check
        try:
            target_dir.relative_to(self.diagnostics_root)
        except ValueError as exc:
            raise ValueError(f"Path traversal detected: target directory is outside diagnostics root. {exc}")

        # Ensure directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / "raw_response.json"

        # Calculate response hash (over UTF-8 bytes of raw_response)
        sha256 = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()

        # Format ISO timestamp
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Create diagnostic payload
        payload = {
            "created_at": created_at,
            "error_message": error_message,
            "error_type": error_type,
            "experiment_id": experiment_id,
            "raw_response": raw_response,
            "response_sha256": sha256,
            "role": role,
            "run_id": run_id,
        }

        # Canonical JSON serialization
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if not canonical_json.endswith("\n"):
            canonical_json += "\n"

        # Write using exclusive-create mode ('x') to prevent overwrite
        try:
            with open(target_file, "x", encoding="utf-8", newline="\n") as f:
                f.write(canonical_json)
        except FileExistsError as exc:
            raise FileExistsError(f"Diagnostic record already exists: {target_file}. Overwrite rejected.") from exc

        # Calculate relative path from approved root for record representation
        rel_path = str(target_file.relative_to(self.approved_root)).replace("\\", "/")

        return AbortDiagnosticRecord(
            experiment_id=experiment_id,
            run_id=run_id,
            role=role,
            error_type=error_type,
            error_message=error_message,
            response_sha256=sha256,
            created_at=created_at,
            relative_path=rel_path,
        )


def get_sanitized_error_code(exc: Exception) -> str:
    if hasattr(exc, "attempt_records") and exc.attempt_records:
        last_rec = exc.attempt_records[-1]
        if last_rec.error is not None and last_rec.error.error_code:
            return last_rec.error.error_code
    
    cls_name = exc.__class__.__name__
    if cls_name == "BudgetExceededError":
        return "budget_exceeded"
    elif cls_name == "ProviderTransportError":
        return "transport_failure"
    elif cls_name == "ProviderAuthenticationError":
        return "authentication_failure"
    elif cls_name == "ProviderCancelledError":
        return "cancelled"
    elif cls_name == "ProviderGatewayError":
        return "gateway_failure"
    elif cls_name == "LiveExecutionAbort":
        return "infrastructure_failure"
    return "unknown_error"


def serialize_attempt_record(record: ProviderAttemptRecord) -> dict[str, Any]:
    err_dict = None
    if record.error is not None:
        err_dict = {
            "category": record.error.category,
            "retryable": record.error.retryable,
            "status_code": record.error.status_code,
            "error_code": record.error.error_code,
        }
    return {
        "call_index": record.call_index,
        "attempt_index": record.attempt_index,
        "latency_seconds": record.latency_seconds,
        "backoff_seconds_after": record.backoff_seconds_after,
        "outcome": record.outcome,
        "error": err_dict,
    }


def write_provider_failure_diagnostic(
    *,
    approved_root: Path,
    experiment_id: str,
    run: PlannedRun,
    config: ExperimentConfig,
    exc: Exception,
    elapsed_seconds: float,
) -> None:
    # 1. Security & original cause traversal
    orig_exc = exc
    while orig_exc is not None:
        if hasattr(orig_exc, "attempt_records") and orig_exc.attempt_records:
            break
        if getattr(orig_exc, "__cause__", None) is not None:
            orig_exc = orig_exc.__cause__
        elif getattr(orig_exc, "__context__", None) is not None:
            orig_exc = orig_exc.__context__
        else:
            break
    if orig_exc is None or not hasattr(orig_exc, "attempt_records") or not orig_exc.attempt_records:
        orig_exc = exc

    error_class = orig_exc.__class__.__name__
    sanitized_error_code = get_sanitized_error_code(orig_exc)

    attempt_records: tuple[ProviderAttemptRecord, ...] = ()
    if hasattr(orig_exc, "attempt_records"):
        attempt_records = orig_exc.attempt_records

    # Filter allowlisted rate-limit headers
    allowlisted_rate_limit_headers: list[tuple[str, str]] = []
    if hasattr(orig_exc, "allowlisted_headers") and orig_exc.allowlisted_headers:
        allowlisted_rate_limit_headers = list(orig_exc.allowlisted_headers)
    elif hasattr(exc, "allowlisted_headers") and exc.allowlisted_headers:
        allowlisted_rate_limit_headers = list(exc.allowlisted_headers)

    final_http_status = None
    if attempt_records:
        last_rec = attempt_records[-1]
        if last_rec.error is not None:
            final_http_status = last_rec.error.status_code

    serialized_attempts = []
    for rec in attempt_records:
        serialized_attempts.append(serialize_attempt_record(rec))

    payload = {
        "diagnostic_version": "1.0",
        "experiment_id": experiment_id,
        "run_id": run.identity.run_id,
        "task_id": run.identity.task_id,
        "strategy": run.identity.strategy,
        "provider_id": config.model_provider_id,
        "model": config.model,
        "error_class": error_class,
        "sanitized_error_code": sanitized_error_code,
        "final_http_status": final_http_status,
        "attempt_count": len(attempt_records),
        "attempt_records": serialized_attempts,
        "allowlisted_rate_limit_headers": allowlisted_rate_limit_headers,
        "elapsed_seconds": elapsed_seconds,
    }

    # Format JSON string
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    # 2. Strict Security Checks ON JSON content BEFORE any directories are created!
    denylist_patterns = [
        "evaluation/hidden_tests",
        "evaluation\\hidden_tests",
        "evaluation/reference_patches",
        "evaluation\\reference_patches",
    ]
    for pattern in denylist_patterns:
        if pattern in canonical_json:
            raise ValueError(f"Security Blocker: denylisted pattern '{pattern}' found in diagnostic content")
    
    for key in ("authorization", "bearer", "private_key", "api_key", "secret"):
        if key in canonical_json.lower():
            raise ValueError(f"Security Blocker: credential-like pattern '{key}' found in diagnostic content")

    for forbidden in (":\\", ":/", "/Users/", "/home/"):
        if forbidden.lower() in canonical_json.lower():
            raise ValueError(f"Security Blocker: forbidden pattern '{forbidden}' found in diagnostic content")

    if not canonical_json.endswith("\n"):
        canonical_json += "\n"

    # 3. Path Validation
    for val, name in [
        (experiment_id, "experiment_id"),
        (run.identity.run_id, "run_id"),
        (run.identity.task_id, "task_id"),
        (run.identity.strategy, "strategy"),
    ]:
        if any(char in val for char in ("/", "\\", "..", ":")):
            raise ValueError(f"Invalid {name}: contains path traversal characters")

    diagnostics_root = (approved_root / "results" / "raw" / "diagnostics").resolve()
    target_dir = (diagnostics_root / experiment_id / run.identity.run_id).resolve()

    try:
        target_dir.relative_to(diagnostics_root)
    except ValueError as exc_path:
        raise ValueError(f"Path traversal detected: target directory is outside diagnostics root. {exc_path}")

    # Now we are 100% verified and secure. We can safely create target directory and write!
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "provider_failure.json"

    try:
        with open(target_file, "x", encoding="utf-8", newline="\n") as f:
            f.write(canonical_json)
    except FileExistsError:
        raise FileExistsError("Diagnostic write rejected: file already exists") from None
    except Exception:
        raise RuntimeError("Diagnostic write failed") from None
