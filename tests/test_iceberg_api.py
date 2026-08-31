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


def test_a76c_physics_evaluation_is_hindcast_model_output() -> None:
    response = client.get("/api/icebergs/A76C/physics-evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_mode"] == "HINDCAST"
    assert payload["prediction_classification"] == "MODEL_PREDICTION"
    assert payload["forcing"]["ocean_classification"] == "ANALYSIS"
    assert payload["forcing"]["wind_classification"] == "REANALYSIS"
    assert payload["models"]["P3_WDE17_SURFACE"]["n"] == 33
    assert "forecast" not in payload["label"].lower()


def test_hybrid_api_exposes_locked_hindcast_without_operational_claim() -> None:
    response = client.get("/api/icebergs/A76C/hybrid-evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_mode"] == "HISTORICAL HINDCAST"
    assert payload["prediction_classification"] == "MODEL_PREDICTION"
    assert payload["selected_lambda"] == 0.45
    assert payload["split"]["final_test"]["intervals"] == 7
    assert payload["selected_production_candidate"] == "P2_SURFACE_CURRENT"
    assert "hindcast_example" not in payload


def test_hybrid_hindcast_endpoint_has_real_endpoint_and_uncertainty() -> None:
    response = client.get("/api/icebergs/A76C/hybrid-hindcast/2026-08-27")
    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction_classification"] == "MODEL_PREDICTION"
    assert payload["evaluation_mode"] == "HISTORICAL HINDCAST"
    assert payload["actual_endpoint"]["date"] == "2026-08-27"
    assert len(payload["trajectory"]) > 2
    assert set(payload["uncertainty_radii_km"]) == {"50", "80", "95"}
    assert client.get("/api/icebergs/A76C/hybrid-hindcast/2026-01-01").status_code == 404
