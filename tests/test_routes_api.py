from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_routes_status():
    response = client.get("/api/routes/status")
    assert response.status_code == 200
    assert response.json()["supported_objectives"] == ["SAFE", "FAST", "ECO", "BALANCED"]


def test_routes_plan_rejects_unknown_vessel():
    response = client.post(
        "/api/routes/plan",
        json={
            "origin": {"latitude": -69, "longitude": 76},
            "destination": {"latitude": -68, "longitude": 77},
            "departure_time": "2026-01-01T00:00:00Z",
            "vessel_id": "not-a-vessel",
        },
    )
    assert response.status_code == 422


def test_routes_plan_valid_request_returns_explicit_environment_status():
    response = client.post(
        "/api/routes/plan",
        json={
            "origin": {"latitude": -69, "longitude": 76},
            "destination": {"latitude": -68, "longitude": 77},
            "departure_time": "2026-01-01T00:00:00Z",
            "vessel_id": "simulated-research",
        },
    )
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert "routes" in response.json() and "failures" in response.json()
