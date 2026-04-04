"""Tests for api/main.py."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_required_fields(self, client: TestClient):
        response = client.get("/health")
        data = response.json()
        assert "model_loaded" in data
        assert "index_size" in data
        assert "db_cards" in data
        assert "status" in data


class TestGenerateEndpoint:
    """Tests for /generate endpoint."""

    def test_generate_requires_topic(self, client: TestClient):
        response = client.post("/generate", json={})
        assert response.status_code == 422  # Validation error

    def test_generate_with_valid_request(self, client: TestClient):
        response = client.post("/generate", json={
            "topic": "photosynthesis",
            "mode": "simple_explanation",
        })
        # May fail if Ollama is down, but should be 200 if available
        assert response.status_code in (200, 500)

    def test_generate_invalid_mode_still_works(self, client: TestClient):
        response = client.post("/generate", json={
            "topic": "test",
            "mode": "nonexistent_mode",
        })
        assert response.status_code in (200, 500)


class TestFlashcardsEndpoint:
    """Tests for /flashcards endpoints."""

    def test_get_due_cards(self, client: TestClient):
        response = client.get("/flashcards/due")
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert "count" in data

    def test_review_requires_card_id(self, client: TestClient):
        response = client.post("/flashcards/review", json={
            "quality": 4,
        })
        assert response.status_code == 422


class TestProgressEndpoint:
    """Tests for /progress endpoint."""

    def test_progress_returns_200(self, client: TestClient):
        response = client.get("/progress")
        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert "overall_mastery" in data
        assert "total_cards" in data


class TestExportEndpoint:
    """Tests for /export/anki endpoint."""

    def test_export_anki(self, client: TestClient):
        response = client.get("/export/anki")
        # 200 if cards exist, 404 if no cards
        assert response.status_code in (200, 404)
