from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from experiments.providers.models import FinishReason, ProviderFinishReasonError
from experiments.retrieval.guards import assert_query_safe
from experiments.strategies.models import (
    EvidenceLedger,
    PlannerOutput,
    ResponseClassification,
    RetrievalChunkReadRequest,
    RetrievalRequest,
    RetrievalSearchRequest,
    ReviewerIssue,
    ReviewerVerdict,
)


class StrategyResponseError(ValueError):
    pass


class InvalidPatchError(StrategyResponseError):
    pass


class RetrievalBudgetExceededError(StrategyResponseError):
    pass


class ResponseEnvelopeClassifier:
    @staticmethod
    def classify(
        *,
        expected_role: str,
        response_text: str,
        finish_reason: FinishReason,
    ) -> ResponseClassification:
        digest = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
        if finish_reason != "stop":
            raise ProviderFinishReasonError(f"finish_reason is not stop: {finish_reason}")
        parsed = _load_exact_json(response_text)
        if isinstance(parsed, dict) and parsed.get("action") == "retrieve":
            return ResponseClassification("retrieval_request", digest, None, None, None)
        if expected_role in ("Planner", "Reviewer") and isinstance(parsed, dict):
            return ResponseClassification("final_output", digest, None, response_text, None)
        if expected_role in ("Single", "Coder", "Repair"):
            try:
                PatchResponseParser.parse(response_text)
                return ResponseClassification("final_output", digest, None, response_text, None)
            except InvalidPatchError as exc:
                return ResponseClassification("invalid", digest, None, None, str(exc))
        return ResponseClassification("invalid", digest, None, None, "response does not match expected role")


class PatchResponseParser:
    @staticmethod
    def parse(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise InvalidPatchError("patch is empty")
        normalized = _normalize_model_patch_counts(
            _strip_git_diff_metadata(_unwrap_single_fenced_diff(text))
        )
        lines = normalized.splitlines()
        if len(lines) < 4 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
            raise InvalidPatchError("patch must start with paired unified diff headers")
        if not any(line.startswith("@@ ") for line in lines[2:]):
            raise InvalidPatchError("patch requires a hunk")
        in_hunk = False
        for line in lines[2:]:
            if line.startswith("@@ "):
                in_hunk = True
                continue
            if not in_hunk or (line and line[0] not in (" ", "+", "-", "\\")):
                raise InvalidPatchError("patch contains commentary or malformed hunk content")
        return normalized


def _unwrap_single_fenced_diff(text: str) -> str:
    stripped = text.strip()
    if "```" not in stripped:
        return text
    if stripped.count("```") != 2:
        raise InvalidPatchError("multiple fenced blocks are forbidden")

    first_fence = stripped.find("```")
    last_fence = stripped.rfind("```")
    if first_fence == last_fence:
        raise InvalidPatchError("multiple fenced blocks are forbidden")

    opening_line_end = stripped.find("\n", first_fence)
    if opening_line_end == -1 or opening_line_end >= last_fence:
        raise InvalidPatchError("patch is empty")

    opening = stripped[first_fence:opening_line_end]
    if opening == "```diff":
        inner = stripped[opening_line_end + 1:last_fence]
    elif opening == "```patch":
        inner = stripped[opening_line_end + 1:last_fence]
    elif opening == "```":
        inner = stripped[opening_line_end + 1:last_fence]
    else:
        raise InvalidPatchError("unsupported fenced patch format")
    if not inner.strip():
        raise InvalidPatchError("patch is empty")
    return inner.strip() + ("\n" if text.endswith(("\n", "\r")) else "")


def _strip_git_diff_metadata(text: str) -> str:
    lines = text.splitlines()
    normalized: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            continue
        if line.strip() == "diff":
            continue
        if line.startswith("index "):
            continue
        normalized.append(line)
    trailing_newline = "\n" if text.endswith(("\n", "\r")) else ""
    return "\n".join(normalized) + trailing_newline


_MODEL_HUNK_HEADER_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$"
)


def _normalize_model_patch_counts(text: str) -> str:
    lines = text.splitlines()
    normalized: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("@@ "):
            normalized.append(line)
            index += 1
            continue

        match = _MODEL_HUNK_HEADER_RE.match(line)
        if match is None:
            raise InvalidPatchError(f"Malformed hunk header: {line}")
        body_start = index + 1
        body_end = body_start
        while body_end < len(lines):
            candidate = lines[body_end]
            is_file_header = (
                candidate.startswith("--- ")
                and body_end + 1 < len(lines)
                and lines[body_end + 1].startswith("+++ ")
            )
            if candidate.startswith("@@ ") or is_file_header:
                break
            if not candidate or candidate[0] not in (" ", "+", "-", "\\"):
                raise InvalidPatchError("patch contains commentary or malformed hunk content")
            body_end += 1

        body = lines[body_start:body_end]
        old_count = sum(1 for item in body if item.startswith((" ", "-")))
        new_count = sum(1 for item in body if item.startswith((" ", "+")))
        if old_count == 0 and new_count == 0:
            raise InvalidPatchError("patch hunk is empty")

        declared_old = int(match.group(2)) if match.group(2) is not None else 1
        declared_new = int(match.group(4)) if match.group(4) is not None else 1
        if declared_old == old_count and declared_new == new_count:
            normalized.append(line)
        else:
            normalized.append(
                f"@@ -{match.group(1)},{old_count} +{match.group(3)},{new_count} @@{match.group(5)}"
            )
        normalized.extend(body)
        index = body_end

    trailing_newline = "\n" if text.endswith(("\n", "\r")) else ""
    return "\n".join(normalized) + trailing_newline


class PlannerResponseParser:
    @staticmethod
    def parse(text: str, *, allowed_files: tuple[str, ...]) -> PlannerOutput:
        value = _require_object(text)
        if set(value) != {"implementation_steps", "risks", "files_to_modify"}:
            raise StrategyResponseError("Planner fields must be exact")
        steps = _string_list(value["implementation_steps"], "implementation_steps", allow_empty=False)
        risks = _string_list(value["risks"], "risks", allow_empty=True)
        files = _string_list(value["files_to_modify"], "files_to_modify", allow_empty=False)
        if len(files) != len(set(files)) or any(item not in allowed_files for item in files):
            raise StrategyResponseError("Planner files are duplicated or outside allowlist")
        return PlannerOutput(steps, risks, files)


def _extract_clean_json_object(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise StrategyResponseError("response is empty")
    
    # Check for markdown code fences
    fence_count = cleaned.count("```")
    if fence_count > 0:
        if fence_count != 2:
            raise StrategyResponseError("response must contain exactly one fenced JSON block or none")
        
        # Must start with ``` and end with ```
        if not (cleaned.startswith("```") and cleaned.endswith("```")):
            raise StrategyResponseError("text before/after markdown fence is forbidden")
            
        # Strip fences
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        else:
            cleaned = cleaned[3:]
            
        cleaned = cleaned[:-3].strip()
        
        if "```" in cleaned:
            raise StrategyResponseError("multiple fenced blocks or malformed fences are forbidden")
            
    # Now verify that it looks like a single JSON object (starts with { and ends with })
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
         raise StrategyResponseError("response must be exactly one JSON object")
         
    return cleaned


class ReviewerResponseParser:
    _CATEGORIES = {
        "requirement",
        "api_usage",
        "forbidden_behavior",
        "patch_scope",
        "correctness",
        "exception_handling",
        "style",
    }

    @classmethod
    def parse(cls, text: str, *, allowed_evidence_ids: tuple[str, ...]) -> ReviewerVerdict:
        if len(text.encode("utf-8")) > 16 * 1024:
            raise StrategyResponseError("Reviewer response exceeds 16 KiB")
        
        cleaned_json = _extract_clean_json_object(text)
        try:
            value = json.loads(cleaned_json)
        except Exception as e:
            raise StrategyResponseError(f"response is not valid JSON: {e}")
            
        if not isinstance(value, dict):
            raise StrategyResponseError("response must be exactly one JSON object")
            
        if "verdict" in value and isinstance(value["verdict"], str):
            val_verdict = value["verdict"].upper()
        else:
            raise StrategyResponseError("Reviewer envelope is invalid")
            
        if set(value) != {"verdict", "issues"} or val_verdict not in ("PASS", "FAIL") or not isinstance(value["issues"], list):
            raise StrategyResponseError("Reviewer envelope is invalid")
            
        value["verdict"] = val_verdict
        
        if value["verdict"] == "PASS" and value["issues"]:
            raise StrategyResponseError("PASS requires zero issues")
        if value["verdict"] == "FAIL" and not 1 <= len(value["issues"]) <= 20:
            raise StrategyResponseError("FAIL requires 1-20 issues")
        issues: list[ReviewerIssue] = []
        for item in value["issues"]:
            if not isinstance(item, dict) or set(item) != {"category", "message", "evidence_chunk_ids"}:
                raise StrategyResponseError("Reviewer issue fields must be exact")
            if item["category"] not in cls._CATEGORIES:
                raise StrategyResponseError("unknown Reviewer category")
            message = item["message"]
            if not isinstance(message, str) or not 1 <= len(message) <= 1000:
                raise StrategyResponseError("Reviewer message length is invalid")
            ids = _string_list(item["evidence_chunk_ids"], "evidence_chunk_ids", allow_empty=True)
            if any(evidence_id not in allowed_evidence_ids for evidence_id in ids):
                raise StrategyResponseError("Reviewer cited unauthorized evidence")
            issues.append(ReviewerIssue(item["category"], message, ids))
        return ReviewerVerdict(value["verdict"], tuple(issues))


class RetrievalRequestParser:
    @staticmethod
    def parse(
        text: str,
        *,
        ledger: EvidenceLedger,
        run_id: str,
        task_id: str,
        role: str,
        phase: str,
    ) -> RetrievalRequest:
        value = _require_object(text)
        if value.get("action") != "retrieve":
            raise StrategyResponseError("retrieval action must be retrieve")
        tool = value.get("tool")
        if tool in ("keyword_search", "semantic_search"):
            if set(value) != {"action", "tool", "query", "top_k"}:
                raise StrategyResponseError("search request fields must be exact")
            query = value["query"]
            top_k = _normalize_top_k(value["top_k"])
            if not isinstance(query, str) or not query.strip() or len(query) > 4096:
                raise StrategyResponseError("retrieval query is invalid")
            try:
                assert_query_safe(query)
            except Exception as exc:
                raise StrategyResponseError(str(exc)) from exc
            if top_k < 1:
                raise StrategyResponseError("top_k must be an integer from 1 to 3")
            if top_k > 3:
                top_k = 3
            return RetrievalSearchRequest("retrieve", tool, query, top_k)
        if tool == "chunk_read":
            if set(value) != {"action", "tool", "file_path", "chunk_id"}:
                raise StrategyResponseError("chunk request fields must be exact")
            authorization = (
                run_id,
                task_id,
                role,
                phase,
                value["file_path"],
                value["chunk_id"],
            )
            allowed = any(
                (
                    item.run_id,
                    item.task_id,
                    item.role,
                    item.phase,
                    item.file_path,
                    item.chunk_id,
                )
                == authorization
                for item in ledger.search_authorizations
            )
            if ledger.run_id != run_id or ledger.task_id != task_id or not allowed:
                raise StrategyResponseError("chunk_read is not authorized for this scope")
            return RetrievalChunkReadRequest("retrieve", "chunk_read", value["file_path"], value["chunk_id"])
        raise StrategyResponseError("unknown retrieval tool")


def _load_exact_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return None


def _require_object(text: str) -> dict[str, Any]:
    value = _load_exact_json(text)
    if not isinstance(value, dict):
        raise StrategyResponseError("response must be exactly one JSON object")
    return value


def _normalize_top_k(value: Any) -> int:
    if isinstance(value, bool):
        raise StrategyResponseError("top_k must be an integer from 1 to 3")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
        try:
            as_float = float(stripped)
        except ValueError:
            raise StrategyResponseError("top_k must be an integer from 1 to 3") from None
        if as_float.is_integer():
            return int(as_float)
    raise StrategyResponseError("top_k must be an integer from 1 to 3")


def _string_list(value: Any, name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise StrategyResponseError(f"{name} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise StrategyResponseError(f"{name} must not be empty")
    return tuple(value)
