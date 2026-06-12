from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from experiments.retrieval.models import (
    CorpusPathError,
    DenylistedCorpusError,
    RetrievalPermissionError,
    SensitiveQueryError,
)
from experiments.runtime.guards import PathEscapeError, SecurityGuards

DENIED_ROOT_PREFIXES = (
    ("evaluation", "hidden_tests"),
    ("evaluation", "reference_patches"),
    ("results",),
    ("workspaces",),
    (".git",),
)
DENIED_COMPONENTS = {
    "__pycache__",
    ".pytest_cache",
    "cache",
    "caches",
    "index",
    "indexes",
    "artifact",
    "artifacts",
    "summary",
    "summaries",
}
DENIED_SUFFIXES = {".pyc", ".pyo"}

_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def assert_strategy_e(strategy: Any) -> None:
    if strategy != "E":
        raise RetrievalPermissionError("retrieval is only available for Strategy E")


def assert_agent_role(agent_role: Any) -> None:
    if agent_role not in ("Planner", "Coder", "Reviewer"):
        raise RetrievalPermissionError(f"invalid retrieval agent_role: {agent_role!r}")


def _path_components(path: str) -> tuple[str, ...]:
    normalized = path.replace("\\", "/")
    return tuple(part.casefold() for part in normalized.split("/") if part not in ("", "."))


def is_absolute_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("/") or bool(_WINDOWS_ABSOLUTE_RE.match(path))


def is_denylisted_repo_path(path: str) -> bool:
    if is_absolute_path(path):
        return True

    parts = _path_components(path)
    if any(part == ".." for part in parts):
        return True

    for prefix in DENIED_ROOT_PREFIXES:
        if parts[: len(prefix)] == prefix:
            return True

    if any(part in DENIED_COMPONENTS for part in parts):
        return True

    suffix = Path(parts[-1]).suffix.casefold() if parts else ""
    return suffix in DENIED_SUFFIXES


def assert_corpus_path_allowed(repo_relative_path: str) -> str:
    normalized = repo_relative_path.replace("\\", "/")
    if is_denylisted_repo_path(normalized):
        raise DenylistedCorpusError(f"denylisted corpus path: {repo_relative_path}")
    return normalized


def assert_resolved_under_base(target_path: Path, approved_base: Path) -> None:
    try:
        SecurityGuards.assert_safe_path(target_path, approved_base)
    except PathEscapeError as exc:
        raise CorpusPathError(str(exc)) from exc


def _looks_path_like(token: str) -> bool:
    stripped = _normalize_query_candidate(token.strip(".,;:()[]{}\"'"))
    if not stripped:
        return False
    if is_absolute_path(stripped):
        return True
    if "/" in stripped or "\\" in stripped:
        return True
    lowered = stripped.casefold()
    return any(lowered.startswith("/".join(prefix) + "/") for prefix in DENIED_ROOT_PREFIXES)


def assert_query_safe(query: str) -> None:
    for raw_token in query.split():
        candidate = _normalize_query_candidate(raw_token.strip(".,;:()[]{}\"'"))
        if _looks_path_like(candidate) and is_denylisted_repo_path(candidate):
            raise SensitiveQueryError("query contains a sensitive path-like candidate")


def _normalize_query_candidate(token: str) -> str:
    return (
        token.replace("%2f", "/")
        .replace("%2F", "/")
        .replace("%5c", "\\")
        .replace("%5C", "\\")
    )
