from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

from backend.environment.copernicus_currents import DATASET_ID, current_files
from backend.environment.era5_wind import DATASET_ID as ERA5_DATASET_ID
from backend.environment.era5_wind import load_wind_dataset
from backend.environment.models import EnvironmentalForcingSample
from backend.environment.sampling import (
    interpolate_vector,
    vector_direction,
    vector_magnitude,
)
from backend.iceberg.history import load_history, tracks_by_iceberg
from backend.iceberg.motion import GEOD
from backend.ingestion.models import ScientificClassification


def a76c_track():
    return tracks_by_iceberg(load_history().points)["A76C"]


def build_point_samples() -> list[EnvironmentalForcingSample]:
    track = a76c_track()
    samples: list[EnvironmentalForcingSample] = []
    wind_dataset = load_wind_dataset().sortby("latitude")
    try:
        wind_by_date: dict[object, tuple[float | None, float | None, list[str]]] = {}
        for point in track:
            sampling_time = datetime.combine(point.observation_date, datetime.min.time(), UTC)
            wind_by_date[point.observation_date] = interpolate_vector(
                wind_dataset,
                point.latitude,
                point.longitude,
                sampling_time,
                u_name="u10",
                v_name="v10",
            )
        for path in current_files():
            with xr.open_dataset(path) as dataset:
                depth = float(dataset.depth.item())
                for point in track:
                    sampling_time = datetime.combine(
                        point.observation_date, datetime.min.time(), UTC
                    )
                    u_value, v_value, flags = interpolate_vector(
                        dataset, point.latitude, point.longitude, sampling_time
                    )
                    wind_u, wind_v, wind_flags = wind_by_date[point.observation_date]
                    samples.append(
                        EnvironmentalForcingSample(
                            valid_at=sampling_time,
                            iceberg_id="A76C",
                            iceberg_latitude=point.latitude,
                            iceberg_longitude=point.longitude,
                            ocean_u=u_value,
                            ocean_v=v_value,
                            ocean_depth=depth,
                            wind_u10=wind_u,
                            wind_v10=wind_v,
                            source_ocean=DATASET_ID,
                            source_wind=ERA5_DATASET_ID,
                            classification_wind=ScientificClassification.REANALYSIS,
                            quality_flags=["USNIC_DATE_PRECISION_ONLY"]
                            + flags
                            + wind_flags,
                            provenance={
                                "ocean_file": path.as_posix(),
                                "wind_files": "monthly ERA5 files 2026-01 through 2026-08",
                                "usnic_files": ";".join(point.source_files),
                            },
                        )
                    )
    finally:
        wind_dataset.close()
    return samples


def _component_summary(u_values: list[float], v_values: list[float]) -> dict[str, object]:
    speeds = np.hypot(u_values, v_values)
    return {
        "mean_u": float(np.mean(u_values)) if u_values else None,
        "mean_v": float(np.mean(v_values)) if v_values else None,
        "std_u": float(np.std(u_values)) if u_values else None,
        "std_v": float(np.std(v_values)) if v_values else None,
        "minimum_speed": float(np.min(speeds)) if len(speeds) else None,
        "maximum_speed": float(np.max(speeds)) if len(speeds) else None,
        "mean_speed": float(np.mean(speeds)) if len(speeds) else None,
        "valid_samples": len(u_values),
    }


def _path_position(
    sample_time: datetime,
    start_time: datetime,
    duration_seconds: float,
    start_latitude: float,
    start_longitude: float,
    bearing: float,
    distance_m: float,
) -> tuple[float, float]:
    fraction = (sample_time - start_time).total_seconds() / duration_seconds
    longitude, latitude, _ = GEOD.fwd(
        start_longitude, start_latitude, bearing, distance_m * fraction
    )
    return latitude, longitude


def build_interval_summaries() -> list[dict[str, object]]:
    """Summarize forcing along the observed geodesic path approximation."""
    track = a76c_track()
    summaries: list[dict[str, object]] = []
    ocean_datasets = [xr.open_dataset(path) for path in current_files()]
    wind_dataset = load_wind_dataset().sortby("latitude")
    try:
        for start, end in zip(track, track[1:], strict=False):
            start_time = datetime.combine(start.observation_date, datetime.min.time(), UTC)
            end_time = datetime.combine(end.observation_date, datetime.min.time(), UTC)
            duration_seconds = (end_time - start_time).total_seconds()
            bearing, _, distance_m = GEOD.inv(
                start.longitude, start.latitude, end.longitude, end.latitude
            )
            ocean_summaries: dict[str, object] = {}
            for dataset in ocean_datasets:
                times = []
                cursor = start_time
                while cursor <= end_time:
                    times.append(cursor)
                    cursor += timedelta(hours=6)
                u_values: list[float] = []
                v_values: list[float] = []
                for sample_time in times:
                    latitude, longitude = _path_position(
                        sample_time,
                        start_time,
                        duration_seconds,
                        start.latitude,
                        start.longitude,
                        bearing,
                        distance_m,
                    )
                    u_value, v_value, _ = interpolate_vector(
                        dataset, latitude, longitude, sample_time
                    )
                    if u_value is not None and v_value is not None:
                        u_values.append(u_value)
                        v_values.append(v_value)
                depth = float(dataset.depth.item())
                ocean_summaries[f"{depth:.6f}"] = {
                    **_component_summary(u_values, v_values),
                    "expected_samples": len(times),
                    "coverage_percentage": 100 * len(u_values) / len(times),
                }

            wind_times = []
            cursor = start_time
            while cursor <= end_time:
                wind_times.append(cursor)
                cursor += timedelta(hours=1)
            wind_u_values: list[float] = []
            wind_v_values: list[float] = []
            for sample_time in wind_times:
                latitude, longitude = _path_position(
                    sample_time,
                    start_time,
                    duration_seconds,
                    start.latitude,
                    start.longitude,
                    bearing,
                    distance_m,
                )
                u_value, v_value, _ = interpolate_vector(
                    wind_dataset,
                    latitude,
                    longitude,
                    sample_time,
                    u_name="u10",
                    v_name="v10",
                )
                if u_value is not None and v_value is not None:
                    wind_u_values.append(u_value)
                    wind_v_values.append(v_value)
            observed_speed = distance_m / duration_seconds
            observed_east = observed_speed * np.sin(np.deg2rad(bearing))
            observed_north = observed_speed * np.cos(np.deg2rad(bearing))
            summaries.append(
                {
                    "start_date": start.observation_date.isoformat(),
                    "end_date": end.observation_date.isoformat(),
                    "duration_hours": duration_seconds / 3600,
                    "ocean_by_depth": ocean_summaries,
                    "wind": {
                        **_component_summary(wind_u_values, wind_v_values),
                        "expected_samples": len(wind_times),
                        "coverage_percentage": 100 * len(wind_u_values) / len(wind_times),
                    },
                    "observed_east_velocity": float(observed_east),
                    "observed_north_velocity": float(observed_north),
                }
            )
    finally:
        for dataset in ocean_datasets:
            dataset.close()
        wind_dataset.close()
    return summaries


def write_processed_dataset(
    samples: list[EnvironmentalForcingSample],
    path: Path = Path("data/processed/environment/a76c_forcing.nc"),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ocean_speed = [
        vector_magnitude(sample.ocean_u, sample.ocean_v)
        if sample.ocean_u is not None and sample.ocean_v is not None
        else np.nan
        for sample in samples
    ]
    ocean_direction = [
        vector_direction(sample.ocean_u, sample.ocean_v)
        if sample.ocean_u is not None and sample.ocean_v is not None
        else np.nan
        for sample in samples
    ]
    wind_speed = [
        vector_magnitude(sample.wind_u10, sample.wind_v10)
        if sample.wind_u10 is not None and sample.wind_v10 is not None
        else np.nan
        for sample in samples
    ]
    wind_direction = [
        vector_direction(sample.wind_u10, sample.wind_v10)
        if sample.wind_u10 is not None and sample.wind_v10 is not None
        else np.nan
        for sample in samples
    ]
    dataset = xr.Dataset(
        data_vars={
            "ocean_u": ("sample", [sample.ocean_u for sample in samples]),
            "ocean_v": ("sample", [sample.ocean_v for sample in samples]),
            "wind_u10": ("sample", [sample.wind_u10 for sample in samples]),
            "wind_v10": ("sample", [sample.wind_v10 for sample in samples]),
            "ocean_speed": ("sample", ocean_speed),
            "ocean_direction": ("sample", ocean_direction),
            "wind_speed": ("sample", wind_speed),
            "wind_direction": ("sample", wind_direction),
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
            "wind_source_files": (
                "sample",
                [sample.provenance["wind_files"] for sample in samples],
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
            "wind_status": "ERA5 available through 2026-08-26T12:00Z; final 35 hours missing",
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
    dataset.ocean_speed.attrs.update(units="m s-1", derivation="hypot(ocean_u, ocean_v)")
    dataset.wind_speed.attrs.update(units="m s-1", derivation="hypot(wind_u10, wind_v10)")
    for name in ("ocean_direction", "wind_direction"):
        dataset[name].attrs.update(
            units="degrees",
            convention="vector-to bearing clockwise from north",
            classification="DERIVED_ENVIRONMENTAL_FEATURE",
        )
    dataset.to_netcdf(path)
    return path
