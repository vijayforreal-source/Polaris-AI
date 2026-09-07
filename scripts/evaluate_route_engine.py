"""Deterministic engineering evaluation for the regional route planner."""

import json
from datetime import UTC, datetime

from backend.navigation.risk import service
from backend.navigation.risk.vessel import get_vessel
from backend.navigation.routing.engine import RoutePlanner


def main():
    vessel = get_vessel("simulated-research")
    planner = RoutePlanner(
        lambda horizon: service.get_risk_field(horizon_hours=horizon, vessel_profile=vessel),
        vessel,
        datetime.now(UTC),
    )
    report = {"domain": "Bharati / Prydz Bay regional study area", "objectives": {}}
    for objective in ("SAFE", "FAST", "ECO", "BALANCED"):
        try:
            route = planner.plan((-69.4, 76.2), (-68.8, 77.1), objective)
            report["objectives"][objective] = route.model_dump(
                mode="json", exclude={"waypoints", "display_waypoints"}
            )
        except Exception as error:
            report["objectives"][objective] = {
                "status": getattr(error, "code", "ERROR"),
                "reason": str(error),
            }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
