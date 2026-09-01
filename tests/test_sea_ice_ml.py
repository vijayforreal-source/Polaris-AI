from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import torch
import xarray as xr

from backend.forecasting.sea_ice.forecast_service import generate_forecast
from backend.forecasting.sea_ice.ml import (
    EVALUATION_MODE,
    PREDICTION_CLASSIFICATION,
    TARGET_CLASSIFICATION,
)
from backend.forecasting.sea_ice.ml.atmospheric import load_daily_forcing
from backend.forecasting.sea_ice.ml.dataset import (
    SeaIceWindowDataset,
    temporal_window_indices,
)
from backend.forecasting.sea_ice.ml.evaluation import common_evaluation_mask
from backend.forecasting.sea_ice.ml.inference import deterministic_inference
from backend.forecasting.sea_ice.ml.network import (
    BoundedPersistenceResidualCNN,
    PersistenceResidualCNN,
    bounded_persistence_residual,
    parameter_count,
)
from backend.forecasting.sea_ice.ml.training import masked_mae
from backend.forecasting.sea_ice.models import SeaIceSplit


def _generic_dataset() -> SeaIceWindowDataset:
    times = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-13"))
    fields = np.full((len(times), 4, 5), 50.0, dtype="float32")
    fields[:, 0, 0] = np.nan
    ocean = np.ones((4, 5), dtype=bool)
    ocean[0, 0] = False
    split = SeaIceSplit(
        name="GENERIC_TEST", start=date(2020, 1, 1), end=date(2020, 1, 12)
    )
    return SeaIceWindowDataset(fields, times, ocean, split, context_days=7)


def test_temporal_windows_stay_inside_split_without_target_leakage() -> None:
    times = np.arange(np.datetime64("2019-12-28"), np.datetime64("2020-01-16"))
    split = SeaIceSplit(
        name="GENERIC_TEST", start=date(2020, 1, 1), end=date(2020, 1, 15)
    )
    indices = temporal_window_indices(times, split, context_days=7)
    assert str(times[indices[0]] - np.timedelta64(6, "D")) == "2020-01-01"
    assert str(times[indices[-1]] + np.timedelta64(3, "D")) == "2020-01-15"


def test_mask_aware_tensor_shapes_and_nan_fill() -> None:
    sample = _generic_dataset()[0]
    assert sample["features"].shape == (17, 4, 5)
    assert sample["targets"].shape == (3, 4, 5)
    assert sample["target_mask"].shape == (3, 4, 5)
    assert sample["features"][0, 0, 0].item() == 0.0
    assert sample["features"][7, 0, 0].item() == 0.0
    assert not sample["target_mask"][:, 0, 0].any()


def test_residual_skip_connection_reproduces_persistence_with_zero_weights() -> None:
    model = PersistenceResidualCNN(context_days=7, hidden_channels=8)
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    features = _generic_dataset()[0]["features"].unsqueeze(0)
    prediction = model(features)
    latest = features[:, 6:7]
    assert prediction.shape == (1, 3, 4, 5)
    assert torch.allclose(prediction, latest.expand(-1, 3, -1, -1))


def test_physical_clipping_and_compact_parameter_count() -> None:
    model = PersistenceResidualCNN(context_days=7, hidden_channels=8)
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    torch.nn.init.constant_(model.residual_head.bias, 2.0)
    prediction = model(_generic_dataset()[0]["features"].unsqueeze(0))
    assert torch.all(prediction == 1.0)
    assert parameter_count(model) < 1_000_000


def test_masked_mae_excludes_invalid_cells() -> None:
    prediction = torch.tensor([[[[0.0, 1.0]]]])
    target = torch.tensor([[[[1.0, 0.0]]]])
    mask = torch.tensor([[[[True, False]]]])
    assert masked_mae(prediction, target, mask).item() == pytest.approx(1.0)


def test_evaluation_mask_never_treats_missing_target_as_open_water() -> None:
    ocean = np.ones((1, 2), dtype=bool)
    latest_valid = np.ones((1, 1, 2), dtype=bool)
    target_valid = np.asarray([[[True, False]]])
    persistence = np.asarray([[[50.0, 50.0]]])
    mask = common_evaluation_mask(
        ocean, latest_valid, target_valid, persistence
    )
    assert mask.tolist() == [[[True, False]]]


def test_inference_is_deterministic_and_classifies_output_shape() -> None:
    torch.manual_seed(26059)
    model = PersistenceResidualCNN(context_days=7, hidden_channels=8)
    features = _generic_dataset()[0]["features"].unsqueeze(0)
    first = deterministic_inference(model, features)
    second = deterministic_inference(model, features)
    assert torch.equal(first, second)
    assert first.shape[1] == 3
    assert PREDICTION_CLASSIFICATION == "MODEL_PREDICTION"
    assert TARGET_CLASSIFICATION == "OBSERVATION"
    assert EVALUATION_MODE == "HISTORICAL_FORECAST_BENCHMARK"


def test_bounded_residual_is_physical_and_zero_is_persistence() -> None:
    persistence = torch.tensor([0.0, 0.2, 0.8, 1.0])
    raw = torch.tensor([-100.0, -2.0, 2.0, 100.0])
    prediction = bounded_persistence_residual(persistence, raw)
    assert torch.all((prediction >= 0.0) & (prediction <= 1.0))
    assert torch.equal(
        bounded_persistence_residual(persistence, torch.zeros_like(raw)), persistence
    )


def test_v02_network_is_compact_and_naturally_bounded() -> None:
    model = BoundedPersistenceResidualCNN()
    prediction = model(_generic_dataset()[0]["features"].unsqueeze(0))
    assert prediction.shape == (1, 3, 4, 5)
    assert torch.all((prediction >= 0.0) & (prediction <= 1.0))
    assert parameter_count(model) < 50_000


def test_forcing_alignment_rejects_missing_or_future_days(tmp_path: Path) -> None:
    path = tmp_path / "generic_daily_forcing.nc"
    times = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-04"))
    values = np.ones((3, 2, 2), dtype="float32")
    xr.Dataset(
        {name: (("time", "latitude", "longitude"), values) for name in ("u10", "v10", "t2m")},
        coords={"time": times, "latitude": [0.0, 1.0], "longitude": [10.0, 11.0]},
    ).to_netcdf(path)
    loaded = load_daily_forcing(path, times, np.array([0.0, 1.0]), np.array([10.0, 11.0]))
    assert loaded.shape == (3, 3, 2, 2)
    with pytest.raises(ValueError, match="exactly match"):
        load_daily_forcing(
            path,
            times + np.timedelta64(1, "D"),
            np.array([0.0, 1.0]),
            np.array([10.0, 11.0]),
        )


def test_missing_forcing_has_explicit_mask() -> None:
    base = _generic_dataset()
    forcing = np.ones((len(base.times), 3, 4, 5), dtype="float32")
    forcing[:, 0, 0, 0] = np.nan
    dataset = SeaIceWindowDataset(
        base.concentration,
        base.times,
        base.ocean_mask,
        SeaIceSplit(name="GENERIC_TEST", start=date(2020, 1, 1), end=date(2020, 1, 12)),
        forcing=forcing,
        forcing_mean=np.zeros(3, dtype="float32"),
        forcing_std=np.ones(3, dtype="float32"),
    )
    features = dataset[0]["features"]
    assert features.shape[0] == 23
    assert features[17, 0, 0] == 0.0
    assert features[20, 0, 0] == 0.0


def test_forecast_service_falls_back_when_requirements_fail(tmp_path: Path) -> None:
    result = generate_forecast(
        np.full((2, 2), 50.0),
        datetime.now(UTC) - timedelta(days=10),
        model_path=tmp_path / "missing.pt",
        forcing_available=False,
    )
    assert result.source_type == "PERSISTENCE_FALLBACK"
    assert result.provenance["fallback_reason"] == "STALE_OBSERVATION"
    assert np.array_equal(result.forecasts["24h"], result.forecasts["72h"])
