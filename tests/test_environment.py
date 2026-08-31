from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from backend.environment.era5_wind import inspect_file, monthly_request, timestamp_coverage
from backend.environment.models import EnvironmentalForcingSample
from backend.environment.sampling import (
    interpolate_vector,
    normalize_longitude,
    vector_direction,
    vector_magnitude,
)
from backend.environment.track_forcing import build_interval_summaries
from backend.ingestion.models import ScientificClassification


def generic_grid() -> xr.Dataset:
    """Generic mathematical grid; it is not Antarctic environmental data."""
    times = np.array(["2026-01-01T00:00", "2026-01-01T06:00"], dtype="datetime64[m]")
    values = np.array(
        [
            [[[0.0, 1.0], [1.0, 2.0]]],
            [[[6.0, 7.0], [7.0, 8.0]]],
        ]
    )
    return xr.Dataset(
        {"uo": (("time", "depth", "latitude", "longitude"), values),
         "vo": (("time", "depth", "latitude", "longitude"), values * 2)},
        coords={
            "time": times,
            "depth": [1.0],
            "latitude": [0.0, 1.0],
            "longitude": [10.0, 11.0],
        },
    )


def test_classification_semantics_are_extended_without_changing_existing_values() -> None:
    assert ScientificClassification.OBSERVATION == "OBSERVATION"
    assert ScientificClassification.ANALYSIS == "ANALYSIS"
    assert ScientificClassification.REANALYSIS == "REANALYSIS"
    assert ScientificClassification.MODEL_PREDICTION == "MODEL_PREDICTION"


def test_explicit_spatial_and_temporal_interpolation() -> None:
    u_value, v_value, flags = interpolate_vector(
        generic_grid(), 0.5, 10.5, datetime(2026, 1, 1, 3, tzinfo=UTC)
    )
    assert u_value == pytest.approx(4.0)
    assert v_value == pytest.approx(8.0)
    assert flags == []


def test_descending_latitude_interpolation_preserves_data_alignment() -> None:
    descending = generic_grid().sortby("latitude", ascending=False)
    u_value, v_value, flags = interpolate_vector(
        descending, 0.5, 10.5, datetime(2026, 1, 1, 3, tzinfo=UTC)
    )
    assert u_value == pytest.approx(4.0)
    assert v_value == pytest.approx(8.0)
    assert flags == []


def test_exact_timestamp_uses_provider_value() -> None:
    u_value, _, _ = interpolate_vector(
        generic_grid(), 0.0, 10.0, datetime(2026, 1, 1, 0, tzinfo=UTC)
    )
    assert u_value == 0.0


def test_outside_grid_is_flagged_without_extrapolation() -> None:
    u_value, v_value, flags = interpolate_vector(
        generic_grid(), 5.0, 10.5, datetime(2026, 1, 1, 3, tzinfo=UTC)
    )
    assert u_value is None and v_value is None
    assert flags == ["OUTSIDE_SPATIAL_COVERAGE"]


def test_vector_math_and_longitude_wrap() -> None:
    assert vector_magnitude(3.0, 4.0) == 5.0
    assert vector_direction(1.0, 0.0) == 90.0
    assert normalize_longitude(181.0) == -179.0


def test_environment_model_preserves_classification_missing_data_and_provenance() -> None:
    sample = EnvironmentalForcingSample(
        valid_at=datetime(2026, 1, 1, tzinfo=UTC),
        iceberg_id="GENERIC-TEST",
        iceberg_latitude=0,
        iceberg_longitude=0,
        ocean_u=0.1,
        ocean_v=0.2,
        ocean_depth=1,
        source_ocean="generic test source",
        quality_flags=["WIND_UNAVAILABLE"],
        provenance={"fixture": "generic mathematical fixture"},
    )
    assert sample.classification_ocean is ScientificClassification.ANALYSIS
    assert sample.wind_u10 is None
    assert sample.provenance["fixture"] == "generic mathematical fixture"


def test_era5_request_uses_verified_reanalysis_variables() -> None:
    request = monthly_request(2026, 1)
    assert request["variable"] == [
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
    ]
    assert request["product_type"] == ["reanalysis"]


def test_timestamp_coverage_detects_duplicates_and_gaps() -> None:
    times = np.array(
        ["2026-01-01T00", "2026-01-01T01", "2026-01-01T01", "2026-01-01T03"],
        dtype="datetime64[h]",
    )
    result = timestamp_coverage(
        times, np.datetime64("2026-01-01T00"), np.datetime64("2026-01-01T04")
    )
    assert result["duplicate_count"] == 1
    assert result["missing_count"] == 1


def test_real_era5_metadata_and_descending_latitude() -> None:
    metadata = inspect_file(
        Path("data/raw/era5/wind/a76c/2026-01/era5_u10_v10_202601.nc")
    )
    assert metadata["time_coordinate"] == "valid_time"
    assert metadata["latitude_orientation"] == "descending"
    assert metadata["longitude_convention"] == "-180_to_180"
    assert metadata["units"] == {"u10": "m s**-1", "v10": "m s**-1"}


def test_real_local_interval_aggregation_preserves_provider_gap() -> None:
    summaries = build_interval_summaries()
    assert len(summaries) == 34
    surface = [item["ocean_by_depth"]["0.494025"] for item in summaries]
    assert sum(item["valid_samples"] for item in surface) == 982
    assert all(item["coverage_percentage"] == 100 for item in surface)
    assert summaries[-1]["wind"]["coverage_percentage"] < 100


def test_combined_processed_forcing_schema() -> None:
    with xr.open_dataset("data/processed/environment/a76c_forcing.nc") as dataset:
        assert {"ocean_u", "ocean_v", "wind_u10", "wind_v10"}.issubset(
            dataset.data_vars
        )
        assert dataset.attrs["wind_classification"] == "REANALYSIS"
        assert int(dataset.wind_u10.notnull().sum()) == 102
