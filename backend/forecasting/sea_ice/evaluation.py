import json
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from .baselines import (
    build_train_climatology,
    climatology_anomaly_persistence,
    climatology_forecast,
    linear_tendency,
    persistence,
)
from .metrics import forecast_metrics, mean_error_map
from .models import (
    BHARATI_FORECAST_DOMAIN,
    TEST_SPLIT,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    BaselineName,
)
from .preprocessing import chronological_indices, forecast_pairs

RESULTS_PATH = Path("backend/forecasting/sea_ice/baseline_results.json")
ERROR_MAP_PATH = Path("artifacts/sea-ice-baseline-error-maps.nc")


def _predict(
    baseline: BaselineName,
    fields: np.ndarray,
    times: np.ndarray,
    pairs: list[tuple[int, int]],
    horizon_days: int,
    climatology: dict[str, np.ndarray],
) -> np.ndarray:
    predictions: list[np.ndarray] = []
    for initialization_index, target_index in pairs:
        current = fields[initialization_index]
        if baseline == BaselineName.PERSISTENCE:
            prediction = persistence(current)
        elif baseline == BaselineName.SEASONAL_CLIMATOLOGY:
            prediction = climatology_forecast(climatology, times[target_index])
        elif baseline == BaselineName.LINEAR_TENDENCY:
            prediction = linear_tendency(
                current, fields[initialization_index - 1], horizon_days
            )
        else:
            prediction = climatology_anomaly_persistence(
                current,
                times[initialization_index],
                times[target_index],
                climatology,
            )
        predictions.append(prediction.astype("float32"))
    return np.stack(predictions)


def _metrics_payload(
    prediction: np.ndarray, target: np.ndarray, mask: np.ndarray
) -> dict[str, Any]:
    return forecast_metrics(prediction, target, mask).model_dump(mode="json")


def _seasonal_metrics(
    prediction: np.ndarray,
    target: np.ndarray,
    target_times: np.ndarray,
    mask: np.ndarray,
) -> dict[str, Any]:
    months = target_times.astype("datetime64[M]").astype(int) % 12 + 1
    cold = np.isin(months, np.arange(3, 11))
    warm = ~cold
    return {
        "AUSTRAL_COLD_GROWTH_MAR_OCT": _metrics_payload(
            prediction[cold], target[cold], mask
        ),
        "AUSTRAL_WARM_MELT_NOV_FEB": _metrics_payload(
            prediction[warm], target[warm], mask
        ),
    }


def evaluate_baselines(cube: xr.Dataset) -> dict[str, Any]:
    fields = np.asarray(cube.ice_conc.values, dtype="float32")
    times = cube.time.values.astype("datetime64[D]")
    ocean_mask = np.asarray(cube.valid_ocean_mask.values, dtype=bool)
    latitude = np.asarray(cube.latitude.values)
    longitude = np.asarray(cube.longitude.values)
    local_mask = (
        ocean_mask
        & (np.abs(latitude[:, None] - BHARATI_FORECAST_DOMAIN.bharati_latitude) <= 1.0)
        & (np.abs(longitude[None, :] - BHARATI_FORECAST_DOMAIN.bharati_longitude) <= 1.0)
    )
    train_indices = chronological_indices(times, TRAIN_SPLIT)
    climatology = build_train_climatology(fields, times, train_indices)
    baselines = list(BaselineName)
    results: dict[str, Any] = {
        "mode": "HISTORICAL_BASELINE_EVALUATION",
        "target_classification": "OBSERVATION",
        "forecast_classification": "MODEL_PREDICTION",
        "units": "percentage points",
        "ice_threshold_percent": 15.0,
        "seasons": {
            "cold_growth": "March through October",
            "warm_melt": "November through February",
        },
        "bharati_neighborhood": {
            "definition": (
                "within 1 degree latitude/longitude of Bharati; "
                "provider-valid ocean cells only"
            ),
            "valid_ocean_cells": int(local_mask.sum()),
        },
        "splits": {
            split.name: {"start": split.start.isoformat(), "end": split.end.isoformat()}
            for split in (TRAIN_SPLIT, VALIDATION_SPLIT, TEST_SPLIT)
        },
        "sample_counts": {},
        "horizons": {},
    }
    error_maps: dict[str, tuple[tuple[str, str], np.ndarray]] = {}
    aggregate_mae: dict[str, list[float]] = {baseline.value: [] for baseline in baselines}
    for horizon_days in (1, 2, 3):
        horizon_key = f"{horizon_days * 24}H"
        results["sample_counts"][horizon_key] = {
            split.name: len(forecast_pairs(times, split, horizon_days))
            for split in (TRAIN_SPLIT, VALIDATION_SPLIT, TEST_SPLIT)
        }
        pairs = forecast_pairs(times, TEST_SPLIT, horizon_days)
        target_indices = np.asarray([target for _, target in pairs])
        targets = fields[target_indices]
        target_times = times[target_indices]
        horizon_results: dict[str, Any] = {}
        prediction_cache: dict[str, np.ndarray] = {}
        for baseline in baselines:
            predictions = _predict(
                baseline, fields, times, pairs, horizon_days, climatology
            )
            prediction_cache[baseline.value] = predictions
            regional = _metrics_payload(predictions, targets, ocean_mask)
            aggregate_mae[baseline.value].append(regional["mae_percentage_points"])
            horizon_results[baseline.value] = {
                "regional": regional,
                "bharati_local": _metrics_payload(predictions, targets, local_mask),
                "seasonal": _seasonal_metrics(
                    predictions, targets, target_times, ocean_mask
                ),
            }
        best = min(
            baselines,
            key=lambda baseline: horizon_results[baseline.value]["regional"][
                "mae_percentage_points"
            ],
        )
        horizon_results["best_baseline"] = best.value
        results["horizons"][horizon_key] = horizon_results
        if horizon_days in {1, 3}:
            error_maps[f"persistence_{horizon_key.lower()}_mean_error"] = (
                ("latitude", "longitude"),
                mean_error_map(
                    prediction_cache[BaselineName.PERSISTENCE.value], targets
                ).astype("float32"),
            )
        error_maps[f"best_{horizon_key.lower()}_mean_error"] = (
            ("latitude", "longitude"),
            mean_error_map(prediction_cache[best.value], targets).astype("float32"),
        )
    results["best_overall_baseline"] = min(
        baselines, key=lambda baseline: np.mean(aggregate_mae[baseline.value])
    ).value
    results["mean_mae_across_horizons"] = {
        key: float(np.mean(values)) for key, values in aggregate_mae.items()
    }
    ERROR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    xr.Dataset(
        data_vars=error_maps,
        coords={"latitude": latitude, "longitude": longitude},
        attrs={
            "units": "sea-ice concentration percentage points",
            "classification": "DERIVED_BASELINE_ERROR",
        },
    ).to_netcdf(ERROR_MAP_PATH)
    return results


def write_results(results: dict[str, Any], path: Path = RESULTS_PATH) -> None:
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
