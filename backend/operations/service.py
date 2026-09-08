from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from backend.navigation.risk import service as risk_service

from .config import CONFIG
from .models import (
    EnvironmentChange,
    EnvironmentSnapshot,
    Freshness,
    Health,
    Mission,
    OperationalEvent,
    Position,
    SourceRecord,
)

LOGGER = logging.getLogger(__name__)
LOCK = RLock()
MISSIONS: dict[str, Mission] = {}
EVENTS: list[OperationalEvent] = []
CURRENT_SNAPSHOT: EnvironmentSnapshot | None = None


def classify_freshness(
    age_hours: float | None, expected_hours: float | None, *, available: bool = True
) -> Freshness:
    if not available or age_hours is None:
        return Freshness.UNAVAILABLE
    if expected_hours is None:
        return Freshness.NOT_APPLICABLE
    if age_hours <= expected_hours * CONFIG.aging_fraction:
        return Freshness.FRESH
    if age_hours <= expected_hours:
        return Freshness.AGING
    if age_hours <= expected_hours * CONFIG.stale_multiplier:
        return Freshness.STALE
    return Freshness.EXPIRED


def _record(
    source_id,
    name,
    provider,
    classification,
    status,
    freshness,
    version,
    *,
    description="",
    expected=None,
    age=None,
    limitations=None,
    available=True,
    coverage="Regional/declared scope",
):
    now = datetime.now(UTC)
    return SourceRecord(
        source_id=source_id,
        name=name,
        provider=provider,
        classification=classification,
        description=description,
        status=status,
        last_observation_time=None,
        last_refresh_time=now,
        expected_update_interval_hours=expected,
        age_hours=age,
        freshness_state=freshness,
        version=version,
        checksum_or_fingerprint=version,
        coverage=coverage,
        provenance={"classification": classification, "provider": provider},
        limitations=limitations or [],
        available=available,
        configured=True,
    )


def source_registry() -> list[SourceRecord]:
    try:
        risk = risk_service.status()
        risk_state = risk.get("state", "UNAVAILABLE")
        risk_health = (
            Health.HEALTHY
            if risk_state == "AVAILABLE"
            else Health.DEGRADED
            if risk_state == "DEGRADED"
            else Health.UNAVAILABLE
        )
        sea_state = risk.get("component_states", {}).get("sea_ice", "UNAVAILABLE")
        sea_fresh = (
            Freshness.FRESH
            if sea_state == "AVAILABLE"
            else Freshness.STALE
            if sea_state == "STALE"
            else Freshness.UNAVAILABLE
        )
        risk_version = hashlib.sha1(repr(risk.get("summary", {})).encode()).hexdigest()[:12]
    except Exception as error:
        risk = {}
        risk_health = Health.ERROR
        sea_fresh = Freshness.UNAVAILABLE
        risk_version = "unavailable"
        LOGGER.warning("operational risk health unavailable: %s", type(error).__name__)
    try:
        fp = hashlib.sha1(repr(risk_service.source_fingerprint()).encode()).hexdigest()[:12]
    except Exception:
        fp = "unavailable"
    historical_state = risk.get("component_states", {}).get(
        "historical_transit", "NO_VERIFIED_DATA"
    )
    historical_health = Health.HEALTHY if historical_state == "AVAILABLE" else Health.DEGRADED
    return [
        _record(
            "SEA_ICE_OBSERVATION",
            "Sea-ice observation",
            "Copernicus Marine / OSI-SAF",
            "OBSERVATION",
            risk_health,
            sea_fresh,
            fp,
            expected=24,
            age=None,
            limitations=["Existing scientific freshness rules remain authoritative."],
        ),
        _record(
            "SEA_ICE_FORECAST",
            "Sea-ice forecast",
            "POLARIS-AI v0.3",
            "MODEL_PREDICTION",
            risk_health,
            sea_fresh,
            fp,
            expected=24,
            limitations=["Validated through +72H."],
        ),
        _record(
            "ERA5_REANALYSIS",
            "ERA5 forcing",
            "ECMWF / Copernicus Climate",
            "REANALYSIS",
            Health.HEALTHY,
            Freshness.NOT_APPLICABLE,
            "era5-reanalysis",
            limitations=["Historical reanalysis, not a future forecast."],
        ),
        _record(
            "ICEBERG_REGISTRY",
            "Iceberg registry",
            "U.S. National Ice Center",
            "OBSERVATION",
            Health.DEGRADED
            if risk.get("component_states", {}).get("icebergs") != "AVAILABLE"
            else Health.HEALTHY,
            Freshness.STALE
            if risk.get("component_states", {}).get("icebergs") == "STALE"
            else Freshness.FRESH,
            fp,
            expected=168,
            limitations=["Qualifying iceberg coverage only."],
        ),
        _record(
            "ICEBERG_FORECAST",
            "Iceberg forecast",
            "POLARIS-AI engineering envelopes",
            "MODEL_PREDICTION",
            risk_health,
            sea_fresh,
            fp,
            expected=24,
            limitations=["No unobserved trajectory is invented."],
        ),
        _record(
            "HISTORICAL_TRANSIT",
            "Historical transit",
            "POLARIS verified store",
            "HISTORICAL_REFERENCE",
            historical_health,
            Freshness.NOT_APPLICABLE,
            historical_state,
            limitations=["Missing history does not block routing."],
        ),
        _record(
            "VESSEL_POSITION",
            "Vessel position",
            "Manual/operator input",
            "MANUAL_INPUT",
            Health.NOT_CONFIGURED,
            Freshness.UNAVAILABLE,
            "manual-only",
            available=False,
            limitations=["No live GPS/AIS adapter connected."],
        ),
        _record(
            "RISK_ENGINE",
            "Dynamic risk engine",
            "POLARIS-AI",
            "MODEL_PREDICTION",
            risk_health,
            sea_fresh,
            risk_version,
            limitations=["Decision-support risk, not certified safety."],
        ),
        _record(
            "ROUTING_ENGINE",
            "Time-dependent routing",
            "POLARIS-AI",
            "MODEL_PREDICTION",
            risk_health,
            sea_fresh,
            "checkpoint-5",
            limitations=["Regional domain; +72H horizon."],
        ),
        _record(
            "REPLANNING_ENGINE",
            "Dynamic replanning",
            "POLARIS-AI",
            "MODEL_PREDICTION",
            risk_health,
            sea_fresh,
            "checkpoint-6",
            limitations=["Manual/event-triggered only."],
        ),
    ]


def build_environment_snapshot() -> EnvironmentSnapshot:
    global CURRENT_SNAPSHOT
    records = source_registry()
    versions = {record.source_id: record.version for record in records}
    source_states = {record.source_id: record.status.value for record in records}
    freshness = {record.source_id: record.freshness_state.value for record in records}
    material = {
        key: versions[key]
        for key in (
            "SEA_ICE_OBSERVATION",
            "SEA_ICE_FORECAST",
            "ICEBERG_REGISTRY",
            "ICEBERG_FORECAST",
            "HISTORICAL_TRANSIT",
            "RISK_ENGINE",
        )
    }
    fingerprint = hashlib.sha256(repr(sorted(material.items())).encode()).hexdigest()[:20]
    CURRENT_SNAPSHOT = EnvironmentSnapshot(
        snapshot_id=f"snapshot-{fingerprint}",
        created_at=datetime.now(UTC),
        sea_ice_observation_version=versions["SEA_ICE_OBSERVATION"],
        sea_ice_forecast_version=versions["SEA_ICE_FORECAST"],
        iceberg_registry_version=versions["ICEBERG_REGISTRY"],
        iceberg_forecast_version=versions["ICEBERG_FORECAST"],
        historical_transit_version=versions["HISTORICAL_TRANSIT"],
        risk_config_version=versions["RISK_ENGINE"],
        source_states=source_states,
        source_freshness=freshness,
        geographic_domain="Bharati / Prydz Bay regional study area",
        forecast_initialization=None,
        valid_horizon_hours=72,
        fingerprint=fingerprint,
    )
    return CURRENT_SNAPSHOT


def current_snapshot() -> EnvironmentSnapshot:
    return build_environment_snapshot()


def compare_environment_snapshots(
    old: EnvironmentSnapshot, new: EnvironmentSnapshot
) -> EnvironmentChange:
    changes = []
    pairs = (
        ("SEA_ICE_OBSERVATION", "SEA_ICE_UPDATED"),
        ("SEA_ICE_FORECAST", "SEA_ICE_UPDATED"),
        ("ICEBERG_REGISTRY", "ICEBERG_REGISTRY_UPDATED"),
        ("HISTORICAL_TRANSIT", "HISTORICAL_TRANSIT_UPDATED"),
        ("RISK_ENGINE", "RISK_CONFIG_UPDATED"),
    )
    version_fields = {
        "SEA_ICE_OBSERVATION": "sea_ice_observation_version",
        "SEA_ICE_FORECAST": "sea_ice_forecast_version",
        "ICEBERG_REGISTRY": "iceberg_registry_version",
        "HISTORICAL_TRANSIT": "historical_transit_version",
        "RISK_ENGINE": "risk_config_version",
    }
    for key, label in pairs:
        if (
            old.source_states.get(key) != new.source_states.get(key)
            or old.source_freshness.get(key) != new.source_freshness.get(key)
            or getattr(old, version_fields[key]) != getattr(new, version_fields[key])
        ):
            if label not in changes:
                changes.append(label)
    return EnvironmentChange(
        changes=changes,
        material_change=bool(changes),
        old_snapshot_id=old.snapshot_id,
        new_snapshot_id=new.snapshot_id,
    )


def capabilities() -> dict:
    records = {record.source_id: record for record in source_registry()}
    critical = records["RISK_ENGINE"].status in {Health.UNAVAILABLE, Health.ERROR} or records[
        "SEA_ICE_OBSERVATION"
    ].freshness_state in {Freshness.UNAVAILABLE, Freshness.EXPIRED}
    return {
        name: {
            "status": "BLOCKED"
            if critical
            and name in {"FORECAST_SEA_ICE", "COMPUTE_RISK", "PLAN_ROUTE", "REPLAN_ROUTE"}
            else "DEGRADED"
            if name in {"TRACK_ACTIVE_MISSION"}
            else "AVAILABLE",
            "reason_codes": ["CRITICAL_ENVIRONMENT_UNAVAILABLE"] if critical else [],
        }
        for name in (
            "VIEW_SEA_ICE",
            "VIEW_ICEBERGS",
            "FORECAST_SEA_ICE",
            "COMPUTE_RISK",
            "PLAN_ROUTE",
            "ACTIVATE_ROUTE",
            "REPLAN_ROUTE",
            "TRACK_ACTIVE_MISSION",
        )
    }


def health() -> dict:
    records = source_registry()
    snapshot = build_environment_snapshot()
    blockers = [
        record.source_id
        for record in records
        if record.status in {Health.UNAVAILABLE, Health.ERROR}
        and record.source_id in {"SEA_ICE_OBSERVATION", "RISK_ENGINE"}
    ]
    warnings = [
        record.source_id
        for record in records
        if record.freshness_state in {Freshness.STALE, Freshness.EXPIRED}
        or record.status == Health.DEGRADED
    ]
    overall = "BLOCKED" if blockers else "DEGRADED" if warnings else "HEALTHY"
    return {
        "overall_status": overall,
        "component_statuses": {record.source_id: record.status.value for record in records},
        "data_source_statuses": [record.model_dump(mode="json") for record in records],
        "critical_blockers": blockers,
        "warnings": warnings,
        "latest_environment_version": snapshot.snapshot_id,
        "active_mission_status": next(
            (mission.status for mission in MISSIONS.values() if mission.status == "ACTIVE"), None
        ),
        "capabilities": capabilities(),
    }


def _event(event_type, message, severity="INFO", *, mission_id=None, reason_codes=None):
    event = OperationalEvent(
        event_id=f"op-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        event_type=event_type,
        severity=severity,
        mission_id=mission_id,
        environment_snapshot_id=current_snapshot().snapshot_id,
        message=message,
        reason_codes=reason_codes or [],
        provenance={"component": "operations"},
    )
    EVENTS.append(event)
    return event


def create_mission(payload: dict) -> Mission:
    now = datetime.now(UTC)
    mission = Mission(mission_id=f"mission-{uuid4().hex[:10]}", created_at=now, **payload)
    mission.environment_snapshot_id = current_snapshot().snapshot_id
    mission.readiness = mission_readiness(mission)
    MISSIONS[mission.mission_id] = mission
    _event("MISSION_CREATED", "Mission created", mission_id=mission.mission_id)
    return mission


def mission_readiness(mission: Mission) -> str:
    state = health()["overall_status"]
    return "BLOCKED" if state == "BLOCKED" else "DEGRADED" if state == "DEGRADED" else "READY"


TRANSITIONS = {
    "DRAFT": {"PLANNED"},
    "PLANNED": {"ACTIVE", "ABORTED"},
    "ACTIVE": {"PAUSED", "COMPLETED", "ABORTED"},
    "PAUSED": {"ACTIVE", "ABORTED"},
    "COMPLETED": set(),
    "ABORTED": set(),
    "BLOCKED": {"PLANNED", "ABORTED"},
}


def transition(mission_id: str, target: str) -> Mission:
    mission = MISSIONS.get(mission_id)
    if mission is None:
        raise ValueError("MISSION_NOT_FOUND")
    if target not in TRANSITIONS.get(mission.status, set()):
        raise ValueError(f"INVALID_MISSION_TRANSITION:{mission.status}->{target}")
    mission.status = target
    mission.readiness = mission_readiness(mission)
    _event(f"MISSION_{target}", f"Mission transitioned to {target}", mission_id=mission_id)
    return mission


def update_position(mission_id: str, position: Position) -> Mission:
    mission = MISSIONS.get(mission_id)
    if mission is None:
        raise ValueError("MISSION_NOT_FOUND")
    mission.current_position = position
    mission.position_source = position.source_type
    _event("VESSEL_POSITION_UPDATED", "Manual or simulated position updated", mission_id=mission_id)
    return mission
