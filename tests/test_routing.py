from datetime import UTC, datetime

import numpy as np
import pytest

from backend.navigation.risk.models import RiskField
from backend.navigation.risk.vessel import get_vessel
from backend.navigation.routing.engine import RoutePlanner, RoutePlanningError


def field_factory(hazard=None, blocked=None):
    lat = np.array([-70.0, -69.0, -68.0])
    lon = np.array([70.0, 71.0, 72.0, 73.0])
    shape = (3, 4)
    risk = np.full(shape, 0.1)
    if hazard:
        risk[hazard] = 0.95
    nav = np.ones(shape, dtype=bool)
    if blocked:
        nav[blocked] = False
    components = {
        key: np.zeros(shape)
        for key in (
            "sea_ice_hazard",
            "iceberg_hazard",
            "uncertainty_hazard",
            "vessel_constraint_hazard",
            "historical_transit_confidence",
        )
    }
    components["sea_ice_hazard"] = risk.copy()
    return RiskField(
        lat,
        lon,
        risk,
        risk.copy(),
        nav,
        np.searchsorted((0.2, 0.4, 0.6, 0.8), risk).astype("uint8"),
        np.zeros(shape, "uint8"),
        np.where(nav, 0, 1).astype("uint16"),
        components,
        np.zeros(shape),
        {
            "dominant_factor_labels": (
                "SEA_ICE",
                "ICEBERG",
                "UNCERTAINTY",
                "VESSEL_CONSTRAINT",
                "LAND",
                "DATA_UNAVAILABLE",
            )
        },
    )


def planner(provider):
    return RoutePlanner(
        provider, get_vessel("simulated-research"), datetime(2026, 1, 1, tzinfo=UTC)
    )


def test_route_metrics_and_diagonal_distance():
    result = planner(lambda _: field_factory()).plan((-70, 70), (-68, 73), "FAST")
    assert result.status == "AVAILABLE"
    assert result.distance_km > 0
    assert result.waypoints[-1].arrival_time > result.waypoints[0].arrival_time


def test_hard_no_go_is_never_traversed():
    result = planner(lambda _: field_factory(blocked=(1, 1))).plan((-70, 70), (-68, 73), "FAST")
    assert all(point.navigable for point in result.waypoints)


def test_dynamic_hazard_changes_safe_route():
    def provider(horizon):
        return field_factory(hazard=(1, 1) if horizon >= 1 else None)

    result = planner(provider).plan((-70, 70), (-68, 73), "SAFE")
    assert all(point.risk_score < 0.9 for point in result.waypoints)


def test_blocked_destination_is_explicit():
    with pytest.raises(RoutePlanningError, match="hard no-go") as error:
        planner(lambda _: field_factory(blocked=(2, 3))).plan((-70, 70), (-68, 73), "FAST")
    assert error.value.code == "DESTINATION_BLOCKED"


def test_horizon_limit_is_enforced():
    with pytest.raises(RoutePlanningError):
        RoutePlanner(
            lambda _: field_factory(),
            get_vessel("simulated-research"),
            datetime(2026, 1, 1, tzinfo=UTC),
            max_horizon_hours=0.01,
        ).plan((-70, 70), (-68, 73), "FAST")
