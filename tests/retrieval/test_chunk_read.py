import json

import pytest

from experiments.retrieval.models import ChunkFileMismatchError, RetrievalTaskSpec, UnknownChunkError, UnknownFileError
from experiments.retrieval.service import RetrievalFacade


def test_chunk_read_returns_exact_chunk(strategy_e_session):
    search = strategy_e_session.keyword_search("course", top_k=1)
    hit = search.hits[0]

    read = strategy_e_session.chunk_read(hit.file_path, hit.chunk_id)

    assert read.tool_name == "chunk_read"
    assert read.file_path == hit.file_path
    assert read.chunk_id == hit.chunk_id
    assert read.text
    assert json.loads(read.query) == {"chunk_id": hit.chunk_id, "file_path": hit.file_path}


def test_chunk_read_rejects_unknown_file_and_chunk(strategy_e_session):
    with pytest.raises(UnknownFileError):
        strategy_e_session.chunk_read("student_system/NOPE.md", "x")
    with pytest.raises(UnknownChunkError):
        strategy_e_session.chunk_read("student_system/API_SPEC.md", "missing")


def test_chunk_read_rejects_file_chunk_mismatch(build_synthetic_repo, tmp_path):
    root = build_synthetic_repo(
        tmp_path / "repo",
        extra_files={
            "student_system/A.md": b"alpha\n",
            "student_system/B.md": b"beta\n",
        },
    )
    spec = RetrievalTaskSpec("T01", ("student_system/A.md", "student_system/B.md"))
    facade = RetrievalFacade()
    store = facade.build_store(spec=spec, repo_root=root, strategy="E")
    session = facade.create_session(run_id="run_chunk_mismatch", strategy="E", agent_role="Planner", store=store)
    chunk_from_a = next(chunk for chunk in store.corpus.chunks if chunk.file_path == "student_system/A.md")

    with pytest.raises(ChunkFileMismatchError):
        session.chunk_read("student_system/B.md", chunk_from_a.chunk_id)
