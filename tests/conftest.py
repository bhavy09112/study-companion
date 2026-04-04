"""Shared fixtures for tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_pdf_path() -> str:
    """Path to the sample PDF."""
    return str(Path(__file__).parent.parent / "examples" / "sample_input.pdf")


@pytest.fixture
def sample_text() -> str:
    """Sample study text."""
    return (
        "Photosynthesis is the process by which green plants convert "
        "light energy into chemical energy stored in glucose. "
        "The equation is 6CO2 + 6H2O + light -> C6H12O6 + 6O2. "
        "Key components include chlorophyll, thylakoid membranes, "
        "and the Calvin Cycle."
    )


@pytest.fixture
def sample_chunk(sample_text: str) -> dict:
    """A sample chunk dict."""
    return {
        "chunk_id": "test::chunk_0::abc12345",
        "source": "test_doc.pdf",
        "text": sample_text,
        "tokens": len(sample_text) // 4,
        "page": 1,
    }


@pytest.fixture
def sample_documents(sample_text: str) -> list[dict]:
    """Sample ingested documents."""
    return [
        {
            "source": "test_doc.pdf",
            "page": 1,
            "text": sample_text,
            "lang": "en",
        }
    ]


@pytest.fixture
def sample_dataset_entry(sample_text: str) -> dict:
    """A sample dataset JSONL entry."""
    return {
        "instruction": "Explain photosynthesis in simple terms.",
        "input": sample_text,
        "output": "Photosynthesis is how plants make food using sunlight.",
        "metadata": {
            "source": "test_doc.pdf",
            "domain": "stem",
            "output_mode": "simple_explanation",
            "difficulty": "beginner",
        },
    }


@pytest.fixture
def tmp_jsonl(tmp_path: Path, sample_chunk: dict) -> str:
    """Create a temporary JSONL file with sample chunks."""
    path = tmp_path / "test_chunks.jsonl"
    path.write_text(json.dumps(sample_chunk) + "\n", encoding="utf-8")
    return str(path)
