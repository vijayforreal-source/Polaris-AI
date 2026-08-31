from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

from backend.environment.copernicus_currents import DATASET_ID, current_files
from backend.environment.models import EnvironmentalForcingSample
from backend.environment.sampling import interpolate_vector
from backend.iceberg.history import load_history, tracks_by_iceberg
from backend.iceberg.motion import GEOD


def a76c_track():
    return tracks_by_iceberg(load_history().points)["A76C"]


def build_point_samples() -> list[EnvironmentalForcingSample]:
    track = a76c_track()
    samples: list[EnvironmentalForcingSample] = []
    for path in current_files():
        with xr.open_dataset(path) as dataset:
            depth = float(dataset.depth.item())
            for point in track:
                sampling_time = datetime.combine(point.observation_date, datetime.min.time(), UTC)
                u_value, v_value, flags = interpolate_vector(
                    dataset, point.latitude, point.longitude, sampling_time
                )
                samples.append(
                    EnvironmentalForcingSample(
                        valid_at=sampling_time,
                        iceberg_id="A76C",
                        iceberg_latitude=point.latitude,
                        iceberg_longitude=point.longitude,
                        ocean_u=u_value,
                        ocean_v=v_value,
                        ocean_depth=depth,
                        source_ocean=DATASET_ID,
                        quality_flags=["USNIC_DATE_PRECISION_ONLY", "ERA5_AUTHENTICATION_REQUIRED"]
                        + flags,
                        provenance={
                            "ocean_file": path.as_posix(),
                            "usnic_files": ";".join(point.source_files),
                        },
                    )
                )
    return samples


def build_interval_summaries() -> list[dict[str, object]]:
    """Summarize surface forcing along the observed geodesic path approximation."""
    track = a76c_track()
    surface_path = current_files()[0]
    summaries: list[dict[str, object]] = []
    with xr.open_dataset(surface_path) as dataset:
        for start, end in zip(track, track[1:], strict=False):
            start_time = datetime.combine(start.observation_date, datetime.min.time(), UTC)
            end_time = datetime.combine(end.observation_date, datetime.min.time(), UTC)
            duration_seconds = (end_time - start_time).total_seconds()
            bearing, _, distance_m = GEOD.inv(
                start.longitude, start.latitude, end.longitude, end.latitude
            )
            times = []
            cursor = start_time
            while cursor <= end_time:
                times.append(cursor)
                cursor += timedelta(hours=6)
            u_values: list[float] = []
            v_values: list[float] = []
            for sample_time in times:
                fraction = (sample_time - start_time).total_seconds() / duration_seconds
                longitude, latitude, _ = GEOD.fwd(
                    start.longitude, start.latitude, bearing, distance_m * fraction
                )
                u_value, v_value, _ = interpolate_vector(
                    dataset, latitude, longitude, sample_time
                )
                if u_value is not None and v_value is not None:
                    u_values.append(u_value)
                    v_values.append(v_value)
            speeds = np.hypot(u_values, v_values)
            observed_speed = distance_m / duration_seconds
            observed_east = observed_speed * np.sin(np.deg2rad(bearing))
            observed_north = observed_speed * np.cos(np.deg2rad(bearing))
            summaries.append(
                {
                    "start_date": start.observation_date.isoformat(),
                    "end_date": end.observation_date.isoformat(),
                    "duration_hours": duration_seconds / 3600,
                    "mean_ocean_u": float(np.mean(u_values)) if u_values else None,
                    "mean_ocean_v": float(np.mean(v_values)) if v_values else None,
                    "std_ocean_u": float(np.std(u_values)) if u_values else None,
                    "std_ocean_v": float(np.std(v_values)) if v_values else None,
                    "minimum_ocean_speed": float(np.min(speeds)) if len(speeds) else None,
                    "maximum_ocean_speed": float(np.max(speeds)) if len(speeds) else None,
                    "valid_ocean_samples": len(u_values),
                    "expected_ocean_samples": len(times),
                    "coverage_percentage": 100 * len(u_values) / len(times),
                    "observed_east_velocity": float(observed_east),
                    "observed_north_velocity": float(observed_north),
                    "wind_status": "ERA5_AUTHENTICATION_REQUIRED",
                }
            )
    return summaries


def write_processed_dataset(
    samples: list[EnvironmentalForcingSample],
    path: Path = Path("data/processed/environment/a76c_forcing.nc"),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = xr.Dataset(
        data_vars={
            "ocean_u": ("sample", [sample.ocean_u for sample in samples]),
            "ocean_v": ("sample", [sample.ocean_v for sample in samples]),
            "wind_u10": ("sample", np.full(len(samples), np.nan)),
            "wind_v10": ("sample", np.full(len(samples), np.nan)),
            "quality_flags": (
                "sample",
                [";".join(sample.quality_flags) for sample in samples],
            ),
            "ocean_source_file": (
                "sample",
                [sample.provenance["ocean_file"] for sample in samples],
            ),
            "usnic_source_files": (
                "sample",
                [sample.provenance["usnic_files"] for sample in samples],
            ),
        },
        coords={
            "sample": np.arange(len(samples)),
            "time": ("sample", [sample.valid_at.replace(tzinfo=None) for sample in samples]),
            "latitude": ("sample", [sample.iceberg_latitude for sample in samples]),
            "longitude": ("sample", [sample.iceberg_longitude for sample in samples]),
            "depth": ("sample", [sample.ocean_depth for sample in samples]),
        },
        attrs={
            "title": "POLARIS-AI A76C track-aligned environmental forcing",
            "ocean_classification": "ANALYSIS",
            "wind_classification": "REANALYSIS",
            "wind_status": "ERA5_AUTHENTICATION_REQUIRED; values intentionally missing",
            "usnic_classification": "OBSERVATION",
            "spatial_interpolation": "bilinear regular latitude/longitude",
            "temporal_interpolation": "linear",
            "date_semantics": "USNIC date-only positions sampled at 00 UTC by explicit convention",
        },
    )
    dataset.ocean_u.attrs["units"] = "m s-1"
    dataset.ocean_v.attrs["units"] = "m s-1"
    dataset.wind_u10.attrs["units"] = "m s-1"
    dataset.wind_v10.attrs["units"] = "m s-1"
    dataset.to_netcdf(path)
    return path
