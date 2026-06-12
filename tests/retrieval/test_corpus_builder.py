import json

import pytest

from experiments.retrieval.corpus import CorpusBuilder
from experiments.retrieval.models import (
    CorpusDecodeError,
    CorpusPathError,
    DenylistedCorpusError,
    RetrievalTaskSpec,
    SnapshotIntegrityError,
)


def test_allowed_corpus_builds_from_snapshot(retrieval_task_spec, repo_root):
    corpus = CorpusBuilder(repo_root).build(retrieval_task_spec)

    assert corpus.task_id == "T01"
    assert {item.file_path for item in corpus.files} == set(retrieval_task_spec.allowed_corpus)
    assert all("evaluation/hidden_tests" not in chunk.text for chunk in corpus.chunks)


def test_snapshot_hash_mismatch_fails_closed(synthetic_repo_root, synthetic_retrieval_task_spec):
    target = synthetic_repo_root / "student_system/API_SPEC.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nMUTATED", encoding="utf-8")

    with pytest.raises(SnapshotIntegrityError):
        CorpusBuilder(synthetic_repo_root).build(synthetic_retrieval_task_spec)


def test_corpus_hash_is_stable_for_same_snapshot_and_input_reorder(build_synthetic_repo, tmp_path):
    root = build_synthetic_repo(tmp_path / "repo")
    spec_left = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md", "student_system/STYLE_GUIDE.md"))
    spec_right = RetrievalTaskSpec("T01", tuple(reversed(spec_left.allowed_corpus)))

    left = CorpusBuilder(root).build(spec_left)
    right = CorpusBuilder(root).build(spec_right)

    assert left.corpus_hash == right.corpus_hash
    assert [chunk.chunk_id for chunk in left.chunks] == [chunk.chunk_id for chunk in right.chunks]


def test_lf_crlf_raw_snapshot_hash_difference_uses_synthetic_repo(build_synthetic_repo, tmp_path):
    spec = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))
    lf_root = build_synthetic_repo(tmp_path / "lf", newline="\n")
    crlf_root = build_synthetic_repo(tmp_path / "crlf", newline="\r\n")

    lf = CorpusBuilder(lf_root).build(spec)
    crlf = CorpusBuilder(crlf_root).build(spec)

    assert lf.files[0].snapshot_sha256 != crlf.files[0].snapshot_sha256
    assert lf.files[0].normalized_sha256 == crlf.files[0].normalized_sha256
    assert lf.corpus_hash != crlf.corpus_hash


def test_denied_paths_fail_before_partial_corpus(repo_root):
    for path in (
        "evaluation/hidden_tests/test_t01.py",
        "evaluation/reference_patches/T01.diff",
        "results/raw/results.jsonl",
        "workspaces/run_1/student_system/API_SPEC.md",
        ".git/config",
        "student_system/cache/API_SPEC.md",
    ):
        with pytest.raises(DenylistedCorpusError):
            CorpusBuilder(repo_root).build(RetrievalTaskSpec("T01", (path,)))


def test_mixed_slash_escape_is_rejected(repo_root):
    with pytest.raises(CorpusPathError):
        CorpusBuilder(repo_root).build(RetrievalTaskSpec("T01", ("student_system\\..\\evaluation\\hidden_tests\\test_t01.py",)))


def test_normal_substring_filenames_are_allowed_when_snapshot_tracked(build_synthetic_repo, tmp_path):
    root = build_synthetic_repo(tmp_path / "repo")
    spec = RetrievalTaskSpec("T01", ("student_system/src/result_formatter.py", "student_system/docs/runtime_notes.md"))

    corpus = CorpusBuilder(root).build(spec)

    assert {item.file_path for item in corpus.files} == set(spec.allowed_corpus)


def test_empty_allowed_corpus_and_duplicate_paths_are_rejected(repo_root):
    with pytest.raises(CorpusPathError):
        CorpusBuilder(repo_root).build(RetrievalTaskSpec("T01", ()))
    with pytest.raises(CorpusPathError):
        CorpusBuilder(repo_root).build(RetrievalTaskSpec("T01", ("student_system/API_SPEC.md", "student_system/API_SPEC.md")))


def test_public_test_must_be_explicitly_allowed_and_snapshot_tracked(repo_root):
    spec = RetrievalTaskSpec("T01", ("student_system/tests/public/test_t01.py",))

    corpus = CorpusBuilder(repo_root).build(spec)

    assert corpus.files[0].file_path == "student_system/tests/public/test_t01.py"


def test_snapshot_missing_field_duplicate_path_and_illegal_sha_fail(build_synthetic_repo, tmp_path):
    root = build_synthetic_repo(tmp_path / "repo")
    snapshot_path = root / "student_system/SNAPSHOT.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    del snapshot["files"][0]["sha256"]
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotIntegrityError):
        CorpusBuilder(root).build(RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)))

    root = build_synthetic_repo(tmp_path / "repo_dup")
    snapshot_path = root / "student_system/SNAPSHOT.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["files"].append(dict(snapshot["files"][0]))
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotIntegrityError):
        CorpusBuilder(root).build(RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)))

    root = build_synthetic_repo(tmp_path / "repo_sha")
    snapshot_path = root / "student_system/SNAPSHOT.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["files"][0]["sha256"] = "not-a-sha"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotIntegrityError):
        CorpusBuilder(root).build(RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)))


def test_malformed_utf8_and_oversized_files_fail_closed(build_synthetic_repo, tmp_path):
    malformed = {"student_system/BAD.md": b"\xff\xfe\xfd"}
    root = build_synthetic_repo(tmp_path / "bad_utf8", extra_files=malformed)
    with pytest.raises(CorpusDecodeError):
        CorpusBuilder(root).build(RetrievalTaskSpec("T01", ("student_system/BAD.md",)))

    oversized = {"student_system/BIG.md": b"a" * (1024 * 1024 + 1)}
    root = build_synthetic_repo(tmp_path / "big", extra_files=oversized)
    with pytest.raises(CorpusPathError):
        CorpusBuilder(root).build(RetrievalTaskSpec("T01", ("student_system/BIG.md",)))
