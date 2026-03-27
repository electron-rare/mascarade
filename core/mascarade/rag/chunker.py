"""Text chunker for RAG ingestion.

Splits documents into overlapping chunks suitable for embedding.
No external dependencies — pure Python regex-based splitting.

Strategy:
  1. Split on paragraph boundaries (double newline).
  2. Sub-split long paragraphs on sentence boundaries (. ! ? …).
  3. Merge short adjacent chunks up to ``chunk_size`` tokens.
  4. Add ``overlap`` tokens of leading context from the previous chunk.

Token estimate: 1 token ≈ 4 characters (English / code average).
"""

from __future__ import annotations

import re

# Sentence split pattern — handles Latin and CJK sentence endings
_SENTENCE_RE = re.compile(r"(?<=[.!?…。！？])\s*")


def _chars_per_token(text: str) -> float:
    """Estimate chars/token ratio.  CJK scripts average ~1.5 chars/token vs ~4 for Latin."""
    if not text:
        return 4.0
    # Sample first 500 chars to detect script
    sample = text[:500]
    cjk_count = sum(1 for c in sample if "\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff" or "\uac00" <= c <= "\ud7af")
    cjk_ratio = cjk_count / max(len(sample), 1)
    if cjk_ratio > 0.3:
        return 1.5  # CJK-heavy text
    return 4.0  # Latin/code


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    min_chunk_size: int = 20,
) -> list[str]:
    """Split ``text`` into overlapping token-sized chunks.

    Args:
        text: The input document text.
        chunk_size: Target chunk size in tokens.
        chunk_overlap: Number of tokens of overlap between adjacent chunks.
        min_chunk_size: Chunks shorter than this (tokens) are merged with the next.

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    cpt = _chars_per_token(text)
    max_chars = int(chunk_size * cpt)
    overlap_chars = int(chunk_overlap * cpt)
    min_chars = int(min_chunk_size * cpt)

    # Step 1: split on paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # Step 2: sub-split long paragraphs into sentences
    units: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            units.append(para)
        else:
            sentences = _SENTENCE_RE.split(para)
            units.extend(s.strip() for s in sentences if s.strip())

    # Step 3: merge units into chunks up to max_chars
    chunks: list[str] = []
    current = ""

    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= max_chars:
            current = current + " " + unit
        else:
            # Flush current chunk if long enough
            if len(current) >= min_chars:
                chunks.append(current)
            elif chunks:
                # Merge short chunk into the previous one
                chunks[-1] = chunks[-1] + " " + current
            current = unit

    if current:
        if len(current) >= min_chars and chunks:
            chunks.append(current)
        elif current and not chunks:
            chunks.append(current)
        elif chunks:
            chunks[-1] = chunks[-1] + " " + current

    # Step 4: add overlap context from previous chunk
    if chunk_overlap <= 0 or len(chunks) <= 1:
        return chunks

    overlapped: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        # Take the last overlap_chars characters of the previous chunk
        tail = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
        # Find a word boundary to avoid cutting mid-word
        space_idx = tail.find(" ")
        if space_idx != -1:
            tail = tail[space_idx + 1 :]
        overlapped.append(tail + " " + chunks[i] if tail else chunks[i])

    return overlapped


def chunk_document(
    doc: dict,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[dict]:
    """Chunk a document dict (with ``text`` key) into multiple chunk dicts.

    Preserves all original metadata; adds ``chunk_index`` and ``chunk_count``
    fields to each output dict.

    Args:
        doc: Document dict with at least a ``text`` key.
        chunk_size: Target chunk size in tokens.
        chunk_overlap: Token overlap between adjacent chunks.

    Returns:
        List of chunk dicts inheriting doc metadata.
    """
    text = doc.get("text", "")
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if not chunks:
        return []

    base = {k: v for k, v in doc.items() if k != "text"}
    result = []
    for i, chunk in enumerate(chunks):
        result.append(
            {
                **base,
                "text": chunk,
                "chunk_index": i,
                "chunk_count": len(chunks),
            }
        )
    return result
