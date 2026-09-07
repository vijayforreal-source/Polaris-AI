from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from backend.navigation.routing.models import Objective, RouteResult

Decision = Literal[
    "KEEP_CURRENT",
    "REROUTE_RECOMMENDED",
    "REROUTE_REQUIRED",
    "NO_SAFE_ALTERNATIVE",
    "REPLAN_UNAVAILABLE",
    "FORECAST_HORIZON_EXCEEDED",
    "NO_MATERIAL_CHANGE",
]


class ActiveVoyage(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    voyage_id: str
    route_id: str
    objective: Objective
    vessel_id: str
    origin: dict[str, Any]
    destination: dict[str, Any]
    departure_time: AwareDatetime
    current_time: AwareDatetime
    current_position_lat: float = Field(ge=-90, le=90)
    current_position_lon: float = Field(ge=-180, le=180)
    current_waypoint_index: int = Field(ge=0)
    current_route: RouteResult
    route_created_at: AwareDatetime
    last_replan_at: AwareDatetime | None = None
    last_environment_version: str
    status: str = "ACTIVE"


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    voyage_id: str = Field(min_length=1, max_length=100)
    route: RouteResult
    current_time: AwareDatetime | None = None


class PositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    current_time: AwareDatetime


class ReplanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    decision: Decision
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str
    environment_version: str
    voyage: ActiveVoyage | None
    current_metrics: dict[str, Any] | None = None
    candidate_metrics: dict[str, Any] | None = None
    delta: dict[str, Any] = Field(default_factory=dict)
    candidate_route: RouteResult | None = None
    event_id: str | None = None
    evaluated_at: AwareDatetime


class ReplanEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: str
    voyage_id: str
    timestamp: AwareDatetime
    environment_version: str
    previous_route_id: str
    candidate_route_id: str | None
    decision: Decision
    reason_codes: list[str]
    metrics_before: dict[str, Any] | None
    metrics_after: dict[str, Any] | None
    delta: dict[str, Any]
    acknowledgement_status: str = "PENDING"
    provenance: dict[str, Any]
