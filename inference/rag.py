"""Hybrid RAG retriever — dense (FAISS) + sparse (BM25).

Merges scores with configurable alpha weight.
Relevance threshold: if max score < 0.35, flags answer as not well-supported.
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Configuration
DEFAULT_INDEX_DIR = os.getenv("INDEX_DIR", "data/embeddings")
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
DEFAULT_ALPHA = float(os.getenv("RAG_ALPHA", "0.7"))  # Weight for dense vs sparse
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.35"))
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class HybridRetriever:
    """Hybrid BM25 + FAISS retriever with score fusion."""

    def __init__(
        self,
        index_dir: str = DEFAULT_INDEX_DIR,
        model_name: str = DEFAULT_MODEL,
        alpha: float = DEFAULT_ALPHA,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.index_dir = Path(index_dir)
        self.model_name = model_name
        self.alpha = alpha  # 0=pure BM25, 1=pure dense
        self.top_k = top_k

        self.faiss_index: Optional[faiss.IndexFlatIP] = None
        self.metadata: list[dict] = []
        self.bm25 = None
        self.bm25_chunks: list[dict] = []
        self.encoder: Optional[SentenceTransformer] = None
        self._loaded = False

    def load(self) -> None:
        """Load FAISS index, BM25 index, and embedding model."""
        # FAISS
        faiss_path = self.index_dir / "faiss.index"
        meta_path = self.index_dir / "metadata.pkl"

        if faiss_path.exists():
            self.faiss_index = faiss.read_index(str(faiss_path))
            with open(meta_path, "rb") as f:
                self.metadata = pickle.load(f)
            print(f"FAISS loaded: {self.faiss_index.ntotal} vectors", file=sys.stderr)

        # BM25
        bm25_path = self.index_dir / "bm25.pkl"
        if bm25_path.exists():
            with open(bm25_path, "rb") as f:
                data = pickle.load(f)
                self.bm25 = data["bm25"]
                self.bm25_chunks = data["chunks"]
            print(f"BM25 loaded: {len(self.bm25_chunks)} documents", file=sys.stderr)

        # Encoder
        self.encoder = SentenceTransformer(self.model_name)
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        """Check if indices are loaded."""
        return self._loaded

    @property
    def index_size(self) -> int:
        """Number of documents in the index."""
        if self.faiss_index:
            return self.faiss_index.ntotal
        return len(self.bm25_chunks)

    def _dense_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Search using FAISS dense vectors."""
        if self.faiss_index is None or self.encoder is None:
            return []

        query_vec = self.encoder.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype=np.float32)

        k = min(top_k, self.faiss_index.ntotal)
        scores, indices = self.faiss_index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append((int(idx), float(score)))
        return results

    def _sparse_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Search using BM25 sparse retrieval."""
        if self.bm25 is None:
            return []

        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]
        return results

    def _normalize_scores(self, results: list[tuple[int, float]]) -> list[tuple[int, float]]:
        """Min-max normalize scores to [0, 1]."""
        if not results:
            return []
        scores = [s for _, s in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return [(idx, 1.0) for idx, _ in results]
        return [(idx, (s - min_s) / (max_s - min_s)) for idx, s in results]

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        alpha: Optional[float] = None,
    ) -> list[dict]:
        """Hybrid search combining dense and sparse retrieval.

        Args:
            query: Search query.
            top_k: Number of results to return.
            alpha: Dense/sparse weight (0=pure BM25, 1=pure dense).

        Returns:
            List of result dicts with text, source, score, relevance flag.
        """
        if not self._loaded:
            self.load()

        top_k = top_k or self.top_k
        alpha = alpha if alpha is not None else self.alpha

        # Get results from both backends
        dense_results = self._normalize_scores(self._dense_search(query, top_k * 2))
        sparse_results = self._normalize_scores(self._sparse_search(query, top_k * 2))

        # Merge scores
        score_map: dict[int, float] = {}
        for idx, score in dense_results:
            score_map[idx] = alpha * score
        for idx, score in sparse_results:
            score_map[idx] = score_map.get(idx, 0) + (1 - alpha) * score

        # Sort by score and take top-k
        sorted_results = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Build output
        output = []
        for idx, score in sorted_results:
            if idx < len(self.metadata):
                meta = self.metadata[idx]
            elif idx < len(self.bm25_chunks):
                meta = self.bm25_chunks[idx]
            else:
                continue

            output.append({
                "chunk_id": meta.get("chunk_id", f"chunk_{idx}"),
                "source": meta.get("source", "unknown"),
                "text": meta.get("text", ""),
                "page": meta.get("page", 1),
                "score": round(score, 4),
                "relevant": score >= RELEVANCE_THRESHOLD,
            })

        return output

    def search_with_uncertainty(self, query: str, top_k: Optional[int] = None) -> dict:
        """Search and flag if results are uncertain.

        Returns:
            Dict with 'results', 'max_score', 'uncertain' keys.
        """
        results = self.search(query, top_k)

        max_score = max((r["score"] for r in results), default=0.0)
        uncertain = max_score < RELEVANCE_THRESHOLD

        return {
            "results": results,
            "max_score": round(max_score, 4),
            "uncertain": uncertain,
            "message": (
                "⚠ The retrieved material may not well cover this topic."
                if uncertain else ""
            ),
        }


# Module-level singleton
_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """Get or create the global retriever."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


if __name__ == "__main__":
    retriever = get_retriever()
    retriever.load()

    print(f"Index size: {retriever.index_size}")

    result = retriever.search_with_uncertainty("What is photosynthesis?")
    print(f"Max score: {result['max_score']}")
    print(f"Uncertain: {result['uncertain']}")
    for r in result["results"]:
        print(f"  [{r['score']:.3f}] {r['source']}: {r['text'][:80]}...")
