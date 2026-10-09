import pytest

from ragpipeline.chunking import chunk_markdown, chunk_text, split_markdown_sections


def test_chunk_text_splits_long_input():
    text = "word " * 500
    chunks = chunk_text(text, "doc", size=200, overlap=50)
    assert len(chunks) > 1
    assert all(chunk["source_id"] == "doc" for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))


def test_chunk_text_produces_overlap():
    text = "abcdefghij " * 50
    chunks = chunk_text(text, "d", size=100, overlap=20)
    assert chunks[0]["content"][-20:] in chunks[1]["content"]


def test_chunk_ids_are_unique():
    chunks = chunk_text("word " * 400, "doc", size=100, overlap=10)
    ids = [chunk["id"] for chunk in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello", "d", size=10, overlap=10)


def test_split_markdown_sections():
    text = "# A\nbody a\n## B\nbody b"
    sections = split_markdown_sections(text)
    assert ("A", "body a") in sections
    assert ("B", "body b") in sections


def test_chunk_markdown_has_parent_and_section():
    text = "# Refunds\nRefunds within 30 days.\n## Exceptions\nGift cards excluded."
    chunks = chunk_markdown(text, "refund_policy", size=40, overlap=5)
    assert chunks
    for chunk in chunks:
        assert chunk["source_id"] == "refund_policy"
        assert chunk["parent_id"].startswith("refund_policy-p")
        assert chunk["parent_content"]
        assert chunk["section"] in ("Refunds", "Exceptions")
    parents = {chunk["parent_id"] for chunk in chunks}
    assert len(parents) >= 2


def test_chunk_markdown_parent_contains_child():
    text = "# Section\nOne two three four five six seven eight."
    chunks = chunk_markdown(text, "doc", size=20, overlap=2)
    for chunk in chunks:
        assert chunk["content"] in chunk["parent_content"]
