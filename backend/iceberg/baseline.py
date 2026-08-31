from dataclasses import dataclass

from pyproj import Geod

from backend.iceberg.models import IcebergTrackPoint
from backend.iceberg.motion import KM_PER_NAUTICAL_MILE, geodesic_inverse

GEOD = Geod(ellps="WGS84")


@dataclass(frozen=True)
class BaselinePrediction:
    method: str
    classification: str
    forecast_horizon_hours: float
    predicted_latitude: float
    predicted_longitude: float
    actual_latitude: float
    actual_longitude: float
    error_km: float
    error_nm: float


def _result(
    method: str,
    horizon_hours: float,
    predicted_latitude: float,
    predicted_longitude: float,
    actual: IcebergTrackPoint,
) -> BaselinePrediction:
    error_km, _ = geodesic_inverse(
        predicted_latitude, predicted_longitude, actual.latitude, actual.longitude
    )
    return BaselinePrediction(
        method=method,
        classification="MODEL_PREDICTION",
        forecast_horizon_hours=horizon_hours,
        predicted_latitude=predicted_latitude,
        predicted_longitude=predicted_longitude,
        actual_latitude=actual.latitude,
        actual_longitude=actual.longitude,
        error_km=error_km,
        error_nm=error_km / KM_PER_NAUTICAL_MILE,
    )


def persistence_baseline(
    latest: IcebergTrackPoint, actual: IcebergTrackPoint
) -> BaselinePrediction:
    horizon = (actual.observation_date - latest.observation_date).total_seconds() / 3600
    if horizon <= 0:
        raise ValueError("Held-out observation must be later than the latest input")
    return _result(
        "TRAJECTORY_BASELINE_PERSISTENCE",
        horizon,
        latest.latitude,
        latest.longitude,
        actual,
    )


def constant_velocity_baseline(
    previous: IcebergTrackPoint,
    latest: IcebergTrackPoint,
    actual: IcebergTrackPoint,
) -> BaselinePrediction:
    training_hours = (latest.observation_date - previous.observation_date).total_seconds() / 3600
    horizon = (actual.observation_date - latest.observation_date).total_seconds() / 3600
    if training_hours <= 0 or horizon <= 0:
        raise ValueError("Baseline observations must be in strictly increasing time order")
    bearing, _, distance_m = GEOD.inv(
        previous.longitude, previous.latitude, latest.longitude, latest.latitude
    )
    propagated_m = distance_m / training_hours * horizon
    predicted_lon, predicted_lat, _ = GEOD.fwd(
        latest.longitude, latest.latitude, bearing, propagated_m
    )
    return _result(
        "TRAJECTORY_BASELINE_CONSTANT_VELOCITY",
        horizon,
        predicted_lat,
        predicted_lon,
        actual,
    )


def rolling_origin_validation(
    track: list[IcebergTrackPoint],
) -> list[tuple[BaselinePrediction, BaselinePrediction]]:
    ordered = sorted(track, key=lambda point: point.observation_date)
    return [
        (
            persistence_baseline(ordered[index - 1], ordered[index]),
            constant_velocity_baseline(
                ordered[index - 2], ordered[index - 1], ordered[index]
            ),
        )
        for index in range(2, len(ordered))
    ]
