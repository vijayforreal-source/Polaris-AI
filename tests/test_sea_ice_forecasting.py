from datetime import date
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from backend.forecasting.sea_ice.baselines import (
    build_train_climatology,
    climatology_forecast,
    linear_tendency,
    persistence,
)
from backend.forecasting.sea_ice.dataset import (
    CDR_DATASET_ID,
    ICDR_DATASET_ID,
    inspect_source_consistency,
    load_daily_cube,
)
from backend.forecasting.sea_ice.metrics import forecast_metrics
from backend.forecasting.sea_ice.models import SeaIceSplit
from backend.forecasting.sea_ice.preprocessing import (
    chronological_indices,
    forecast_pairs,
)
from backend.ingestion.historical_sea_ice import build_historical_subset_arguments


def _generic_provider_file(path: Path, time: str, value: float) -> Path:
    path.parent.mkdir(parents=True)
    concentration = np.array([[[np.nan, value], [20.0, 40.0]]], dtype="float32")
    uncertainty = np.where(np.isfinite(concentration), 2.0, np.nan).astype("float32")
    status = np.array([[[1, 0], [0, 0]]], dtype="uint16")
    dataset = xr.Dataset(
        {
            "ice_conc": (
                ("time", "latitude", "longitude"),
                concentration,
                {"units": "%", "regrid_method": "bilinear"},
            ),
            "total_standard_uncertainty": (
                ("time", "latitude", "longitude"),
                uncertainty,
                {"units": "%", "regrid_method": "bilinear"},
            ),
            "status_flag": (
                ("time", "latitude", "longitude"),
                status,
                {
                    "flag_masks": np.arange(1, 9),
                    "flag_meanings": "generic structural fixture",
                    "regrid_method": "nearest_s2d",
                },
            ),
        },
        coords={
            "time": np.array([time], dtype="datetime64[D]"),
            "latitude": [-2.0, -1.0],
            "longitude": [10.0, 11.0],
        },
    )
    dataset.to_netcdf(path)
    return path


def test_cdr_icdr_normalization_preserves_missing_and_land(tmp_path: Path) -> None:
    cdr = _generic_provider_file(tmp_path / "cdr" / "a.nc", "2020-12-31", 10.0)
    icdr = _generic_provider_file(tmp_path / "icdr" / "b.nc", "2021-01-01", 15.0)
    consistency = inspect_source_consistency([cdr, icdr])
    cube = load_daily_cube([cdr, icdr])
    assert consistency["compatible"] is True
    assert cube.sizes["time"] == 2
    assert np.isnan(cube.ice_conc.values[:, 0, 0]).all()
    assert not bool(cube.valid_ocean_mask.values[0, 0])
    assert bool(cube.valid_ocean_mask.values[0, 1])


def test_historical_request_contains_only_verified_fields() -> None:
    arguments = build_historical_subset_arguments(
        CDR_DATASET_ID, "2015-01-01", "2015-12-31"
    )
    assert CDR_DATASET_ID in arguments
    requested_variables = {
        arguments[index + 1]
        for index, value in enumerate(arguments)
        if value == "--variable"
    }
    assert requested_variables == {
        "ice_conc",
        "total_standard_uncertainty",
        "status_flag",
    }
    with pytest.raises(ValueError):
        build_historical_subset_arguments("unverified", "2015-01-01", "2015-12-31")
    assert ICDR_DATASET_ID != CDR_DATASET_ID


def test_chronological_split_and_targets_do_not_cross_boundary() -> None:
    times = np.arange(np.datetime64("2024-12-29"), np.datetime64("2025-01-06"))
    split = SeaIceSplit(name="GENERIC_TEST", start=date(2025, 1, 1), end=date(2025, 1, 5))
    indices = chronological_indices(times, split)
    pairs = forecast_pairs(times, split, 3)
    assert [str(times[index]) for index in indices] == [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
    ]
    assert [(str(times[start]), str(times[target])) for start, target in pairs] == [
        ("2025-01-01", "2025-01-04"),
        ("2025-01-02", "2025-01-05"),
    ]


def test_persistence_and_linear_tendency_with_physical_clipping() -> None:
    current = np.array([[10.0, 95.0, np.nan]])
    previous = np.array([[20.0, 80.0, np.nan]])
    assert np.allclose(persistence(current), current, equal_nan=True)
    prediction = linear_tendency(current, previous, 2)
    assert np.allclose(prediction, [[0.0, 100.0, np.nan]], equal_nan=True)


def test_climatology_uses_train_indices_only_and_supports_leap_day() -> None:
    times = np.array(
        ["2016-02-29", "2020-02-29", "2024-02-29"], dtype="datetime64[D]"
    )
    fields = np.array([[[20.0]], [[40.0]], [[100.0]]])
    climatology = build_train_climatology(fields, times, np.array([0, 1]))
    assert climatology_forecast(climatology, times[2]).item() == pytest.approx(30.0)


def test_metrics_ignore_missing_and_land_without_converting_to_zero() -> None:
    prediction = np.array([[[10.0, 30.0], [np.nan, 80.0]]])
    target = np.array([[[20.0, 10.0], [50.0, 100.0]]])
    ocean = np.array([[True, False], [True, True]])
    metrics = forecast_metrics(prediction, target, ocean)
    assert metrics.valid_pixel_count == 2
    assert metrics.mae_percentage_points == pytest.approx(15.0)
    assert metrics.rmse_percentage_points == pytest.approx(np.sqrt(250.0))
    assert metrics.mean_bias_percentage_points == pytest.approx(-15.0)
