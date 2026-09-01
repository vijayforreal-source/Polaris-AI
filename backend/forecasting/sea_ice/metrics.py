import warnings

import numpy as np

from .models import ForecastMetrics

ICE_THRESHOLD_PERCENT = 15.0


def forecast_metrics(
    prediction: np.ndarray,
    target: np.ndarray,
    ocean_mask: np.ndarray,
) -> ForecastMetrics:
    prediction_values = np.asarray(prediction, dtype=float)
    target_values = np.asarray(target, dtype=float)
    mask = np.broadcast_to(np.asarray(ocean_mask, dtype=bool), target_values.shape)
    valid = mask & np.isfinite(prediction_values) & np.isfinite(target_values)
    if not np.any(valid):
        raise ValueError("No valid ocean pixels available for evaluation")
    errors = prediction_values[valid] - target_values[valid]
    predicted_ice = prediction_values[valid] >= ICE_THRESHOLD_PERCENT
    observed_ice = target_values[valid] >= ICE_THRESHOLD_PERCENT
    true_positive = int(np.sum(predicted_ice & observed_ice))
    false_positive = int(np.sum(predicted_ice & ~observed_ice))
    false_negative = int(np.sum(~predicted_ice & observed_ice))
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else None
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else None
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return ForecastMetrics(
        valid_pixel_count=int(valid.sum()),
        mae_percentage_points=float(np.mean(np.abs(errors))),
        rmse_percentage_points=float(np.sqrt(np.mean(errors**2))),
        mean_bias_percentage_points=float(np.mean(errors)),
        precision_15_percent=precision,
        recall_15_percent=recall,
        f1_15_percent=f1,
    )


def mean_error_map(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    errors = np.asarray(prediction, dtype=float) - np.asarray(target, dtype=float)
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.filterwarnings("ignore", message="Mean of empty slice")
        return np.nanmean(errors, axis=0)
