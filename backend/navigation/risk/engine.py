from datetime import timedelta

import numpy as np

from .components import (
    historical_confidence,
    horizon_uncertainty,
    iceberg_hazards,
    interpolate_sic,
    sea_ice_hazards,
)
from .config import CATEGORY_LABELS, CONFIG, DOMINANT_LABELS, HARD_REASONS, RiskConfig
from .models import RiskField, RiskInputs
from .vessel import VesselProfile


def risk_categories(values: np.ndarray, config: RiskConfig = CONFIG) -> np.ndarray:
    return np.searchsorted(config.category_edges, values, side="right").astype("uint8")


def compute_risk(
    inputs: RiskInputs, horizon_hours: float, vessel: VesselProfile, config: RiskConfig = CONFIG
) -> RiskField:
    if not np.isfinite(horizon_hours) or not 0 <= horizon_hours <= 720:
        raise ValueError("Horizon must be finite and within 0..720 hours; forecasts end at 72H")
    if inputs.initialization_time.tzinfo is None or inputs.as_of.tzinfo is None:
        raise ValueError("Risk timestamps require explicit timezones")
    shape = (len(inputs.latitude), len(inputs.longitude))
    if inputs.ocean_mask.shape != shape:
        raise ValueError("Ocean mask must exactly match grid axes")
    sic, interpolation = interpolate_sic(inputs.sic, horizon_hours, shape)
    ice, vessel_hazard, vessel_block, capability_unknown = sea_ice_hazards(sic, vessel, config)
    berg, berg_block, berg_uncertainty, berg_unavailable, berg_stale, berg_details = (
        iceberg_hazards(inputs, horizon_hours, vessel, config)
    )
    lon, lat = np.meshgrid(inputs.longitude, inputs.latitude)
    valid_geo = np.isfinite(lon) & np.isfinite(lat) & (abs(lon) <= 180) & (abs(lat) <= 90)
    valid_ocean = np.isfinite(inputs.ocean_mask) & (inputs.ocean_mask > 0)
    invalid_sic = ~np.isfinite(sic)
    stale_sic = (
        inputs.sea_ice_age_days > config.maximum_sic_age_days or inputs.sea_ice_state == "STALE"
    )
    environment_unavailable = (
        inputs.sea_ice_state == "UNAVAILABLE"
        or inputs.sea_ice_age_days < 0
        or inputs.initialization_time > inputs.as_of
    )
    uncertainty = np.full(shape, horizon_uncertainty(horizon_hours, inputs, config))
    uncertainty += config.sic_age_penalty_max * np.clip(
        inputs.sea_ice_age_days / config.maximum_sic_age_days, 0, 1
    )
    uncertainty += config.iceberg_age_penalty_max * np.clip(
        inputs.iceberg_report_age_days / config.iceberg_unavailable_days, 0, 1
    )
    uncertainty += berg_uncertainty
    if horizon_hours > 0 and inputs.forecast_mode != "MODEL_PREDICTION":
        uncertainty += config.persistence_penalty
    if capability_unknown:
        uncertainty += config.unknown_vessel_penalty
    if any(
        value is None
        for value in (
            vessel.length_m,
            vessel.beam_m,
            vessel.draft_m,
            vessel.nominal_speed_knots,
            vessel.ice_class,
        )
    ):
        uncertainty += config.incomplete_vessel_penalty
    if inputs.iceberg_coverage_incomplete:
        uncertainty += config.iceberg_coverage_penalty
    if berg_unavailable or environment_unavailable or horizon_hours > 72:
        uncertainty[:] = 1
    uncertainty[invalid_sic | ~valid_geo | ~valid_ocean] = 1
    uncertainty = np.clip(np.nan_to_num(uncertainty, nan=1, posinf=1, neginf=1), 0, 1)
    components = {
        "sea_ice_hazard": ice,
        "iceberg_hazard": berg,
        "uncertainty_hazard": uncertainty,
        "vessel_constraint_hazard": vessel_hazard,
    }
    for key, value in components.items():
        components[key] = np.clip(np.nan_to_num(value, nan=1, posinf=1, neginf=1), 0, 1)
    weighted = np.stack([v * w for v, w in zip(components.values(), config.weights, strict=True)])
    risk = np.clip(weighted.sum(axis=0), 0, 1)
    dominant = weighted.argmax(axis=0).astype("uint8")
    hard = np.zeros(shape, dtype="uint16")
    hard[~valid_ocean] |= 1
    hard[~valid_geo] |= 2
    hard[invalid_sic] |= 4
    if stale_sic:
        hard |= 8
    if berg_unavailable:
        hard |= 16
    hard[berg_block] |= 32
    hard[vessel_block] |= 64
    if capability_unknown:
        hard |= 128
    if horizon_hours > 72:
        hard |= 256
    if environment_unavailable:
        hard |= 512
    navigable = hard == 0
    risk[~navigable] = 1
    dominant[vessel_block | capability_unknown] = 3
    dominant[berg_block] = 1
    dominant[(hard & (4 | 8 | 16 | 256 | 512)) != 0] = 5
    dominant[~valid_ocean] = 4
    dominant[~valid_geo] = 5
    history = historical_confidence(inputs, config)
    bonus = np.where(
        navigable & (risk < config.experience_risk_ceiling),
        config.experience_bonus_max * history,
        0,
    )
    cost = np.where(
        navigable,
        np.maximum(0, risk + config.uncertainty_cost_weight * uncertainty - bonus),
        np.nan,
    )
    components.update(historical_transit_confidence=history, experience_bonus=bonus)
    component_states = {
        "sea_ice": "UNAVAILABLE"
        if environment_unavailable
        else "STALE"
        if stale_sic
        else "DEGRADED"
        if interpolation["status"] != "AVAILABLE"
        or (horizon_hours > 0 and inputs.forecast_mode != "MODEL_PREDICTION")
        else inputs.sea_ice_state,
        "icebergs": "UNAVAILABLE"
        if berg_unavailable
        else "STALE"
        if berg_stale
        else "DEGRADED"
        if horizon_hours > 0 or inputs.iceberg_coverage_incomplete
        else "AVAILABLE",
        "historical_transit": inputs.historical_state,
        "vessel": "DEGRADED" if capability_unknown else "AVAILABLE",
    }
    overall = (
        "UNAVAILABLE"
        if environment_unavailable or horizon_hours > 72
        else (
            "DEGRADED"
            if stale_sic
            or berg_unavailable
            or berg_stale
            or capability_unknown
            or any(v == "DEGRADED" for v in component_states.values())
            else "AVAILABLE"
        )
    )
    return RiskField(
        inputs.latitude,
        inputs.longitude,
        risk,
        cost,
        navigable,
        risk_categories(risk, config),
        dominant,
        hard,
        components,
        sic,
        {
            "classification": "ENGINEERING_RISK_ASSESSMENT",
            "state": overall,
            "initialization_time": inputs.initialization_time.isoformat(),
            "as_of": inputs.as_of.isoformat(),
            "valid_time": (inputs.initialization_time + timedelta(hours=horizon_hours)).isoformat(),
            "horizon_hours": horizon_hours,
            "interpolation": interpolation,
            "vessel": vessel.model_dump(mode="json"),
            "component_states": component_states,
            "sea_ice_age_days": inputs.sea_ice_age_days,
            "iceberg_report_age_days": inputs.iceberg_report_age_days,
            "forecast_mode": inputs.forecast_mode,
            "icebergs": berg_details,
            "configuration": config.model_dump(),
            "category_labels": CATEGORY_LABELS,
            "dominant_factor_labels": DOMINANT_LABELS,
            "hard_constraint_bits": HARD_REASONS,
            "provenance": inputs.provenance,
            "limitations": [
                "Risk score is decision-support output, not certified navigational safety "
                "probability.",
                "Historical transit confidence is not a safety probability and never lowers "
                "safety risk.",
                "No bathymetry/depth clearance or route optimization is implemented.",
                "USNIC covers qualifying named/large icebergs, not all hazards.",
                "Unpropagated iceberg observations use expanding engineering envelopes, not "
                "invented trajectories.",
            ],
        },
    )


def field_summary(field: RiskField) -> dict:
    return {
        "risk_min": float(field.risk_grid.min()),
        "risk_max": float(field.risk_grid.max()),
        "risk_mean": float(field.risk_grid.mean()),
        "blocked_cell_count": int((~field.navigable_mask).sum()),
        "cell_count": int(field.risk_grid.size),
        "category_counts": {
            name: int((field.risk_category_grid == i).sum())
            for i, name in enumerate(CATEGORY_LABELS)
        },
        "dominant_factor_counts": {
            name: int((field.dominant_factor_grid == i).sum())
            for i, name in enumerate(DOMINANT_LABELS)
        },
        "mean_components": {
            key: float(value.mean()) for key, value in field.component_grids.items()
        },
    }


def serialize_field(field: RiskField) -> dict:
    cost = np.where(
        np.isfinite(field.navigation_cost_grid), field.navigation_cost_grid, None
    ).tolist()
    return {
        "latitude": field.latitude.tolist(),
        "longitude": field.longitude.tolist(),
        "grid_shape": list(field.risk_grid.shape),
        "risk_grid": field.risk_grid.round(6).tolist(),
        "navigation_cost_grid": cost,
        "navigable_mask": field.navigable_mask.tolist(),
        "risk_category_grid": field.risk_category_grid.tolist(),
        "dominant_factor_grid": field.dominant_factor_grid.tolist(),
        "hard_constraint_grid": field.hard_constraint_grid.tolist(),
        "component_grids": {
            key: value.round(6).tolist() for key, value in field.component_grids.items()
        },
        "metadata": field.metadata,
        "summary": field_summary(field),
        "encoding": "Category/dominant grids use zero-based metadata label indices; null "
        "cost means blocked.",
    }


def explain_point(field: RiskField, latitude: float, longitude: float) -> dict:
    if (
        not np.isfinite(latitude)
        or not np.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("INVALID_COORDINATES")
    if (
        not field.latitude.min() <= latitude <= field.latitude.max()
        or not field.longitude.min() <= longitude <= field.longitude.max()
    ):
        raise ValueError("POINT_OUTSIDE_RISK_GRID")
    y = int(np.argmin(abs(field.latitude - latitude)))
    x = int(np.argmin(abs(field.longitude - longitude)))
    hard = int(field.hard_constraint_grid[y, x])
    reasons = [text for bit, text in HARD_REASONS.items() if hard & bit]
    components = {key: float(value[y, x]) for key, value in field.component_grids.items()}
    explanations = [f"Hard no-go: {reason}." for reason in reasons]
    sic = field.sic_percent[y, x]
    if np.isfinite(sic):
        explanations.append(
            f"Sea-ice concentration at this cell is {sic:.1f}% for the selected vessel profile."
        )
    if components["iceberg_hazard"] >= 0.5:
        explanations.append("Location intersects an iceberg exclusion or caution envelope.")
    if field.metadata["component_states"]["icebergs"] in {"STALE", "DEGRADED", "UNAVAILABLE"}:
        explanations.append(
            "Iceberg confidence is limited by report age, incomplete coverage or absent "
            "operational prediction."
        )
    explanations.append(
        f"{field.metadata['horizon_hours']:g}-hour sea-ice model uncertainty uses locked "
        "MAE as an error-scale proxy, not a probability."
    )
    if components["historical_transit_confidence"] == 0:
        explanations.append("No verified historical transit evidence is available at this cell.")
    else:
        explanations.append(
            "Historical corridor evidence changes preference cost only; it cannot override "
            "current hazard."
        )
    return {
        "requested_location": {"latitude": latitude, "longitude": longitude},
        "sampled_cell": {
            "row": y,
            "column": x,
            "latitude": float(field.latitude[y]),
            "longitude": float(field.longitude[x]),
            "method": "nearest grid center",
        },
        "risk_score": float(field.risk_grid[y, x]),
        "risk_category": CATEGORY_LABELS[int(field.risk_category_grid[y, x])],
        "navigable": bool(field.navigable_mask[y, x]),
        "navigation_cost": float(field.navigation_cost_grid[y, x])
        if field.navigable_mask[y, x]
        else None,
        "dominant_factor": DOMINANT_LABELS[int(field.dominant_factor_grid[y, x])],
        "components": components,
        "hard_constraints": reasons,
        "explanations": explanations,
        "metadata": field.metadata,
    }
