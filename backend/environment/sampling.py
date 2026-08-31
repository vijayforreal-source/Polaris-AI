import math
from datetime import datetime

import numpy as np
import xarray as xr


def normalize_longitude(longitude: float, minimum: float = -180.0) -> float:
    return (longitude - minimum) % 360.0 + minimum


def vector_magnitude(u_component: float, v_component: float) -> float:
    return math.hypot(u_component, v_component)


def vector_direction(u_component: float, v_component: float) -> float:
    """Direction toward which the east/north vector points, clockwise from north."""
    return math.degrees(math.atan2(u_component, v_component)) % 360.0


def interpolate_vector(
    dataset: xr.Dataset, latitude: float, longitude: float, valid_at: datetime
) -> tuple[float | None, float | None, list[str]]:
    flags: list[str] = []
    longitude = normalize_longitude(longitude)
    if not (
        float(dataset.latitude.min()) <= latitude <= float(dataset.latitude.max())
        and float(dataset.longitude.min()) <= longitude <= float(dataset.longitude.max())
    ):
        return None, None, ["OUTSIDE_SPATIAL_COVERAGE"]
    timestamp = np.datetime64(valid_at.replace(tzinfo=None))
    if timestamp < dataset.time.min() or timestamp > dataset.time.max():
        return None, None, ["OUTSIDE_TEMPORAL_COVERAGE"]
    time_values = dataset.time.values
    latitudes = dataset.latitude.values
    longitudes = dataset.longitude.values

    def bracket(values: np.ndarray, target) -> tuple[int, int, float]:
        upper = int(np.searchsorted(values, target, side="right"))
        upper = min(max(upper, 1), len(values) - 1)
        lower = upper - 1
        span = values[upper] - values[lower]
        if np.issubdtype(values.dtype, np.datetime64):
            span_value = float(span / np.timedelta64(1, "ns"))
            offset_value = float((target - values[lower]) / np.timedelta64(1, "ns"))
        else:
            span_value = float(span)
            offset_value = float(target - values[lower])
        weight = offset_value / span_value if span_value else 0.0
        return lower, upper, weight

    time_lower, time_upper, time_weight = bracket(time_values, timestamp)
    lat_lower, lat_upper, lat_weight = bracket(latitudes, latitude)
    lon_lower, lon_upper, lon_weight = bracket(longitudes, longitude)

    def interpolate(name: str) -> float:
        values = dataset[name].isel(
            depth=0,
            time=[time_lower, time_upper],
            latitude=[lat_lower, lat_upper],
            longitude=[lon_lower, lon_upper],
        ).values
        temporal_values = []
        for time_index in (0, 1):
            corners = values[time_index].ravel()
            if not np.all(np.isfinite(corners)):
                return float("nan")
            lower_lat = corners[0] * (1 - lon_weight) + corners[1] * lon_weight
            upper_lat = corners[2] * (1 - lon_weight) + corners[3] * lon_weight
            temporal_values.append(lower_lat * (1 - lat_weight) + upper_lat * lat_weight)
        return float(
            temporal_values[0] * (1 - time_weight) + temporal_values[1] * time_weight
        )

    u_value = interpolate("uo")
    v_value = interpolate("vo")
    if not math.isfinite(u_value) or not math.isfinite(v_value):
        flags.append("MISSING_SOURCE_VALUE")
        return None, None, flags
    return u_value, v_value, flags
