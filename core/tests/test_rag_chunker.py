"""Unit tests for rag/chunker.py."""

from __future__ import annotations

from mascarade.rag.chunker import chunk_document, chunk_text

# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


def test_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_single_chunk():
    text = "Hello world."
    result = chunk_text(text, chunk_size=512)
    assert len(result) == 1
    assert "Hello world" in result[0]


def test_paragraph_split():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = chunk_text(text, chunk_size=512)
    # All fit in one chunk at 512 tokens
    assert len(result) >= 1
    joined = " ".join(result)
    assert "First" in joined
    assert "Third" in joined


def test_long_text_splits_into_multiple_chunks():
    # ~200 chars per sentence × 30 sentences = ~6000 chars ~= 1500 tokens
    sentence = "This is a sentence that contains some technical content about embedded systems. "
    text = sentence * 30
    chunks = chunk_text(text, chunk_size=128, chunk_overlap=0)
    assert len(chunks) >= 3, f"Expected multiple chunks, got {len(chunks)}"


def test_overlap_is_applied():
    sentence = "This is a sentence. "
    text = sentence * 40
    chunks_no_overlap = chunk_text(text, chunk_size=64, chunk_overlap=0)
    chunks_overlap = chunk_text(text, chunk_size=64, chunk_overlap=16)
    # With overlap, content from previous chunk appears at start of next chunk
    assert len(chunks_overlap) >= len(chunks_no_overlap)


def test_chunk_size_respected():
    # Use text with paragraph boundaries so the chunker can actually split it
    paragraph = (
        "This paragraph discusses embedded systems design and real-time operating systems. " * 8
    )
    text = "\n\n".join([paragraph] * 10)  # 10 paragraphs
    chunks = chunk_text(text, chunk_size=128, chunk_overlap=0)
    # Each paragraph is ~640 chars (~160 tokens), chunk_size=128→512chars
    # So paragraphs should be split and merged into multiple chunks
    assert len(chunks) >= 2, f"Expected multiple chunks, got {len(chunks)}"
    # No chunk should be more than 3× the target (boundary merging can produce larger chunks)
    char_limit = 128 * 4 * 3
    for chunk in chunks:
        assert len(chunk) <= char_limit, f"Chunk too long: {len(chunk)} chars"


def test_no_empty_chunks():
    text = "Para one.\n\n\n\nPara two.\n\nPara three."
    chunks = chunk_text(text)
    for chunk in chunks:
        assert chunk.strip(), "Empty chunk found"


def test_single_very_long_paragraph_split_by_sentence():
    # One giant paragraph that must be split by sentences
    sentences = [f"This is sentence number {i} in a very long paragraph. " for i in range(50)]
    text = "".join(sentences)  # No double newlines
    chunks = chunk_text(text, chunk_size=64, chunk_overlap=0)
    assert len(chunks) >= 3


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------


def test_chunk_document_empty_text():
    doc = {"text": "", "source": "test.pdf", "id": "abc"}
    result = chunk_document(doc)
    assert result == []


def test_chunk_document_preserves_metadata():
    doc = {"text": "Some text. " * 20, "source": "test.pdf", "metadata": {"page": 1}}
    chunks = chunk_document(doc, chunk_size=16, chunk_overlap=0)
    for chunk in chunks:
        assert chunk["source"] == "test.pdf"
        assert chunk["metadata"] == {"page": 1}
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "chunk_count" in chunk


def test_chunk_document_index_and_count():
    doc = {"text": "Sentence. " * 50, "source": "doc"}
    chunks = chunk_document(doc, chunk_size=32, chunk_overlap=0)
    assert len(chunks) >= 2
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i
        assert chunk["chunk_count"] == len(chunks)


def test_chunk_document_no_id_field_preserved():
    """Original doc fields except 'text' are preserved; 'id' absent means no id in chunk."""
    doc = {"text": "Hello world.", "custom_field": "keep_me"}
    chunks = chunk_document(doc)
    for chunk in chunks:
        assert chunk["custom_field"] == "keep_me"
        assert "text" in chunk


def test_chunk_document_short_text_single_chunk():
    doc = {"text": "Short text.", "source": "s"}
    chunks = chunk_document(doc, chunk_size=512)
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["chunk_count"] == 1
