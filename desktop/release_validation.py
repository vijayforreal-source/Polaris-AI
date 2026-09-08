"""Isolated packaged DEMO validation; never starts a production API server."""
from datetime import UTC, datetime

import numpy as np

from backend.navigation.risk.models import RiskField


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


def run_demo():
    from backend.app.api.routes import plan_routes
    from backend.navigation.replanning import service as replan
    from backend.navigation.risk import service as risk
    from backend.navigation.routing.models import RoutePlanRequest
    from backend.operations import service as operations

    # This process exits after validation. Synthetic fields never enter the desktop server.
    risk.get_risk_field = lambda *args, **kwargs: _field()
    request = RoutePlanRequest(
        origin={"latitude": -70, "longitude": 70},
        destination={"latitude": -68, "longitude": 72},
        departure_time=datetime.now(UTC), vessel_id="simulated-research",
    )
    mission = operations.create_mission({
        "name": "DEMO / SIMULATED release validation",
        "vessel_id": request.vessel_id, "origin": request.origin.model_dump(),
        "destination": request.destination.model_dump(), "objective": "SAFE",
        "notes": "Isolated synthetic process; not current environmental data",
    })
    response = plan_routes(request)
    assert len(response["routes"]) == 4, response
    from backend.navigation.routing.models import RouteResult
    route = RouteResult.model_validate(response["routes"][0])
    replan.activate(mission.mission_id, route, request.departure_time)
    risk.get_risk_field = lambda *args, **kwargs: _field(blocked=True)
    decision = replan.replan()
    assert decision.decision == "REROUTE_REQUIRED", decision
    assert replan.active().route_id == route.route_id
    accepted = replan.accept(decision.event_id, decision.candidate_route.route_id)
    assert accepted.route_id == decision.candidate_route.route_id
    return {"classification": "DEMO / SIMULATED",
            "objectives": [r["objective"] for r in response["routes"]],
            "decision": decision.decision, "captain_acceptance": "PASSED"}
