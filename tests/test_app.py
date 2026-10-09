import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "hybrid" in body["modes"]


def test_ask_rejects_unknown_mode():
    client = TestClient(app)
    response = client.get("/ask", params={"q": "hi", "mode": "nope"})
    assert response.status_code == 400
