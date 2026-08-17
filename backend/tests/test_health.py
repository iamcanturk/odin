"""Smoke tests for the app skeleton."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_openapi_available() -> None:
    client = TestClient(create_app())
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "ODIN API"
