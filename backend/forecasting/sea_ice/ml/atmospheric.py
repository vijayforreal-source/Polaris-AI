from pathlib import Path

import numpy as np
import xarray as xr

from .dataset import FORCING_VARIABLES

ERA5_DATASET_ID = "reanalysis-era5-single-levels"
ERA5_REQUEST_VARIABLES = (
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
)


def load_daily_forcing(
    path: Path,
    sea_ice_times: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> np.ndarray:
    """Load verified daily forcing and align it without using future timestamps."""
    with xr.open_dataset(path) as source:
        missing = set(FORCING_VARIABLES) - set(source.data_vars)
        if missing:
            raise ValueError(f"Atmospheric forcing variables missing: {sorted(missing)}")
        native_times = source.time.values.astype("datetime64[D]")
        if len(np.unique(native_times)) != len(native_times):
            raise ValueError("Forcing must contain exactly one value per UTC day")
        requested = sea_ice_times.astype("datetime64[D]")
        if not np.array_equal(native_times, requested):
            raise ValueError("Forcing days must exactly match sea-ice observation days")
        return np.stack(
            [
                _bilinear_regrid(
                    np.asarray(source[name].values),
                    np.asarray(source.latitude.values),
                    np.asarray(source.longitude.values),
                    latitude,
                    longitude,
                )
                for name in FORCING_VARIABLES
            ],
            axis=1,
        )


def _bilinear_regrid(
    values: np.ndarray,
    source_latitude: np.ndarray,
    source_longitude: np.ndarray,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
) -> np.ndarray:
    """Bilinear interpolation on a monotonic rectilinear grid without extrapolation."""
    latitude_order = np.argsort(source_latitude)
    longitude_order = np.argsort(source_longitude)
    lat = source_latitude[latitude_order]
    lon = source_longitude[longitude_order]
    data = values[:, latitude_order][:, :, longitude_order]
    result = np.full(
        (len(values), len(target_latitude), len(target_longitude)),
        np.nan,
        dtype="float32",
    )
    for target_y, latitude_value in enumerate(target_latitude):
        if latitude_value < lat[0] or latitude_value > lat[-1]:
            continue
        upper_y = min(max(int(np.searchsorted(lat, latitude_value)), 1), len(lat) - 1)
        lower_y = upper_y - 1
        y_weight = (latitude_value - lat[lower_y]) / (lat[upper_y] - lat[lower_y])
        for target_x, longitude_value in enumerate(target_longitude):
            if longitude_value < lon[0] or longitude_value > lon[-1]:
                continue
            upper_x = min(
                max(int(np.searchsorted(lon, longitude_value)), 1), len(lon) - 1
            )
            lower_x = upper_x - 1
            x_weight = (longitude_value - lon[lower_x]) / (
                lon[upper_x] - lon[lower_x]
            )
            corners = data[
                :,
                [lower_y, lower_y, upper_y, upper_y],
                [lower_x, upper_x, lower_x, upper_x],
            ]
            finite = np.all(np.isfinite(corners), axis=1)
            lower = corners[:, 0] * (1 - x_weight) + corners[:, 1] * x_weight
            upper = corners[:, 2] * (1 - x_weight) + corners[:, 3] * x_weight
            interpolated = lower * (1 - y_weight) + upper * y_weight
            result[finite, target_y, target_x] = interpolated[finite]
    return result
