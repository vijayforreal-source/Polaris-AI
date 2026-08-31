from datetime import UTC, datetime

import numpy as np
import pytest
import xarray as xr

from backend.environment.era5_wind import monthly_request
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


def test_real_local_interval_aggregation_is_complete() -> None:
    summaries = build_interval_summaries()
    assert len(summaries) == 34
    assert sum(item["valid_ocean_samples"] for item in summaries) == 982
    assert all(item["coverage_percentage"] == 100 for item in summaries)
