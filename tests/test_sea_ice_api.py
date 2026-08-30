from fastapi.testclient import TestClient

from backend.app.main import app
from backend.ingestion.config import BHARATI_PRYDZ_BAY
from backend.ingestion.copernicus_sea_ice import DATASET_ID

client = TestClient(app)


def test_latest_metadata_is_verified_observation() -> None:
    response = client.get("/api/sea-ice/latest/metadata")

    assert response.status_code == 200
    metadata = response.json()
    assert metadata["classification"] == "OBSERVATION"
    assert metadata["observation_time"] == "2026-08-29T00:00:00Z"
    assert metadata["dataset_id"] == DATASET_ID
    assert metadata["variable"] == "ice_conc"
    assert metadata["units"] == "%"
    assert metadata["grid_shape"] == [1, 45, 140]
    assert metadata["valid_count"] == 2858
    assert metadata["missing_count"] == 3442


def test_latest_grid_preserves_missing_values() -> None:
    response = client.get("/api/sea-ice/latest/grid")

    assert response.status_code == 200
    grid = response.json()
    assert len(grid["latitude"]) == 45
    assert len(grid["longitude"]) == 140
    assert len(grid["concentration"]) == 45
    assert all(len(row) == 140 for row in grid["concentration"])
    values = [value for row in grid["concentration"] for value in row]
    assert sum(value is None for value in values) == 3442
    assert 0.0 not in [value for value in values if value is not None]
    assert "does not mean 0% ice" in grid["missing_semantics"]


def test_bharati_is_inside_configured_bounds() -> None:
    assert (
        BHARATI_PRYDZ_BAY.minimum_longitude
        <= BHARATI_PRYDZ_BAY.bharati_longitude
        <= BHARATI_PRYDZ_BAY.maximum_longitude
    )
    assert (
        BHARATI_PRYDZ_BAY.minimum_latitude
        <= BHARATI_PRYDZ_BAY.bharati_latitude
        <= BHARATI_PRYDZ_BAY.maximum_latitude
    )

