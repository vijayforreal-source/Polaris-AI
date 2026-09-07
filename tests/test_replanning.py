from datetime import UTC, datetime, timedelta

import numpy as np

from backend.navigation.replanning.config import ReplanningConfig
from backend.navigation.replanning.engine import ReplanningEngine
from backend.navigation.replanning.models import ActiveVoyage
from backend.navigation.risk.models import RiskField
from backend.navigation.risk.vessel import get_vessel
from backend.navigation.routing.engine import RoutePlanner
from backend.navigation.routing.models import RouteResult, RouteWaypoint


def _field(blocked=False, risk=0.1):
    lat = np.array([-70.0, -69.0, -68.0])
    lon = np.array([70.0, 71.0, 72.0])
    shape = (3, 3)
    nav = np.ones(shape, bool)
    nav[1, 1] = not blocked
    values = np.full(shape, risk)
    components = {
        key: np.full(shape, risk if key == "sea_ice_hazard" else 0.1)
        for key in (
            "sea_ice_hazard",
            "iceberg_hazard",
            "uncertainty_hazard",
            "vessel_constraint_hazard",
            "historical_transit_confidence",
        )
    }
    return RiskField(
        lat,
        lon,
        values,
        values.copy(),
        nav,
        np.zeros(shape, "uint8"),
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


def _route(risk=0.1):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    points = [
        RouteWaypoint(
            sequence=i,
            latitude=-70 + i,
            longitude=70 + i,
            arrival_time=start + timedelta(hours=i),
            elapsed_hours=i,
            segment_distance_km=10,
            segment_time_hours=1,
            risk_score=risk,
            risk_category="LOW",
            navigable=True,
            navigation_cost=risk,
            dominant_risk_factor="SEA_ICE",
            sea_ice_hazard=risk,
            iceberg_hazard=0.1,
            uncertainty_hazard=0.1,
            vessel_constraint_hazard=0.1,
            historical_transit_confidence=0,
        )
        for i in range(3)
    ]
    return RouteResult(
        route_id="route-old",
        objective="SAFE",
        status="AVAILABLE",
        origin={"mapped": {"latitude": -70, "longitude": 70}},
        destination={"mapped": {"latitude": -68, "longitude": 72}},
        departure_time=start,
        arrival_time=points[-1].arrival_time,
        eta_hours=2,
        distance_km=20,
        distance_nm=10.8,
        mean_risk=risk,
        max_risk=risk,
        cumulative_risk_exposure=risk * 20,
        eco_cost_proxy=20,
        maximum_uncertainty=0.1,
        historical_transit_support="NO_VERIFIED_DATA",
        waypoints=points,
        display_waypoints=points,
        explanation="test",
        provenance={"vessel_profile": "simulated-research"},
    )


def _voyage(route):
    return ActiveVoyage(
        voyage_id="v1",
        route_id=route.route_id,
        objective=route.objective,
        vessel_id="simulated-research",
        origin=route.origin,
        destination=route.destination,
        departure_time=route.departure_time,
        current_time=route.departure_time,
        current_position_lat=-70,
        current_position_lon=70,
        current_waypoint_index=0,
        current_route=route,
        route_created_at=route.departure_time,
        last_environment_version="old",
    )


def _engine(provider, candidate):
    vessel = get_vessel("simulated-research")
    return ReplanningEngine(
        provider,
        lambda *args: candidate,
        vessel,
        config=ReplanningConfig(cooldown_minutes=30),
        environment_version_provider=lambda: "new",
    )


def test_hard_route_change_requires_reroute():
    old = _route()
    candidate = _route(0.05)
    candidate.route_id = "route-new"
    decision = _engine(lambda _h, _v: _field(blocked=True), candidate).replan(_voyage(old))
    assert decision.decision == "REROUTE_REQUIRED"


def test_small_improvement_keeps_current():
    old = _route(0.10)
    candidate = _route(0.095)
    candidate.route_id = "route-new"
    candidate.distance_km = 30
    candidate.eta_hours = 3
    candidate.cumulative_risk_exposure = 2.85
    decision = _engine(lambda _h, _v: _field(risk=0.10), candidate).replan(_voyage(old))
    assert decision.decision == "KEEP_CURRENT"
    assert "IMPROVEMENT_BELOW_THRESHOLD" in decision.reason_codes


def test_cooldown_keeps_soft_recommendation():
    old = _route(0.10)
    old_voyage = _voyage(old)
    old_voyage.last_replan_at = old_voyage.current_time
    candidate = _route(0.01)
    candidate.route_id = "route-new"
    decision = _engine(lambda _h, _v: _field(risk=0.1), candidate).replan(old_voyage)
    assert decision.decision == "KEEP_CURRENT"
    assert "REPLAN_COOLDOWN_ACTIVE" in decision.reason_codes


def test_route_planner_candidate_starts_at_current_position():
    route = _route()
    vessel = get_vessel("simulated-research")
    planner = RoutePlanner(lambda _h: _field(), vessel, route.departure_time)
    result = planner.plan((-70, 70), (-68, 72), "SAFE")
    assert result.waypoints[0].latitude == -70
