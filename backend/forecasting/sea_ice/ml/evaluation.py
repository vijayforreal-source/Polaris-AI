import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import xarray as xr
from torch.utils.data import DataLoader

from backend.forecasting.sea_ice.metrics import forecast_metrics
from backend.forecasting.sea_ice.models import BHARATI_FORECAST_DOMAIN

from .dataset import SeaIceWindowDataset
from .network import PersistenceResidualCNN

RESULTS_PATH = Path("backend/forecasting/sea_ice/ml/model_results.json")
ERROR_MAP_PATH = Path("artifacts/sea-ice-ai-error-analysis.nc")
EXAMPLES_PATH = Path("artifacts/sea-ice-ai-example-forecasts.nc")
BOOTSTRAP_SEED = 26059
BOOTSTRAP_RESAMPLES = 10_000


def common_evaluation_mask(
    ocean_mask: np.ndarray,
    latest_valid: np.ndarray,
    target_valid: np.ndarray,
    persistence: np.ndarray,
) -> np.ndarray:
    """Intersect scientific validity for paired AI/persistence evaluation."""
    return (
        ocean_mask[None, :, :]
        & latest_valid
        & target_valid
        & np.isfinite(persistence)
    )


def daily_mae(
    prediction: np.ndarray, target: np.ndarray, valid_mask: np.ndarray
) -> np.ndarray:
    errors = np.abs(prediction - target)
    values: list[float] = []
    for sample_errors, sample_mask in zip(errors, valid_mask, strict=True):
        values.append(float(sample_errors[sample_mask].mean()))
    return np.asarray(values)


def paired_bootstrap(
    ai_daily_mae: np.ndarray,
    persistence_daily_mae: np.ndarray,
    *,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float]:
    differences = ai_daily_mae - persistence_daily_mae
    generator = np.random.default_rng(seed)
    bootstrap_means = np.empty(resamples, dtype="float64")
    for start in range(0, resamples, 1000):
        count = min(1000, resamples - start)
        selections = generator.integers(0, len(differences), size=(count, len(differences)))
        bootstrap_means[start : start + count] = differences[selections].mean(axis=1)
    lower, upper = np.quantile(bootstrap_means, [0.025, 0.975])
    return {
        "mean_ai_minus_persistence_mae_pp": float(differences.mean()),
        "ci_95_lower_pp": float(lower),
        "ci_95_upper_pp": float(upper),
        "resamples": resamples,
        "seed": seed,
    }


def _metric_payload(
    prediction: np.ndarray, target: np.ndarray, valid_mask: np.ndarray
) -> dict[str, Any]:
    spatial_mask = np.ones(valid_mask.shape[-2:], dtype=bool)
    masked_prediction = np.where(valid_mask, prediction, np.nan)
    masked_target = np.where(valid_mask, target, np.nan)
    return forecast_metrics(masked_prediction, masked_target, spatial_mask).model_dump(
        mode="json"
    )


def _mean_absolute_error_map(
    prediction: np.ndarray, target: np.ndarray, valid: np.ndarray
) -> np.ndarray:
    errors = np.where(valid, np.abs(prediction - target), 0.0)
    valid_counts = valid.sum(axis=0)
    result = np.full(valid_counts.shape, np.nan, dtype="float64")
    np.divide(errors.sum(axis=0), valid_counts, out=result, where=valid_counts > 0)
    return result.astype("float32")


def evaluate_model(
    model: PersistenceResidualCNN,
    dataset: SeaIceWindowDataset,
    cube: xr.Dataset,
    *,
    batch_size: int = 16,
) -> dict[str, Any]:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    predictions: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    target_validity: list[np.ndarray] = []
    current_valid: list[np.ndarray] = []
    initialization_indices: list[np.ndarray] = []
    clipped_count = 0
    clipping_denominator = 0
    model.eval()
    with torch.no_grad():
        for batch in loader:
            features = batch["features"]
            raw = model.raw_prediction(features)
            prediction = torch.clamp(raw, 0.0, 1.0)
            target_mask = batch["target_mask"]
            clipped_count += int(((raw < 0) | (raw > 1))[target_mask].sum())
            clipping_denominator += int(target_mask.sum())
            predictions.append(prediction.numpy() * 100.0)
            targets.append(batch["targets"].numpy() * 100.0)
            target_validity.append(target_mask.numpy())
            current_valid.append(batch["current_valid"].numpy())
            initialization_indices.append(batch["initialization_index"].numpy())
    ai = np.concatenate(predictions)
    observed = np.concatenate(targets)
    target_valid = np.concatenate(target_validity)
    latest_valid = np.concatenate(current_valid)
    init_indices = np.concatenate(initialization_indices)
    source_fields = np.asarray(cube.ice_conc.values, dtype="float32")
    persistence = source_fields[init_indices]
    ocean = np.asarray(cube.valid_ocean_mask.values, dtype=bool)
    latitude = np.asarray(cube.latitude.values)
    longitude = np.asarray(cube.longitude.values)
    local = (
        ocean
        & (np.abs(latitude[:, None] - BHARATI_FORECAST_DOMAIN.bharati_latitude) <= 1.0)
        & (np.abs(longitude[None, :] - BHARATI_FORECAST_DOMAIN.bharati_longitude) <= 1.0)
    )
    times = cube.time.values.astype("datetime64[D]")
    results: dict[str, Any] = {
        "model_name": "POLARIS Sea-Ice Residual CNN v0.1",
        "mode": "HISTORICAL_FORECAST_BENCHMARK",
        "prediction_classification": "MODEL_PREDICTION",
        "target_classification": "OBSERVATION",
        "test_sample_count": int(len(dataset)),
        "clipping": {
            "clipped_valid_values": clipped_count,
            "evaluated_valid_values": clipping_denominator,
            "fraction": clipped_count / clipping_denominator,
        },
        "horizons": {},
    }
    error_variables: dict[str, tuple[tuple[str, str], np.ndarray]] = {}
    persistence_daily_by_horizon: dict[int, np.ndarray] = {}
    for horizon_index, horizon_days in enumerate((1, 2, 3)):
        target = observed[:, horizon_index]
        prediction = ai[:, horizon_index]
        common_valid = common_evaluation_mask(
            ocean,
            latest_valid,
            target_valid[:, horizon_index],
            persistence,
        )
        local_valid = common_valid & local[None, :, :]
        ai_daily = daily_mae(prediction, target, common_valid)
        persistence_daily = daily_mae(persistence, target, common_valid)
        persistence_daily_by_horizon[horizon_days] = persistence_daily
        target_times = times[init_indices] + np.timedelta64(horizon_days, "D")
        months = target_times.astype("datetime64[M]").astype(int) % 12 + 1
        cold = np.isin(months, np.arange(3, 11))
        warm = ~cold
        horizon_key = f"{horizon_days * 24}H"
        results["horizons"][horizon_key] = {
            "sample_count": int(len(ai_daily)),
            "ai": _metric_payload(prediction, target, common_valid),
            "persistence": _metric_payload(persistence, target, common_valid),
            "skill_vs_persistence_mae": float(
                1.0 - ai_daily.mean() / persistence_daily.mean()
            ),
            "fraction_days_ai_beats_persistence": float(
                np.mean(ai_daily < persistence_daily)
            ),
            "mean_paired_improvement_pp": float(
                np.mean(persistence_daily - ai_daily)
            ),
            "bootstrap": paired_bootstrap(ai_daily, persistence_daily),
            "seasonal": {
                "AUSTRAL_COLD_GROWTH_MAR_OCT": {
                    "ai_mae_pp": float(ai_daily[cold].mean()),
                    "persistence_mae_pp": float(persistence_daily[cold].mean()),
                    "sample_count": int(cold.sum()),
                },
                "AUSTRAL_WARM_MELT_NOV_FEB": {
                    "ai_mae_pp": float(ai_daily[warm].mean()),
                    "persistence_mae_pp": float(persistence_daily[warm].mean()),
                    "sample_count": int(warm.sum()),
                },
            },
            "bharati_local": {
                "ai": _metric_payload(prediction, target, local_valid),
                "persistence": _metric_payload(persistence, target, local_valid),
            },
        }
        local_ai_mae = results["horizons"][horizon_key]["bharati_local"]["ai"][
            "mae_percentage_points"
        ]
        local_persistence_mae = results["horizons"][horizon_key]["bharati_local"][
            "persistence"
        ]["mae_percentage_points"]
        results["horizons"][horizon_key]["bharati_local"][
            "skill_vs_persistence_mae"
        ] = 1.0 - local_ai_mae / local_persistence_mae
        if horizon_days in {1, 3}:
            ai_map = _mean_absolute_error_map(prediction, target, common_valid)
            persistence_map = _mean_absolute_error_map(
                persistence, target, common_valid
            )
            error_variables[f"ai_{horizon_key.lower()}_mae"] = (
                ("latitude", "longitude"),
                ai_map,
            )
            error_variables[f"persistence_{horizon_key.lower()}_mae"] = (
                ("latitude", "longitude"),
                persistence_map,
            )
            error_variables[f"ai_minus_persistence_{horizon_key.lower()}_mae"] = (
                ("latitude", "longitude"),
                ai_map - persistence_map,
            )
    ERROR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    xr.Dataset(
        error_variables,
        coords={"latitude": latitude, "longitude": longitude},
        attrs={"units": "sea-ice concentration percentage points"},
    ).to_netcdf(ERROR_MAP_PATH)
    _write_examples(
        ai,
        observed,
        persistence,
        init_indices,
        times,
        latitude,
        longitude,
        persistence_daily_by_horizon[3],
    )
    return results


def _write_examples(
    ai: np.ndarray,
    observed: np.ndarray,
    persistence: np.ndarray,
    init_indices: np.ndarray,
    times: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
    persistence_daily_72h: np.ndarray,
) -> None:
    selected = np.asarray(
        [0, len(init_indices) // 2, int(np.argmax(persistence_daily_72h))]
    )
    target = observed[selected, 2]
    ai_forecast = ai[selected, 2]
    persistence_forecast = persistence[selected]
    initialization = persistence_forecast.copy()
    labels = np.asarray(["first", "middle", "largest_persistence_error"])
    dates = [str(times[init_indices[index]]) for index in selected]
    xr.Dataset(
        {
            "initial_observation": (("example", "latitude", "longitude"), initialization),
            "ai_forecast_72h": (("example", "latitude", "longitude"), ai_forecast),
            "persistence_forecast_72h": (
                ("example", "latitude", "longitude"),
                persistence_forecast,
            ),
            "actual_observation_72h": (("example", "latitude", "longitude"), target),
            "ai_absolute_error_72h": (
                ("example", "latitude", "longitude"),
                np.abs(ai_forecast - target),
            ),
            "persistence_absolute_error_72h": (
                ("example", "latitude", "longitude"),
                np.abs(persistence_forecast - target),
            ),
        },
        coords={"example": labels, "latitude": latitude, "longitude": longitude},
        attrs={
            "selection": "first, middle, and largest persistence-error dates",
            "dates": json.dumps(dates),
        },
    ).to_netcdf(EXAMPLES_PATH)


def write_model_results(results: dict[str, Any], path: Path = RESULTS_PATH) -> None:
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
