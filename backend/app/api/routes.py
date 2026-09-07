from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from backend.navigation.risk import service as risk_service
from backend.navigation.risk.vessel import PROFILES, get_vessel
from backend.navigation.routing.engine import OBJECTIVES, RoutePlanner, RoutePlanningError
from backend.navigation.routing.models import RoutePlanRequest

router = APIRouter(prefix="/api/routes", tags=["routing"])


@router.get("/status")
def routing_status():
    risk = risk_service.status()
    return {
        "routing_available": risk.get("state") not in {"UNAVAILABLE"},
        "risk_engine_state": risk.get("state", "UNAVAILABLE"),
        "supported_objectives": list(OBJECTIVES),
        "supported_horizons_hours": [0, 24, 48, 72],
        "vessel_profiles": [v.model_dump(mode="json") for v in PROFILES.values()],
        "routing_domain": "Bharati / Prydz Bay regional study area",
        "limitations": [
            "Research decision-support recommendation, not a certified navigational route.",
            "Forecast conditions are validated only through +72H.",
            "No bathymetry or propulsion/fuel model is included.",
        ],
    }


@router.post("/plan")
def plan_routes(request: RoutePlanRequest):
    try:
        vessel = get_vessel(request.vessel_id)
        departure = request.departure_time.astimezone(UTC)
        planner = RoutePlanner(
            lambda horizon: risk_service.get_risk_field(
                horizon_hours=horizon, vessel_profile=vessel
            ),
            vessel,
            departure,
            bucket_hours=request.time_bucket_hours,
        )
        routes = []
        failures = []
        for objective in dict.fromkeys(request.objectives):
            try:
                routes.append(
                    planner.plan(
                        (request.origin.latitude, request.origin.longitude),
                        (request.destination.latitude, request.destination.longitude),
                        objective,
                    ).model_dump(mode="json")
                )
            except RoutePlanningError as error:
                failures.append(
                    {"objective": objective, "status": error.code, "reason": error.message}
                )
        status = (
            "AVAILABLE" if routes else (failures[0]["status"] if failures else "NO_ROUTE_FOUND")
        )
        return {
            "status": status,
            "routes": routes,
            "failures": failures,
            "request": request.model_dump(mode="json"),
            "provenance": {
                "routing_domain": "Bharati / Prydz Bay regional study area",
                "risk_engine": "Checkpoint 4",
                "generated_at": datetime.now(UTC).isoformat(),
            },
        }
    except ValueError as error:
        message = str(error)
        if message == "UNKNOWN_VESSEL_PROFILE":
            raise HTTPException(422, detail=message) from error
        raise HTTPException(
            503, detail={"status": "ENVIRONMENT_UNAVAILABLE", "reason": message}
        ) from error
