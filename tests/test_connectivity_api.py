from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_connectivity_api():
    assert client.get("/api/connectivity/status").status_code == 200
    assert client.get("/api/connectivity/policy").status_code == 200
    assert client.get("/api/sync/status").status_code == 200
    assert client.get("/api/sync/tasks").status_code == 200
    assert client.get("/api/cache/status").status_code == 200
    assert client.post("/api/connectivity/override", json={"state": "OFFLINE"}).status_code == 200
    assert client.post("/api/connectivity/refresh").status_code == 200
