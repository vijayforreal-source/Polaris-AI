from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrajectoryModel(StrEnum):
    P2_SURFACE_CURRENT = "P2_SURFACE_CURRENT"
    WDE17_SURFACE = "WDE17_SURFACE"
    H0_EFFECTIVE_CURRENT_HYBRID = "H0_EFFECTIVE_CURRENT_HYBRID"
    H1_HYBRID_WDE17_STYLE = "H1_HYBRID_WDE17_STYLE"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    FORCING_UNAVAILABLE = "FORCING_DATA_UNAVAILABLE_FOR_REQUESTED_HORIZON"


class TrajectoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iceberg_id: str = Field(min_length=1)
    initial_latitude: float = Field(ge=-90, le=90)
    initial_longitude: float = Field(ge=-180, le=180)
    initial_time: datetime
    prediction_horizon_hours: int = Field(default=24)
    model: TrajectoryModel = TrajectoryModel.P2_SURFACE_CURRENT

    @field_validator("initial_time")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("initial_time must include an explicit timezone")
        return value

    @field_validator("prediction_horizon_hours")
    @classmethod
    def supported_horizon(cls, value: int) -> int:
        if value not in {6, 12, 24, 48, 72}:
            raise ValueError("prediction_horizon_hours must be one of 6, 12, 24, 48, 72")
        return value


class Position(BaseModel):
    latitude: float
    longitude: float


class PublicTrajectoryPoint(Position):
    time: datetime


class UncertaintyEnvelope(BaseModel):
    label: str
    applicable: bool
    radius_50_km: float | None = None
    radius_80_km: float | None = None
    radius_95_km: float | None = None
    note: str


class ActualObservation(Position):
    observed_on: str
    classification: str = "OBSERVATION"
    endpoint_error_km: float


class TrajectoryResponse(BaseModel):
    model: TrajectoryModel
    model_status: str
    mode: str = "HISTORICAL HINDCAST"
    classification: str = "MODEL_PREDICTION"
    iceberg_id: str
    start_time: datetime
    requested_horizon_hours: int
    actual_horizon_hours: float
    start_position: Position
    trajectory_points: list[PublicTrajectoryPoint]
    endpoint: Position | None
    actual_historical_observation: ActualObservation | None = None
    environment_sources: dict[str, str]
    uncertainty: UncertaintyEnvelope
    availability_status: AvailabilityStatus
    scientific_warnings: list[str]

