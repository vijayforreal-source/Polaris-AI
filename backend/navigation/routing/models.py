from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Objective = Literal["SAFE", "FAST", "ECO", "BALANCED"]


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RoutePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    origin: Coordinate
    destination: Coordinate
    departure_time: AwareDatetime
    vessel_id: str = Field(min_length=1, max_length=80)
    objectives: list[Objective] = Field(
        default_factory=lambda: ["SAFE", "FAST", "ECO", "BALANCED"], min_length=1
    )
    time_bucket_hours: float = Field(1, gt=0, le=6)


class RouteWaypoint(BaseModel):
    sequence: int
    latitude: float
    longitude: float
    arrival_time: AwareDatetime
    elapsed_hours: float
    segment_distance_km: float
    segment_time_hours: float
    risk_score: float
    risk_category: str
    navigable: bool
    navigation_cost: float | None
    dominant_risk_factor: str
    sea_ice_hazard: float
    iceberg_hazard: float
    uncertainty_hazard: float
    vessel_constraint_hazard: float
    historical_transit_confidence: float


class RouteResult(BaseModel):
    route_id: str
    objective: Objective
    status: str
    reason: str | None = None
    origin: dict
    destination: dict
    departure_time: AwareDatetime
    arrival_time: AwareDatetime | None = None
    eta_hours: float | None = None
    distance_km: float | None = None
    distance_nm: float | None = None
    mean_risk: float | None = None
    max_risk: float | None = None
    cumulative_risk_exposure: float | None = None
    time_in_LOW: float = 0
    time_in_GUARDED: float = 0
    time_in_ELEVATED: float = 0
    time_in_HIGH: float = 0
    time_in_CRITICAL: float = 0
    eco_cost_proxy: float | None = None
    maximum_uncertainty: float | None = None
    blocked_cells_avoided: int = 0
    historical_transit_support: str
    waypoints: list[RouteWaypoint] = Field(default_factory=list)
    display_waypoints: list[RouteWaypoint] = Field(default_factory=list)
    explanation: str
    provenance: dict
    expanded_states: int = 0


class RouteComparison(BaseModel):
    objective: Objective
    distance_difference_km: float | None = None
    eta_difference_hours: float | None = None
    mean_risk_difference: float | None = None
    max_risk_difference: float | None = None
    cumulative_risk_difference: float | None = None
    eco_proxy_difference: float | None = None
