from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_registry_metadata() -> None:
    response = client.get("/api/icebergs/latest/metadata")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["classification"] == "OBSERVATION"
    assert metadata["provider_report_date"] == "2026-08-27"
    assert metadata["total_registry_count"] == 33
    assert metadata["valid_coordinate_count"] == 33
    assert metadata["study_region_count"] == 6
    assert metadata["rejected_record_count"] == 0


def test_registry_api_exposes_observations_without_predictions() -> None:
    response = client.get("/api/icebergs/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "study_region"
    assert len(payload["icebergs"]) == 6
    forbidden = {
        "predicted_latitude",
        "velocity",
        "heading",
        "drift_speed",
        "collision_probability",
    }
    assert all(forbidden.isdisjoint(record) for record in payload["icebergs"])


def test_all_registry_scope_is_explicit() -> None:
    response = client.get("/api/icebergs/latest?scope=all")
    assert response.status_code == 200
    assert len(response.json()["icebergs"]) == 33


def test_historical_api_preserves_observation_classification() -> None:
    response = client.get("/api/icebergs/A76C/history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"] == "OBSERVATION"
    assert payload["record_count"] == 35
    assert payload["unique_position_count"] == 34
    assert all(point["classification"] == "OBSERVATION" for point in payload["track_points"])


def test_baseline_api_separates_prediction_from_observation() -> None:
    response = client.get("/api/icebergs/A76C/baseline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "TRAJECTORY BASELINE"
    assert payload["historical_input_classification"] == "OBSERVATION"
    assert payload["prediction_classification"] == "MODEL_PREDICTION"
    assert all(item["classification"] == "MODEL_PREDICTION" for item in payload["predictions"])
    assert all("collision_probability" not in item for item in payload["predictions"])
