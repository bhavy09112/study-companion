"""Tests for inference/rag.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from inference.rag import HybridRetriever


@pytest.fixture
def test_retriever(tmp_path: Path, sample_chunk: dict) -> HybridRetriever:
    """Create a retriever with test data."""
    from pipeline.embed import EmbeddingIndex, build_bm25_index

    # Write test chunks
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(json.dumps(sample_chunk) + "\n", encoding="utf-8")

    # Build index
    index_dir = str(tmp_path / "embeddings")
    idx = EmbeddingIndex(index_dir=index_dir)
    idx.build([sample_chunk])
    idx.save()

    # Build BM25
    import pickle
    from rank_bm25 import BM25Okapi

    tokenized = [sample_chunk["text"].lower().split()]
    bm25 = BM25Okapi(tokenized)
    bm25_path = Path(index_dir) / "bm25.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": [sample_chunk]}, f)

    # Create retriever
    retriever = HybridRetriever(index_dir=index_dir)
    retriever.load()
    return retriever


class TestHybridRetriever:
    """Tests for the hybrid retriever."""

    def test_retriever_loads(self, test_retriever: HybridRetriever):
        assert test_retriever.is_loaded
        assert test_retriever.index_size > 0

    def test_search_returns_results(self, test_retriever: HybridRetriever):
        results = test_retriever.search("photosynthesis")
        assert len(results) >= 1
        assert results[0]["score"] > 0

    def test_search_has_required_fields(self, test_retriever: HybridRetriever):
        results = test_retriever.search("chlorophyll")
        assert len(results) >= 1
        result = results[0]
        assert "chunk_id" in result
        assert "source" in result
        assert "text" in result
        assert "score" in result
        assert "relevant" in result

    def test_search_with_uncertainty(self, test_retriever: HybridRetriever):
        result = test_retriever.search_with_uncertainty("photosynthesis")
        assert "results" in result
        assert "max_score" in result
        assert "uncertain" in result

    def test_irrelevant_query_low_score(self, test_retriever: HybridRetriever):
        result = test_retriever.search_with_uncertainty("quantum computing blockchain")
        # The score should be lower for unrelated queries
        assert result["max_score"] < 1.0

    def test_top_k_respected(self, test_retriever: HybridRetriever):
        results = test_retriever.search("photosynthesis", top_k=1)
        assert len(results) <= 1
