from __future__ import annotations

import ast
import hashlib
import re
from collections import Counter

from experiments.retrieval.models import Chunk

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]+")
CHUNK_LINE_LIMIT = 80
CHUNK_CHAR_LIMIT = 4000
CHUNK_OVERLAP_LINES = 10


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for match in TOKEN_RE.findall(text.casefold()):
        tokens.append(match)
        if "_" in match:
            tokens.extend(part for part in match.split("_") if part)
        if "." in match:
            tokens.extend(part for part in match.split(".") if part)
    return tuple(tokens)


def token_counts(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def _line_count(text: str) -> int:
    if text == "":
        return 1
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _split_long_lines(lines: list[str]) -> list[tuple[int, int, str]]:
    if not lines:
        return [(1, 1, "")]
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(lines):
        end = start
        chars = 0
        while end < len(lines) and end - start < CHUNK_LINE_LIMIT and chars + len(lines[end]) <= CHUNK_CHAR_LIMIT:
            chars += len(lines[end])
            end += 1
        if end == start:
            end += 1
        text = "".join(lines[start:end])
        chunks.append((start + 1, end, text))
        if end >= len(lines):
            break
        start = max(end - CHUNK_OVERLAP_LINES, start + 1)
    return chunks


def _markdown_segments(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [(1, 1, "")]
    heading_indices = [index for index, line in enumerate(lines) if re.match(r"^#{1,6}\s+", line)]
    if not heading_indices:
        return _split_long_lines(lines)
    segments: list[tuple[int, int, str]] = []
    for pos, start in enumerate(heading_indices):
        end = heading_indices[pos + 1] if pos + 1 < len(heading_indices) else len(lines)
        section_lines = lines[start:end]
        if len(section_lines) <= CHUNK_LINE_LIMIT and sum(map(len, section_lines)) <= CHUNK_CHAR_LIMIT:
            segments.append((start + 1, end, "".join(section_lines)))
        else:
            for rel_start, rel_end, chunk_text in _split_long_lines(section_lines):
                segments.append((start + rel_start, start + rel_end, chunk_text))
    return segments


def _python_segments(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [(1, 1, "")]
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _split_long_lines(lines)
    starts = sorted(
        node.lineno - 1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and hasattr(node, "lineno")
    )
    if not starts:
        return _split_long_lines(lines)
    boundaries = [0]
    for start in starts:
        if start not in boundaries:
            boundaries.append(start)
    boundaries.append(len(lines))
    boundaries = sorted(set(boundaries))
    segments: list[tuple[int, int, str]] = []
    for pos, start in enumerate(boundaries[:-1]):
        end = boundaries[pos + 1]
        if start == end:
            continue
        block = lines[start:end]
        if len(block) <= CHUNK_LINE_LIMIT and sum(map(len, block)) <= CHUNK_CHAR_LIMIT:
            segments.append((start + 1, end, "".join(block)))
        else:
            for rel_start, rel_end, chunk_text in _split_long_lines(block):
                segments.append((start + rel_start, start + rel_end, chunk_text))
    return segments


def chunk_file_text(file_path: str, text: str) -> tuple[Chunk, ...]:
    normalized = normalize_text(text)
    if file_path.endswith(".md"):
        segments = _markdown_segments(normalized)
    elif file_path.endswith(".py"):
        segments = _python_segments(normalized)
    else:
        segments = _split_long_lines(normalized.splitlines(keepends=True))

    chunks: list[Chunk] = []
    for index, (start_line, end_line, chunk_text) in enumerate(segments):
        digest = sha256_text(chunk_text)
        chunk_id = f"{file_path}#chunk_{index:04d}_{digest[:12]}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                file_path=file_path,
                chunk_index=index,
                start_line=start_line,
                end_line=end_line,
                text=chunk_text,
                sha256=digest,
                token_count=len(tokenize(chunk_text)),
            )
        )
    return tuple(chunks)


def count_lines(text: str) -> int:
    return _line_count(text)
