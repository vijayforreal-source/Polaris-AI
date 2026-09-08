from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Freshness(StrEnum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Health(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source_id: str
    name: str
    provider: str
    classification: str
    description: str
    status: Health
    last_observation_time: AwareDatetime | None = None
    last_refresh_time: AwareDatetime | None = None
    expected_update_interval_hours: float | None = None
    age_hours: float | None = None
    freshness_state: Freshness
    version: str
    checksum_or_fingerprint: str | None = None
    coverage: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    configured: bool = True
    available: bool = True
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_error_time: AwareDatetime | None = None
    retryable: bool = False


class EnvironmentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    snapshot_id: str
    created_at: AwareDatetime
    sea_ice_observation_version: str
    sea_ice_forecast_version: str
    iceberg_registry_version: str
    iceberg_forecast_version: str
    historical_transit_version: str
    risk_config_version: str
    source_states: dict[str, str]
    source_freshness: dict[str, str]
    geographic_domain: str
    forecast_initialization: str | None
    valid_horizon_hours: int
    fingerprint: str


class EnvironmentChange(BaseModel):
    changes: list[str]
    material_change: bool
    old_snapshot_id: str | None = None
    new_snapshot_id: str


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: AwareDatetime
    source_type: str
    source_id: str
    accuracy_m: float | None = Field(None, ge=0)
    is_simulated: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mission_id: str
    name: str
    status: str = "DRAFT"
    vessel_id: str
    origin: dict[str, Any]
    destination: dict[str, Any]
    created_at: AwareDatetime
    planned_departure: AwareDatetime | None = None
    actual_departure: AwareDatetime | None = None
    active_route_id: str | None = None
    active_voyage_id: str | None = None
    current_position: Position | None = None
    position_source: str | None = None
    environment_snapshot_id: str | None = None
    objective: str = "BALANCED"
    notes: str | None = None
    readiness: str = "DEGRADED"


class OperationalEvent(BaseModel):
    event_id: str
    timestamp: AwareDatetime
    event_type: str
    severity: str
    mission_id: str | None = None
    voyage_id: str | None = None
    source_id: str | None = None
    environment_snapshot_id: str | None = None
    message: str
    reason_codes: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
