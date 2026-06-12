from experiments.retrieval.chunking import chunk_file_text, tokenize


def test_markdown_chunk_ids_are_deterministic():
    text = "# API\n\nDetails\r\n## Usage\nCall function\n"

    left = chunk_file_text("student_system/API_SPEC.md", text)
    right = chunk_file_text("student_system/API_SPEC.md", text.replace("\r\n", "\n"))

    assert [chunk.chunk_id for chunk in left] == [chunk.chunk_id for chunk in right]
    assert all(chunk.file_path == "student_system/API_SPEC.md" for chunk in left)


def test_empty_file_produces_one_empty_chunk():
    chunks = chunk_file_text("student_system/EMPTY.md", "")

    assert len(chunks) == 1
    assert chunks[0].text == ""
    assert chunks[0].token_count == 0


def test_duplicate_chunks_are_retained_with_distinct_ids():
    left = chunk_file_text("student_system/A.md", "same\n")
    right = chunk_file_text("student_system/B.md", "same\n")

    assert left[0].sha256 == right[0].sha256
    assert left[0].chunk_id != right[0].chunk_id


def test_tokenizer_is_deterministic_for_identifiers_numbers_and_cjk():
    assert tokenize("score_to_gpa v2.0 學生") == ("score_to_gpa", "score", "to", "gpa", "v2", "0", "學生")
