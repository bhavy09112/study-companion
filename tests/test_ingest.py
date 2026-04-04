"""Tests for pipeline/ingest.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.ingest import (
    ingest,
    ingest_pdf,
    ingest_text,
    _detect_lang,
    _extract_youtube_id,
)


class TestIngestPDF:
    """Tests for PDF ingestion."""

    def test_ingest_pdf_returns_documents(self, sample_pdf_path: str):
        """Test that PDF ingestion returns valid documents."""
        docs = ingest_pdf(sample_pdf_path)
        assert len(docs) >= 1
        assert docs[0]["source"] == "sample_input.pdf"
        assert docs[0]["page"] == 1
        assert "photosynthesis" in docs[0]["text"].lower()
        assert docs[0]["lang"] == "en"

    def test_ingest_auto_detects_pdf(self, sample_pdf_path: str):
        """Test that ingest() auto-detects PDF format."""
        docs = ingest(sample_pdf_path)
        assert len(docs) >= 1
        assert docs[0]["source"] == "sample_input.pdf"


class TestIngestText:
    """Tests for plain text ingestion."""

    def test_ingest_text_file(self, tmp_path: Path):
        """Test ingesting a .txt file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world. This is a test.", encoding="utf-8")
        docs = ingest_text(str(txt_file))
        assert len(docs) == 1
        assert "Hello world" in docs[0]["text"]

    def test_ingest_empty_file(self, tmp_path: Path):
        """Test ingesting an empty file returns nothing."""
        txt_file = tmp_path / "empty.txt"
        txt_file.write_text("", encoding="utf-8")
        docs = ingest_text(str(txt_file))
        assert len(docs) == 0


class TestHelpers:
    """Tests for helper functions."""

    def test_detect_lang_english(self):
        assert _detect_lang("This is an English sentence.") == "en"

    def test_detect_lang_chinese(self):
        assert _detect_lang("这是中文文本") == "zh"

    def test_extract_youtube_id_standard(self):
        assert _extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_youtube_id_short(self):
        assert _extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_youtube_id_invalid(self):
        assert _extract_youtube_id("https://example.com") is None

    def test_ingest_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ingest("/nonexistent/file.pdf")
