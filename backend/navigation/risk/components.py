from datetime import timedelta

import numpy as np
from pyproj import Geod

from .config import RiskConfig
from .models import RiskInputs
from .vessel import VesselProfile

GEOD = Geod(ellps="WGS84")


def interpolate_sic(sic: dict[int, np.ndarray], horizon: float, shape: tuple) -> tuple:
    if not np.isfinite(horizon) or horizon < 0:
        raise ValueError("Horizon must be finite and non-negative")
    if horizon > 72:
        return np.full(shape, np.nan), {
            "status": "FORECAST_HORIZON_EXCEEDED",
            "lower_horizon": None,
            "upper_horizon": None,
            "interpolation_fraction": None,
        }
    lower = int(horizon // 24) * 24
    upper = lower if horizon == lower else lower + 24
    fraction = (horizon - lower) / 24 if upper != lower else 0
    a, b = sic.get(lower), sic.get(upper)
    if a is None or b is None or a.shape != shape or b.shape != shape:
        return np.full(shape, np.nan), {
            "status": "MISSING_FORECAST_HORIZON",
            "lower_horizon": lower,
            "upper_horizon": upper,
            "interpolation_fraction": fraction,
        }
    valid = np.isfinite(a) & np.isfinite(b) & (a >= 0) & (a <= 100) & (b >= 0) & (b <= 100)
    values = a if upper == lower else a * (1 - fraction) + b * fraction
    return np.where(valid, values, np.nan), {
        "status": "AVAILABLE",
        "lower_horizon": lower,
        "upper_horizon": upper,
        "interpolation_fraction": fraction,
    }


def sea_ice_hazards(sic: np.ndarray, vessel: VesselProfile, config: RiskConfig) -> tuple:
    recommended = vessel.maximum_recommended_sic_percent
    maximum = vessel.maximum_operational_sic_percent
    capability_unknown = (
        recommended is None or maximum is None or vessel.minimum_clearance_km is None
    )
    adjusted = (
        sic * config.reference_recommended_sic / (recommended or config.reference_recommended_sic)
    )
    ice = np.interp(np.nan_to_num(adjusted, nan=100), config.sic_breakpoints, config.sic_hazards)
    if recommended is None or maximum is None:
        constraint = np.ones(sic.shape)
        violation = np.ones(sic.shape, dtype=bool)
    else:
        constraint = np.clip(
            (np.nan_to_num(sic, nan=100) - recommended) / (maximum - recommended), 0, 1
        )
        violation = sic >= maximum
    return ice, constraint, violation, capability_unknown


def iceberg_hazards(
    inputs: RiskInputs, horizon: float, vessel: VesselProfile, config: RiskConfig
) -> tuple:
    lon, lat = np.meshgrid(inputs.longitude, inputs.latitude)
    hazard = np.zeros(lat.shape)
    hard = np.zeros(lat.shape, dtype=bool)
    uncertainty = np.zeros(lat.shape)
    details = []
    unavailable = inputs.iceberg_state == "UNAVAILABLE"
    stale = inputs.iceberg_state in {"STALE", "DEGRADED"}
    valid_time = inputs.initialization_time + timedelta(hours=horizon)
    for berg in inputs.icebergs:
        age = (inputs.as_of - berg.observed_at).total_seconds() / 86400 + berg.date_precision_days
        if age < 0:
            unavailable = True
            continue
        unavailable |= age > config.iceberg_unavailable_days
        stale |= age > config.iceberg_stale_days
        predicted = (
            berg.prediction_valid_time == valid_time
            and berg.predicted_latitude is not None
            and berg.predicted_longitude is not None
        )
        center_lat = berg.predicted_latitude if predicted else berg.latitude
        center_lon = berg.predicted_longitude if predicted else berg.longitude
        _, _, meters = GEOD.inv(
            np.full(lat.shape, center_lon), np.full(lat.shape, center_lat), lon, lat
        )
        center_distance = np.asarray(meters) / 1000
        growth = age * config.iceberg_age_growth_km_per_day
        if not predicted:
            growth += horizon * config.iceberg_horizon_growth_km_per_hour
        radius = berg.uncertainty_radius_km + growth
        size = (
            berg.size_radius_km
            if berg.size_radius_km is not None
            else config.unknown_iceberg_size_km
        )
        effective = np.maximum(0, center_distance - radius - size)
        exclusion = config.iceberg_exclusion_km + (vessel.minimum_clearance_km or 0)
        caution = exclusion + config.iceberg_caution_km
        local = np.where(
            effective <= exclusion,
            1,
            np.where(
                effective < caution,
                1 - 0.5 * (effective - exclusion) / config.iceberg_caution_km,
                0.5 * np.exp(-(effective - caution) / config.iceberg_caution_km),
            ),
        )
        hazard = np.maximum(hazard, local)
        hard |= effective <= exclusion
        uncertainty = np.maximum(
            uncertainty, np.clip(radius / config.iceberg_uncertainty_scale_km, 0, 1) * local
        )
        details.append(
            {
                "iceberg_id": berg.iceberg_id,
                "age_days": age,
                "effective_uncertainty_radius_km": radius,
                "size_radius_km": size,
                "center_classification": "MODEL_PREDICTION" if predicted else "OBSERVATION",
                "source": berg.source,
            }
        )
    if unavailable:
        hazard[:] = 1
        uncertainty[:] = 1
    return hazard, hard, uncertainty, unavailable, stale, details


def historical_confidence(inputs: RiskInputs, config: RiskConfig) -> np.ndarray:
    lon, lat = np.meshgrid(inputs.longitude, inputs.latitude)
    confidence = np.zeros(lat.shape)
    if inputs.historical_state != "AVAILABLE":
        return confidence
    for cell in inputs.historical_cells:
        west, south, east, north = cell["bbox"]
        mask = (lon >= west) & (lon < east) & (lat >= south) & (lat < north)
        score = cell["recency_score"] * (
            1 - np.exp(-cell["unique_voyages"] / config.historical_frequency_scale)
        )
        confidence[mask] = np.maximum(confidence[mask], np.clip(score, 0, 1))
    return confidence


def horizon_uncertainty(horizon: float, inputs: RiskInputs, config: RiskConfig) -> float:
    if horizon > 72:
        return 1.0
    values = [config.observation_uncertainty] + [
        config.observation_uncertainty + v / config.mae_uncertainty_scale_pp for v in inputs.mae_pp
    ]
    return float(np.clip(np.interp(horizon, [0, 24, 48, 72], values), 0, 1))
