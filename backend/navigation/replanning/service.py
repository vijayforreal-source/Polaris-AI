from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from threading import RLock

from backend.navigation.risk import service as risk_service
from backend.navigation.risk.vessel import get_vessel
from backend.navigation.routing.engine import RoutePlanner
from backend.navigation.routing.models import RouteResult

from .config import CONFIG
from .engine import ReplanningEngine
from .models import ActiveVoyage, ReplanDecision, ReplanEvent

LOCK = RLock()
ACTIVE: ActiveVoyage | None = None
EVENTS: list[ReplanEvent] = []
LAST_DECISION: ReplanDecision | None = None


def environment_version() -> str:
    try:
        fingerprint = risk_service.source_fingerprint()
        return "env-" + hashlib.sha256(repr(fingerprint).encode()).hexdigest()[:16]
    except Exception:
        return "env-unavailable"


def _engine(vessel_id: str, now: datetime, origin, destination, objective):
    vessel = get_vessel(vessel_id)
    return ReplanningEngine(
        lambda horizon, profile: risk_service.get_risk_field(
            horizon_hours=horizon, vessel_profile=profile
        ),
        lambda departure, start, end, selected: RoutePlanner(
            lambda horizon: risk_service.get_risk_field(
                horizon_hours=horizon, vessel_profile=vessel
            ),
            vessel,
            departure,
        ),
        vessel,
        environment_version_provider=environment_version,
    )


def activate(
    voyage_id: str, route: RouteResult, current_time: datetime | None = None
) -> ActiveVoyage:
    global ACTIVE
    now = (current_time or datetime.now(UTC)).astimezone(UTC)
    mapped = route.origin.get("mapped", route.origin.get("requested", {}))
    with LOCK:
        ACTIVE = ActiveVoyage(
            voyage_id=voyage_id,
            route_id=route.route_id,
            objective=route.objective,
            vessel_id=route.provenance.get("vessel_profile", "simulated-research"),
            origin=route.origin,
            destination=route.destination,
            departure_time=route.departure_time,
            current_time=now,
            current_position_lat=float(mapped["latitude"]),
            current_position_lon=float(mapped["longitude"]),
            current_waypoint_index=0,
            current_route=route,
            route_created_at=now,
            last_environment_version=environment_version(),
        )
        return ACTIVE


def active() -> ActiveVoyage | None:
    return ACTIVE


def update_position(latitude: float, longitude: float, current_time: datetime) -> ActiveVoyage:
    if ACTIVE is None:
        raise ValueError("NO_ACTIVE_VOYAGE")
    ACTIVE.current_position_lat = latitude
    ACTIVE.current_position_lon = longitude
    ACTIVE.current_time = current_time.astimezone(UTC)
    candidates = [
        p.sequence for p in ACTIVE.current_route.waypoints if p.arrival_time >= ACTIVE.current_time
    ]
    ACTIVE.current_waypoint_index = (
        min(candidates) if candidates else len(ACTIVE.current_route.waypoints) - 1
    )
    return ACTIVE


def evaluate() -> dict:
    if ACTIVE is None:
        raise ValueError("NO_ACTIVE_VOYAGE")
    return _engine(
        ACTIVE.vessel_id,
        ACTIVE.current_time,
        (ACTIVE.current_position_lat, ACTIVE.current_position_lon),
        (0, 0),
        ACTIVE.objective,
    ).evaluate_route(ACTIVE)


def replan() -> ReplanDecision:
    global LAST_DECISION
    if ACTIVE is None:
        raise ValueError("NO_ACTIVE_VOYAGE")
    engine = _engine(
        ACTIVE.vessel_id,
        ACTIVE.current_time,
        (ACTIVE.current_position_lat, ACTIVE.current_position_lon),
        (0, 0),
        ACTIVE.objective,
    )
    decision = engine.replan(ACTIVE)
    LAST_DECISION = decision
    event = ReplanEvent(
        event_id="event-"
        + hashlib.sha1(
            f"{ACTIVE.voyage_id}-{decision.evaluated_at.isoformat()}".encode()
        ).hexdigest()[:12],
        voyage_id=ACTIVE.voyage_id,
        timestamp=decision.evaluated_at,
        environment_version=decision.environment_version,
        previous_route_id=ACTIVE.route_id,
        candidate_route_id=decision.candidate_route.route_id if decision.candidate_route else None,
        decision=decision.decision,
        reason_codes=decision.reason_codes,
        metrics_before=decision.current_metrics,
        metrics_after=decision.candidate_metrics,
        delta=decision.delta,
        provenance={
            "risk_engine": "Checkpoint 4",
            "routing_algorithm": "Checkpoint 5 time-dependent Dijkstra",
            "threshold_config": CONFIG.model_dump(),
        },
    )
    decision.event_id = event.event_id
    EVENTS.append(event)
    return decision


def accept(event_id: str, candidate_route_id: str) -> ActiveVoyage:
    if ACTIVE is None:
        raise ValueError("NO_ACTIVE_VOYAGE")
    event = next((item for item in EVENTS if item.event_id == event_id), None)
    if (
        event is None
        or event.candidate_route_id != candidate_route_id
        or LAST_DECISION is None
        or LAST_DECISION.candidate_route is None
    ):
        raise ValueError("UNKNOWN_REROUTE_EVENT")
    ACTIVE.current_route = LAST_DECISION.candidate_route
    ACTIVE.route_id = ACTIVE.current_route.route_id
    ACTIVE.last_replan_at = datetime.now(UTC)
    ACTIVE.last_environment_version = event.environment_version
    event.acknowledgement_status = "ACCEPTED"
    return ACTIVE


def status() -> dict:
    return {
        "checkpoint": "CHECKPOINT_6",
        "active_voyage_exists": ACTIVE is not None,
        "last_replan": LAST_DECISION.model_dump(mode="json") if LAST_DECISION else None,
        "current_environment_version": environment_version(),
        "supported_decisions": [
            "KEEP_CURRENT",
            "REROUTE_RECOMMENDED",
            "REROUTE_REQUIRED",
            "NO_SAFE_ALTERNATIVE",
            "REPLAN_UNAVAILABLE",
            "FORECAST_HORIZON_EXCEEDED",
        ],
        "threshold_config": CONFIG.model_dump(),
        "limitations": [
            "Single-process in-memory state; manual position updates only.",
            "No live AIS, GPS, polling, or autonomous control.",
        ],
    }
