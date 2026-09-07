from datetime import UTC, date, datetime

import numpy as np
import pytest
import torch
import xarray as xr
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.forecasting.sea_ice import operational as op
from backend.forecasting.sea_ice.ml.atmospheric import load_daily_forcing
from backend.forecasting.sea_ice.ml.dataset import (
    SeaIceWindowDataset,
    training_forcing_statistics,
)
from backend.forecasting.sea_ice.ml.network import BoundedPersistenceResidualCNN
from backend.forecasting.sea_ice.models import SeaIceSplit


@pytest.fixture
def cube():
    times = np.arange(np.datetime64("2025-01-01"), np.datetime64("2025-01-13"))
    values = np.full((12, 52, 100), 50, dtype="float32")
    values[:, 0, 0] = np.nan
    return xr.Dataset(
        {
            "ice_conc": (("time", "latitude", "longitude"), values),
            "valid_ocean_mask": (("latitude", "longitude"), np.isfinite(values[0])),
        },
        coords={
            "time": times,
            "latitude": np.linspace(-73, -63, 52),
            "longitude": np.linspace(67, 87, 100),
        },
    )


@pytest.fixture
def service(monkeypatch, cube):
    monkeypatch.setattr(op, "source_cube", lambda: cube)
    monkeypatch.setattr(op, "latest_source", lambda value: value)
    model = BoundedPersistenceResidualCNN(forcing_variables=3)
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    metadata = {"forcing_normalization": {v: {"mean": 0, "std": 1} for v in ("u10", "v10", "t2m")}}
    monkeypatch.setattr(op, "_model", lambda *args: (model, metadata))
    monkeypatch.setattr(op, "_forcing", lambda *args: np.ones((12, 3, 52, 100)))
    # Artifact existence must not be a prerequisite for isolated tests.
    monkeypatch.setattr(op.Path, "is_file", lambda *args: True)
    original_stat = op.Path.stat

    def stat(path, *args, **kwargs):
        if str(path).endswith((".pt", ".nc")):
            from types import SimpleNamespace

            return SimpleNamespace(st_mtime_ns=1)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(op.Path, "stat", stat)
    return model


def test_registry_and_frozen_decision():
    registry = op.registry()
    results = op.results()
    assert registry["model_version"] == "v0.3"
    assert registry["forcing_variables"] == ["u10", "v10", "t2m"]
    assert results["test_sample_count"] == 584
    assert results["summary"]["decision"] == "ADOPT_V03"
    assert results["clipping"]["clipped_valid_values"] == 0
    assert len(registry["weights_sha256"]) == 64


def test_training_features_equal_inference_without_future_inputs(cube):
    split = SeaIceSplit(name="test", start=date(2025, 1, 1), end=date(2025, 1, 12))
    data = SeaIceWindowDataset.from_xarray(cube, split)
    expected = data[0]["features"].numpy()
    data.concentration[7:] = 0
    np.testing.assert_array_equal(expected, data.features_at(6))
    assert expected.shape == (17, 52, 100)


def test_normalization_uses_training_only():
    times = np.array(["2023-12-31", "2024-01-01"], dtype="datetime64[D]")
    forcing = np.array([[[[1, 3]]] * 3, [[[1000, 2000]]] * 3])
    split = SeaIceSplit(name="train", start=date(2023, 1, 1), end=date(2023, 12, 31))
    mean, std = training_forcing_statistics(forcing, times, split)
    np.testing.assert_array_equal(mean, [2, 2, 2])
    np.testing.assert_array_equal(std, [1, 1, 1])


def test_same_day_future_forcing_is_rejected(tmp_path):
    times = np.array(["2025-01-01T12:00"], dtype="datetime64[ns]")
    path = tmp_path / "forcing.nc"
    xr.Dataset(
        {v: (("time", "latitude", "longitude"), np.ones((1, 2, 2))) for v in ("u10", "v10", "t2m")},
        coords={"time": times, "latitude": [0, 1], "longitude": [0, 1]},
    ).to_netcdf(path)
    with pytest.raises(ValueError, match="00:00 UTC"):
        load_daily_forcing(path, times, np.array([0, 1]), np.array([0, 1]))


def test_historical_prediction_shape_masks_and_zero_residual(service):
    result = op.forecast(date(2025, 1, 7))
    assert result["mode"] == "MODEL_PREDICTION"
    assert result["forcing_classification"] == "REANALYSIS"
    assert result["classification"] == "HISTORICAL_FORECAST_BENCHMARK"
    assert result["grid_shape"] == [52, 100]
    for field in result["forecasts"]:
        assert field["grid"]["concentration"][0][0] is None
        assert field["grid"]["concentration"][1][1] == 50
        assert field["target_classification"] == "OBSERVATION"
        assert field["classification"] == "MODEL_PREDICTION"


def test_v03_raw_bounds_and_v02_state_loading():
    torch.manual_seed(26059)
    for variables in (0, 3):
        model = BoundedPersistenceResidualCNN(forcing_variables=variables)
        restored = BoundedPersistenceResidualCNN(forcing_variables=variables)
        restored.load_state_dict(model.state_dict())
        output = restored.raw_prediction(torch.rand(1, 17 + variables * 2, 52, 100))
        assert output.shape == (1, 3, 52, 100)
        assert torch.all((output >= 0) & (output <= 1))


def test_missing_forcing_falls_back(service, monkeypatch):
    def unavailable(*args):
        raise ValueError("FORCING_UNAVAILABLE")

    monkeypatch.setattr(op, "_forcing", unavailable)
    result = op.forecast(date(2025, 1, 7))
    assert result["mode"] == "PERSISTENCE"
    assert result["fallback_reason"] == "FORCING_UNAVAILABLE"
    assert result["forcing_source"] is None


def test_stale_latest_falls_back(service):
    result = op.forecast(now=datetime(2025, 2, 1, tzinfo=UTC))
    assert result["fallback_reason"] == "STALE_OBSERVATION"
    assert result["classification"] == "PERSISTENCE_FALLBACK"


def test_current_latest_classification(service):
    result = op.forecast(now=datetime(2025, 1, 13, tzinfo=UTC))
    assert result["classification"] == "LATEST_AVAILABLE_MODEL_PREDICTION"
    assert result["forecasts"][-1]["observed_target"] is None


def test_all_missing_observation_is_unavailable(service, cube):
    cube.ice_conc.values[:] = np.nan
    assert op.forecast()["classification"] == "UNAVAILABLE"


def test_latest_prefers_newer_verified_observation(monkeypatch, cube):
    from backend.app.api import sea_ice

    metadata = {"observation_time": "2025-02-01T00:00:00Z"}
    grid = {"concentration": [[25, None], [50, 75]], "latitude": [-70, -69], "longitude": [76, 77]}
    monkeypatch.setattr(sea_ice, "load_latest_observation", lambda: (metadata, grid))
    latest = op.latest_source(cube)
    assert str(latest.time.values[0].astype("datetime64[D]")) == "2025-02-01"
    assert np.isnan(latest.ice_conc.values[0, 0, 1])


def test_physical_failure_is_not_silently_clipped(service, monkeypatch):
    monkeypatch.setattr(service, "raw_prediction", lambda f: torch.full((1, 3, 52, 100), 2.0))
    assert op.forecast(date(2025, 1, 7))["fallback_reason"] == "MODEL_OUTPUT_OUT_OF_BOUNDS"


def test_forecast_api(service):
    client = TestClient(app)
    for path in ("status", "latest", "results", "historical?date=2025-01-07"):
        response = client.get(f"/api/sea-ice/forecast/{path}")
        assert response.status_code == 200
    payload = client.get("/api/sea-ice/forecast/historical?date=2025-01-07").json()
    assert len(payload["forecasts"][0]["grid"]["concentration"]) == 52
    assert payload["mode"] == "MODEL_PREDICTION"
    for invalid in ("bad", "1999-01-01"):
        assert client.get(f"/api/sea-ice/forecast/historical?date={invalid}").status_code == 422


def test_unavailable_api(monkeypatch):
    def unavailable():
        raise FileNotFoundError("No local cube")

    monkeypatch.setattr(op, "source_cube", unavailable)
    monkeypatch.setattr(op, "latest_source", lambda value: value)
    response = TestClient(app).get("/api/sea-ice/forecast/latest")
    assert response.status_code == 200
    assert response.json()["classification"] == "UNAVAILABLE"
