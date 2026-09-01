import warnings
from collections import defaultdict

import numpy as np


def persistence(current: np.ndarray) -> np.ndarray:
    return np.asarray(current, dtype=float).copy()


def linear_tendency(current: np.ndarray, previous: np.ndarray, horizon_days: int) -> np.ndarray:
    prediction = np.asarray(current, dtype=float) + horizon_days * (
        np.asarray(current, dtype=float) - np.asarray(previous, dtype=float)
    )
    return np.clip(prediction, 0.0, 100.0)


def month_day_key(value: np.datetime64) -> str:
    return str(value.astype("datetime64[D]"))[5:]


def build_train_climatology(
    fields: np.ndarray, times: np.ndarray, train_indices: np.ndarray
) -> dict[str, np.ndarray]:
    grouped: dict[str, list[np.ndarray]] = defaultdict(list)
    for index in train_indices:
        grouped[month_day_key(times[index])].append(fields[index])
    climatology: dict[str, np.ndarray] = {}
    for key, values in grouped.items():
        with warnings.catch_warnings(), np.errstate(invalid="ignore"):
            warnings.filterwarnings("ignore", message="Mean of empty slice")
            climatology[key] = np.nanmean(np.stack(values), axis=0)
    return climatology


def climatology_forecast(
    climatology: dict[str, np.ndarray], target_time: np.datetime64
) -> np.ndarray:
    key = month_day_key(target_time)
    if key not in climatology:
        raise KeyError(f"No training climatology for calendar day {key}")
    return climatology[key].copy()


def climatology_anomaly_persistence(
    current: np.ndarray,
    current_time: np.datetime64,
    target_time: np.datetime64,
    climatology: dict[str, np.ndarray],
) -> np.ndarray:
    current_climatology = climatology_forecast(climatology, current_time)
    target_climatology = climatology_forecast(climatology, target_time)
    return np.clip(target_climatology + (current - current_climatology), 0.0, 100.0)
