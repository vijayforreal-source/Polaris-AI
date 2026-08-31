from dataclasses import dataclass
from datetime import date
from statistics import median

from pydantic import BaseModel, ConfigDict, Field
from pyproj import Geod

from backend.iceberg.models import IcebergTrackPoint

GEOD = Geod(ellps="WGS84")
KM_PER_NAUTICAL_MILE = 1.852


class MotionThresholds(BaseModel):
    """Transparent QC/classification thresholds for provider-quantized positions."""

    model_config = ConfigDict(frozen=True)

    low_motion_km: float = Field(default=10.0, gt=0)
    minimum_candidate_positions: int = Field(default=4, ge=3)
    minimum_candidate_displacement_km: float = Field(default=50.0, gt=0)
    data_gap_days: int = Field(default=21, ge=1)
    malformed_speed_knots: float = Field(default=10.0, gt=0)


@dataclass(frozen=True)
class MotionStep:
    start_date: date
    end_date: date
    elapsed_hours: float
    distance_km: float
    distance_nm: float
    speed_knots: float
    bearing_degrees: float
    flagged_malformed_jump: bool


@dataclass(frozen=True)
class TrackMetrics:
    iceberg_id: str
    record_count: int
    distinct_dated_positions: int
    unique_position_count: int
    duration_days: int
    cumulative_displacement_km: float
    start_to_end_displacement_km: float
    median_step_km: float
    maximum_step_km: float
    data_gap_count: int
    classification: str
    candidate: bool
    malformed_jump_count: int


def geodesic_inverse(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> tuple[float, float]:
    bearing, _, distance_m = GEOD.inv(
        start_longitude, start_latitude, end_longitude, end_latitude
    )
    return distance_m / 1000.0, bearing % 360.0


def motion_steps(
    track: list[IcebergTrackPoint], thresholds: MotionThresholds | None = None
) -> list[MotionStep]:
    limits = thresholds or MotionThresholds()
    steps: list[MotionStep] = []
    for start, end in zip(track, track[1:], strict=False):
        elapsed_hours = (end.observation_date - start.observation_date).total_seconds() / 3600
        if elapsed_hours <= 0:
            continue
        distance_km, bearing = geodesic_inverse(
            start.latitude, start.longitude, end.latitude, end.longitude
        )
        distance_nm = distance_km / KM_PER_NAUTICAL_MILE
        speed_knots = distance_nm / elapsed_hours
        steps.append(
            MotionStep(
                start.observation_date,
                end.observation_date,
                elapsed_hours,
                distance_km,
                distance_nm,
                speed_knots,
                bearing,
                speed_knots > limits.malformed_speed_knots,
            )
        )
    return steps


def analyze_track(
    track: list[IcebergTrackPoint],
    record_count: int | None = None,
    thresholds: MotionThresholds | None = None,
) -> TrackMetrics:
    if not track:
        raise ValueError("Track must contain at least one observation")
    limits = thresholds or MotionThresholds()
    ordered = sorted(track, key=lambda point: point.observation_date)
    steps = motion_steps(ordered, limits)
    positions = {(point.latitude, point.longitude) for point in ordered}
    distances = [step.distance_km for step in steps]
    duration_days = (ordered[-1].observation_date - ordered[0].observation_date).days
    cumulative = sum(distances)
    end_to_end = geodesic_inverse(
        ordered[0].latitude,
        ordered[0].longitude,
        ordered[-1].latitude,
        ordered[-1].longitude,
    )[0]
    malformed = sum(step.flagged_malformed_jump for step in steps)
    gaps = sum(step.elapsed_hours / 24 > limits.data_gap_days for step in steps)
    if len(ordered) < 2:
        classification = "INSUFFICIENT HISTORY"
    elif len(positions) == 1:
        classification = "APPARENTLY STATIONARY"
    elif cumulative < limits.low_motion_km:
        classification = "LOW-MOTION"
    else:
        classification = "MOVING"
    candidate = (
        len(ordered) >= limits.minimum_candidate_positions
        and cumulative >= limits.minimum_candidate_displacement_km
        and gaps == 0
        and malformed == 0
    )
    return TrackMetrics(
        iceberg_id=ordered[0].iceberg_id,
        record_count=record_count if record_count is not None else len(ordered),
        distinct_dated_positions=len(ordered),
        unique_position_count=len(positions),
        duration_days=duration_days,
        cumulative_displacement_km=cumulative,
        start_to_end_displacement_km=end_to_end,
        median_step_km=median(distances) if distances else 0.0,
        maximum_step_km=max(distances, default=0.0),
        data_gap_count=gaps,
        classification=classification,
        candidate=candidate,
        malformed_jump_count=malformed,
    )


def select_baseline_candidate(metrics: list[TrackMetrics]) -> TrackMetrics:
    candidates = [metric for metric in metrics if metric.candidate]
    if not candidates:
        raise ValueError("No track satisfies the configured trajectory baseline criteria")
    return max(candidates, key=lambda metric: metric.cumulative_displacement_km)
