from datetime import date

import numpy as np
import pytest
import torch

from backend.forecasting.sea_ice.ml import (
    EVALUATION_MODE,
    PREDICTION_CLASSIFICATION,
    TARGET_CLASSIFICATION,
)
from backend.forecasting.sea_ice.ml.dataset import (
    SeaIceWindowDataset,
    temporal_window_indices,
)
from backend.forecasting.sea_ice.ml.evaluation import common_evaluation_mask
from backend.forecasting.sea_ice.ml.inference import deterministic_inference
from backend.forecasting.sea_ice.ml.network import (
    PersistenceResidualCNN,
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
