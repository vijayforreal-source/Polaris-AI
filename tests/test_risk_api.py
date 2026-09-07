from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_risk_status_and_vessels():
    status = client.get("/api/risk/status")
    vessels = client.get("/api/risk/vessels")
    assert status.status_code == 200
    assert status.json()["checkpoint"] == "CHECKPOINT_4"
    assert vessels.status_code == 200
    assert any(v["classification"] == "SIMULATED_VESSEL_PROFILE" for v in vessels.json()["vessels"])


def test_risk_grid_serialization_and_components():
    response = client.get(
        "/api/risk/grid", params={"horizon_hours": 12, "vessel_id": "simulated-research"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["grid_shape"] == [52, 100]
    assert len(payload["risk_grid"]) == 52
    assert (
        set(
            (
                "sea_ice_hazard",
                "iceberg_hazard",
                "uncertainty_hazard",
                "vessel_constraint_hazard",
                "historical_transit_confidence",
                "experience_bonus",
            )
        )
        <= payload["component_grids"].keys()
    )
    assert payload["metadata"]["interpolation"]["interpolation_fraction"] == 0.5


def test_point_explainability_and_validation():
    response = client.get("/api/risk/point", params={"lat": -69, "lon": 76, "horizon_hours": 24})
    assert response.status_code == 200
    payload = response.json()
    assert {
        "risk_score",
        "risk_category",
        "navigable",
        "dominant_factor",
        "components",
        "explanations",
    } <= payload.keys()
    assert any("Historical" in line or "No verified" in line for line in payload["explanations"])
    assert client.get("/api/risk/point", params={"lat": 100, "lon": 76}).status_code == 422
    assert client.get("/api/risk/grid", params={"horizon_hours": 73}).status_code == 200
    assert (
        client.get(
            "/api/risk/grid", params={"horizon_hours": 0, "vessel_id": "missing"}
        ).status_code
        == 422
    )


def test_custom_vessel_profile_endpoint():
    response = client.post(
        "/api/risk/point",
        json={
            "latitude": -69,
            "longitude": 76,
            "horizon_hours": 0,
            "vessel_profile": {
                "vessel_id": "test",
                "name": "Unknown test vessel",
                "vessel_type": "TEST",
                "source": "test",
                "provenance": "deterministic test",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["navigable"] is False
