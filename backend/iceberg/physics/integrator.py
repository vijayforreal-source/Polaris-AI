import math
from collections.abc import Callable
from datetime import datetime, timedelta

from backend.iceberg.motion import GEOD
from backend.iceberg.physics.models import HindcastTrajectory, TrajectoryPoint
from backend.iceberg.physics.parameters import WDE17Parameters
from backend.iceberg.physics.wde17 import analytical_velocity

VectorSampler = Callable[[float, float, datetime], tuple[float | None, float | None]]


def geodesic_step(
    latitude: float,
    longitude: float,
    eastward_velocity: float,
    northward_velocity: float,
    elapsed_seconds: float,
) -> tuple[float, float]:
    speed = math.hypot(eastward_velocity, northward_velocity)
    if speed == 0:
        return latitude, longitude
    bearing = math.degrees(math.atan2(eastward_velocity, northward_velocity))
    next_longitude, next_latitude, _ = GEOD.fwd(
        longitude, latitude, bearing, speed * elapsed_seconds
    )
    return next_latitude, next_longitude


def integrate_trajectory(
    model: str,
    start_time: datetime,
    end_time: datetime,
    start_latitude: float,
    start_longitude: float,
    ocean_sampler: VectorSampler | None,
    wind_sampler: VectorSampler | None = None,
    length_m: float = 0.0,
    width_m: float = 0.0,
    timestep_hours: float = 1.0,
    forcing_depth_m: float | None = None,
    parameters: WDE17Parameters | None = None,
) -> HindcastTrajectory:
    if end_time <= start_time or timestep_hours <= 0:
        raise ValueError("Integration time and timestep must be positive")
    current_time = start_time
    latitude, longitude = start_latitude, start_longitude
    points = [TrajectoryPoint(current_time, latitude, longitude)]
    ratios: list[float] = []
    while current_time < end_time:
        step_seconds = min(
            timestep_hours * 3600.0, (end_time - current_time).total_seconds()
        )
        ocean_u = ocean_v = 0.0
        if model != "P0_PERSISTENCE":
            if ocean_sampler is None:
                raise ValueError("This trajectory model requires ocean forcing")
            sampled_u, sampled_v = ocean_sampler(latitude, longitude, current_time)
            if sampled_u is None or sampled_v is None:
                return HindcastTrajectory(
                    model, "HINDCAST", "MODEL_PREDICTION", "OUT_OF_FORCING_DOMAIN", tuple(points)
                )
            ocean_u, ocean_v = sampled_u, sampled_v
        wind_u = wind_v = None
        lambda_value = alpha = beta = None
        iceberg_u, iceberg_v = ocean_u, ocean_v
        if model in {"P3_WDE17", "P2W_EMPIRICAL_2_PERCENT_WIND"}:
            if wind_sampler is None:
                raise ValueError("This trajectory model requires wind forcing")
            wind_u, wind_v = wind_sampler(latitude, longitude, current_time)
            if wind_u is None or wind_v is None:
                return HindcastTrajectory(
                    model, "HINDCAST", "MODEL_PREDICTION", "OUT_OF_FORCING_DOMAIN", tuple(points)
                )
            if model == "P3_WDE17":
                drift = analytical_velocity(
                    ocean_u,
                    ocean_v,
                    wind_u,
                    wind_v,
                    latitude,
                    length_m,
                    width_m,
                    parameters,
                )
                iceberg_u, iceberg_v = drift.eastward, drift.northward
                lambda_value, alpha, beta = drift.lambda_value, drift.alpha, drift.beta
                ocean_speed = math.hypot(ocean_u, ocean_v)
                if ocean_speed > 0:
                    ratios.append(drift.wind_contribution_speed / ocean_speed)
            else:
                iceberg_u = ocean_u + 0.02 * wind_u
                iceberg_v = ocean_v + 0.02 * wind_v
        latitude, longitude = geodesic_step(
            latitude, longitude, iceberg_u, iceberg_v, step_seconds
        )
        current_time += timedelta(seconds=step_seconds)
        points.append(
            TrajectoryPoint(
                current_time,
                latitude,
                longitude,
                ocean_u,
                ocean_v,
                wind_u,
                wind_v,
                iceberg_u,
                iceberg_v,
                lambda_value,
                alpha,
                beta,
            )
        )
    return HindcastTrajectory(
        model,
        "HINDCAST",
        "MODEL_PREDICTION",
        "COMPLETE",
        tuple(points),
        forcing_depth_m,
        tuple(ratios),
    )
