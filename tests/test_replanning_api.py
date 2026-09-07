from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_replanning_status():
    response = client.get("/api/replanning/status")
    assert response.status_code == 200
    assert "KEEP_CURRENT" in response.json()["supported_decisions"]


def test_active_route_requires_activation():
    response = client.get("/api/replanning/active")
    assert response.status_code in (200, 404)
