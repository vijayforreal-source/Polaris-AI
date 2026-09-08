"""Local API endpoint health check; uses TestClient and never performs downloads."""

from fastapi.testclient import TestClient

from backend.app.main import app

ENDPOINTS = (
    "/api/sea-ice/forecast/status",
    "/api/icebergs/latest/metadata",
    "/api/historical-transit/status",
    "/api/risk/status",
    "/api/routes/status",
    "/api/replanning/status",
    "/api/operations/status",
    "/api/operations/missions",
    "/api/connectivity/status",
    "/api/sync/status",
    "/api/cache/status",
)


if __name__ == "__main__":
    client = TestClient(app)
    for endpoint in ENDPOINTS:
        response = client.get(endpoint)
        state = (
            "PASS"
            if response.status_code < 400
            else "DEGRADED"
            if response.status_code < 500
            else "FAIL"
        )
        print(f"{state:8} {response.status_code:3} {endpoint}")
