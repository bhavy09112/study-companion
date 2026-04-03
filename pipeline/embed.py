"""Embedding and FAISS index builder.

Builds a dense vector index (FAISS) + sparse BM25 index for hybrid retrieval.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Defaults
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_INDEX_DIR = "data/embeddings"
DEFAULT_BATCH_SIZE = 32


class EmbeddingIndex:
    """Manages FAISS index and metadata for dense retrieval."""

    def __init__(self, model_name: str = DEFAULT_MODEL, index_dir: str = DEFAULT_INDEX_DIR):
        self.model_name = model_name
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: list[dict] = []

    def _load_model(self) -> None:
        """Lazy-load the embedding model."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)

    def build(self, chunks: list[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """Build FAISS index from chunks.

        Args:
            chunks: List of chunk dicts with 'text', 'chunk_id', 'source' keys.
            batch_size: Encoding batch size.
        """
        self._load_model()
        assert self.model is not None

        texts = [c["text"] for c in chunks]
        print(f"Encoding {len(texts)} chunks with {self.model_name}...", file=sys.stderr)

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # Inner product (cosine sim for normalized vecs)
        self.index.add(embeddings)

        self.metadata = [
            {
                "chunk_id": c["chunk_id"],
                "source": c["source"],
                "text": c["text"],
                "tokens": c.get("tokens", 0),
                "page": c.get("page", 1),
            }
            for c in chunks
        ]

        print(f"FAISS index built: {self.index.ntotal} vectors, dim={dim}", file=sys.stderr)

    def save(self) -> None:
        """Save FAISS index and metadata to disk."""
        if self.index is None:
            raise RuntimeError("No index to save. Call build() first.")

        faiss.write_index(self.index, str(self.index_dir / "faiss.index"))
        with open(self.index_dir / "metadata.pkl", "wb") as f:
            pickle.dump(self.metadata, f)
        with open(self.index_dir / "config.json", "w") as f:
            json.dump({"model_name": self.model_name, "num_vectors": self.index.ntotal}, f)

        print(f"Index saved to {self.index_dir}", file=sys.stderr)

    def load(self) -> None:
        """Load FAISS index and metadata from disk."""
        index_path = self.index_dir / "faiss.index"
        meta_path = self.index_dir / "metadata.pkl"

        if not index_path.exists():
            raise FileNotFoundError(f"No index found at {index_path}")

        self.index = faiss.read_index(str(index_path))
        with open(meta_path, "rb") as f:
            self.metadata = pickle.load(f)

        print(f"Loaded index with {self.index.ntotal} vectors", file=sys.stderr)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the index for the given query.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of dicts with metadata + score.
        """
        self._load_model()
        assert self.model is not None
        assert self.index is not None

        query_vec = self.model.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype=np.float32)

        scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            result = {**self.metadata[idx], "score": float(score)}
            results.append(result)

        return results

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        return self.index.ntotal if self.index else 0


def build_bm25_index(chunks: list[dict]) -> None:
    """Build and save a BM25 index for sparse retrieval.

    Args:
        chunks: List of chunk dicts with 'text' key.
    """
    from rank_bm25 import BM25Okapi

    tokenized = [c["text"].lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)

    index_dir = Path(DEFAULT_INDEX_DIR)
    index_dir.mkdir(parents=True, exist_ok=True)

    with open(index_dir / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)

    print(f"BM25 index saved ({len(chunks)} documents)", file=sys.stderr)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build embedding index for study companion")
    parser.add_argument("--input", "-i", required=True, help="Input JSONL file with chunks")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Embedding model (default: {DEFAULT_MODEL})")
    parser.add_argument("--index-dir", default=DEFAULT_INDEX_DIR, help=f"Index directory (default: {DEFAULT_INDEX_DIR})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    lines = Path(args.input).read_text(encoding="utf-8").strip().split("\n")
    chunks = [json.loads(line) for line in lines if line.strip()]

    if not chunks:
        print("No chunks to index", file=sys.stderr)
        return

    # Build FAISS index
    idx = EmbeddingIndex(model_name=args.model, index_dir=args.index_dir)
    idx.build(chunks, batch_size=args.batch_size)
    idx.save()

    # Build BM25 index
    build_bm25_index(chunks)

    print(f"All indices built: {idx.size} vectors", file=sys.stderr)


if __name__ == "__main__":
    main()
