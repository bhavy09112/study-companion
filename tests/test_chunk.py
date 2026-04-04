"""Tests for pipeline/chunk.py."""
from __future__ import annotations

import pytest

from pipeline.chunk import (
    chunk_document,
    chunk_documents,
    semantic_split,
    merge_small_segments,
    sliding_window_split,
    estimate_tokens,
    generate_chunk_id,
)


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 1  # Minimum is 1

    def test_known_length(self):
        text = "word " * 100  # 500 chars
        tokens = estimate_tokens(text)
        assert 100 <= tokens <= 200

    def test_short_text(self):
        assert estimate_tokens("hi") >= 1


class TestSemanticSplit:
    """Tests for semantic splitting."""

    def test_splits_on_double_newline(self):
        text = "First paragraph.\n\nSecond paragraph."
        segments = semantic_split(text)
        assert len(segments) >= 2

    def test_single_paragraph(self):
        text = "Just one paragraph with no breaks."
        segments = semantic_split(text)
        assert len(segments) >= 1


class TestMergeSmallSegments:
    """Tests for segment merging."""

    def test_merges_small_segments(self):
        segments = ["Small.", "Also small.", "Tiny."]
        merged = merge_small_segments(segments, max_tokens=500)
        assert len(merged) == 1  # All should merge into one

    def test_preserves_large_segments(self):
        segments = ["x " * 300, "y " * 300]
        merged = merge_small_segments(segments, max_tokens=100)
        assert len(merged) == 2


class TestSlidingWindowSplit:
    """Tests for sliding window fallback."""

    def test_short_text_no_split(self):
        text = "Short text."
        chunks = sliding_window_split(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1

    def test_long_text_splits(self):
        text = "word " * 1000
        chunks = sliding_window_split(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1


class TestChunkDocument:
    """Tests for document chunking."""

    def test_chunk_basic_document(self, sample_documents):
        doc = sample_documents[0]
        chunks = chunk_document(doc, chunk_size=500, overlap=50)
        assert len(chunks) >= 1
        assert all("chunk_id" in c for c in chunks)
        assert all("text" in c for c in chunks)
        assert all("tokens" in c for c in chunks)
        assert all("source" in c for c in chunks)

    def test_chunk_preserves_source(self, sample_documents):
        doc = sample_documents[0]
        chunks = chunk_document(doc)
        assert all(c["source"] == "test_doc.pdf" for c in chunks)


class TestGenerateChunkId:
    """Tests for chunk ID generation."""

    def test_deterministic(self):
        id1 = generate_chunk_id("src", 0, "text")
        id2 = generate_chunk_id("src", 0, "text")
        assert id1 == id2

    def test_different_for_different_text(self):
        id1 = generate_chunk_id("src", 0, "text1")
        id2 = generate_chunk_id("src", 0, "text2")
        assert id1 != id2
