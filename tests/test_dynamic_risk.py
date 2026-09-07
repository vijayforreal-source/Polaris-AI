from datetime import UTC, datetime

import numpy as np
import pytest

from backend.navigation.risk.components import (
    iceberg_hazards,
    interpolate_sic,
    sea_ice_hazards,
)
from backend.navigation.risk.config import CATEGORY_LABELS, CONFIG
from backend.navigation.risk.engine import compute_risk, risk_categories
from backend.navigation.risk.models import IcebergState, RiskInputs
from backend.navigation.risk.vessel import PROFILES, VesselProfile

NOW = datetime(2026, 9, 7, tzinfo=UTC)


def make_inputs(**updates):
    base = dict(
        latitude=np.array([-70.0, -69.0]),
        longitude=np.array([75.0, 76.0]),
        ocean_mask=np.ones((2, 2), dtype=bool),
        sic={
            0: np.full((2, 2), 10.0),
            24: np.full((2, 2), 30.0),
            48: np.full((2, 2), 50.0),
            72: np.full((2, 2), 70.0),
        },
        initialization_time=NOW,
        as_of=NOW,
        sea_ice_age_days=0,
        iceberg_report_age_days=0,
        iceberg_coverage_incomplete=False,
        historical_state="NO_VERIFIED_DATA",
        iceberg_state="AVAILABLE",
    )
    base.update(updates)
    return RiskInputs(**base)


def test_categories_have_exact_boundaries():
    assert risk_categories(np.array([0, 0.2, 0.4, 0.6, 0.8, 1.0])).tolist() == [0, 1, 2, 3, 4, 4]
    assert CATEGORY_LABELS == ("LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL")


def test_sic_hazard_monotonic_and_capability_changes_mapping():
    sic = np.array([[0.0, 15.0, 40.0, 70.0, 100.0]])
    strong, _, _, _ = sea_ice_hazards(sic, PROFILES["simulated-research"], CONFIG)
    open_water, _, _, _ = sea_ice_hazards(sic, PROFILES["simulated-open-water"], CONFIG)
    assert np.all(np.diff(strong[0]) >= 0)
    assert np.all(open_water >= strong)


def test_interpolation_and_horizon_exceeded():
    fields, metadata = interpolate_sic({0: np.zeros((1, 1)), 24: np.full((1, 1), 20.0)}, 12, (1, 1))
    assert fields[0, 0] == 10 and metadata["interpolation_fraction"] == 0.5
    fields, metadata = interpolate_sic({0: np.zeros((1, 1))}, 73, (1, 1))
    assert np.isnan(fields[0, 0]) and metadata["status"] == "FORECAST_HORIZON_EXCEEDED"


def test_hard_land_and_missing_sic_are_no_go():
    inputs = make_inputs(
        ocean_mask=np.array([[True, False], [True, True]]), sic={0: np.full((2, 2), 10.0)}
    )
    field = compute_risk(inputs, 0, PROFILES["simulated-research"])
    assert not field.navigable_mask[0, 1]
    assert np.isnan(field.navigation_cost_grid[0, 1])
    missing = compute_risk(make_inputs(sic={}), 0, PROFILES["simulated-research"])
    assert not missing.navigable_mask.all()
    assert np.all(missing.risk_grid == 1)


def test_unknown_vessel_capability_is_hard_blocked_and_uncertain():
    vessel = VesselProfile(
        vessel_id="unknown",
        name="Unknown",
        vessel_type="UNKNOWN",
        length_m=10,
        beam_m=2,
        draft_m=1,
        nominal_speed_knots=5,
        source="test",
        provenance="test",
    )
    field = compute_risk(make_inputs(), 0, vessel)
    assert not field.navigable_mask.any()
    assert np.all(field.component_grids["uncertainty_hazard"] >= 0.35)


def test_iceberg_distance_decay_and_exclusion():
    base = make_inputs()
    near = IcebergState(
        iceberg_id="T",
        latitude=-70,
        longitude=75,
        observed_at=NOW,
        uncertainty_radius_km=0,
        source="test",
    )
    far = near.model_copy(update={"latitude": -68, "longitude": 80})
    # Mutate only immutable dataclass input lists through replacement.
    base.icebergs = [near]
    close = iceberg_hazards(base, 0, PROFILES["simulated-research"], CONFIG)
    base.icebergs = [far]
    distant = iceberg_hazards(base, 0, PROFILES["simulated-research"], CONFIG)
    assert close[0][0, 0] > distant[0][0, 0]
    assert close[1][0, 0]


def test_historical_experience_changes_cost_not_safety():
    no_history = compute_risk(make_inputs(), 0, PROFILES["simulated-research"])
    history = compute_risk(
        make_inputs(
            historical_state="AVAILABLE",
            historical_cells=[
                {"bbox": [74.5, -70.5, 75.5, -69.5], "unique_voyages": 4, "recency_score": 1.0}
            ],
        ),
        0,
        PROFILES["simulated-research"],
    )
    assert np.array_equal(no_history.risk_grid, history.risk_grid)
    assert history.component_grids["experience_bonus"][0, 0] == CONFIG.experience_bonus_max * (
        1 - np.exp(-4 / CONFIG.historical_frequency_scale)
    )
    assert history.navigation_cost_grid[0, 0] < no_history.navigation_cost_grid[0, 0]
    assert history.component_grids["experience_bonus"].max() <= CONFIG.experience_bonus_max


def test_stale_and_beyond_horizon_are_degraded_or_blocked():
    stale = compute_risk(
        make_inputs(sea_ice_age_days=10, sea_ice_state="STALE"), 24, PROFILES["simulated-research"]
    )
    assert not stale.navigable_mask.any()
    beyond = compute_risk(make_inputs(), 73, PROFILES["simulated-research"])
    assert not beyond.navigable_mask.any()
    assert beyond.metadata["interpolation"]["status"] == "FORECAST_HORIZON_EXCEEDED"


def test_point_service_rejects_invalid_coordinates():
    with pytest.raises(ValueError, match="INVALID_COORDINATES"):
        from backend.navigation.risk.engine import explain_point

        explain_point(compute_risk(make_inputs(), 0, PROFILES["simulated-research"]), 100, 75)
