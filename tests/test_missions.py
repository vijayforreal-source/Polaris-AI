from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_mission_lifecycle():
    response = client.post(
        "/api/operations/missions",
        json={
            "name": "Test mission",
            "vessel_id": "simulated-research",
            "origin": {"latitude": -69, "longitude": 76},
            "destination": {"latitude": -68, "longitude": 77},
        },
    )
    assert response.status_code == 200
    mission_id = response.json()["mission_id"]
    assert client.post(f"/api/operations/missions/{mission_id}/plan").json()["status"] == "PLANNED"
    assert (
        client.post(f"/api/operations/missions/{mission_id}/activate").json()["status"] == "ACTIVE"
    )
    assert client.post(f"/api/operations/missions/{mission_id}/pause").json()["status"] == "PAUSED"
    assert client.post(f"/api/operations/missions/{mission_id}/resume").json()["status"] == "ACTIVE"
    assert (
        client.post(f"/api/operations/missions/{mission_id}/complete").json()["status"]
        == "COMPLETED"
    )


def test_operations_endpoints():
    assert client.get("/api/operations/status").status_code == 200
    assert client.get("/api/operations/sources").status_code == 200
    assert client.get("/api/operations/snapshot").status_code == 200
    assert client.get("/api/operations/capabilities").status_code == 200
