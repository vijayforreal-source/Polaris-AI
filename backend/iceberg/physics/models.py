from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TrajectoryPoint:
    valid_at: datetime
    latitude: float
    longitude: float
    ocean_u: float | None = None
    ocean_v: float | None = None
    wind_u: float | None = None
    wind_v: float | None = None
    iceberg_u: float | None = None
    iceberg_v: float | None = None
    lambda_value: float | None = None
    alpha: float | None = None
    beta: float | None = None


@dataclass(frozen=True)
class HindcastTrajectory:
    model: str
    evaluation_mode: str
    classification: str
    status: str
    points: tuple[TrajectoryPoint, ...]
    forcing_depth_m: float | None = None
    wind_contribution_ratios: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IntervalEvaluation:
    model: str
    start_date: str
    end_date: str
    horizon_hours: float
    endpoint_error_km: float
    endpoint_error_nm: float
    observed_displacement_km: float
    predicted_displacement_km: float
    bearing_error_degrees: float | None
    status: str
