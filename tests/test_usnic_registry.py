import csv
from datetime import date
from pathlib import Path

import pytest

from backend.iceberg.usnic_registry import (
    EXPECTED_HEADERS,
    filter_study_region,
    parse_coordinate,
    parse_provider_date,
    parse_registry,
)
from backend.ingestion.config import BHARATI_PRYDZ_BAY
from backend.ingestion.models import ScientificClassification


def test_coordinate_hemisphere_conversion() -> None:
    assert parse_coordinate("53° 44' S", "latitude") == pytest.approx(-53.733333)
    assert parse_coordinate("53° 44' N", "latitude") == pytest.approx(53.733333)
    assert parse_coordinate("29° 30' W", "longitude") == -29.5
    assert parse_coordinate("29° 30' E", "longitude") == 29.5
    assert parse_coordinate("-69.44", "latitude") == -69.44


@pytest.mark.parametrize(
    ("value", "axis"),
    [("91", "latitude"), ("181", "longitude"), ("10° 70' S", "latitude"), ("bad", "longitude")],
)
def test_coordinate_validation(value: str, axis: str) -> None:
    with pytest.raises(ValueError):
        parse_coordinate(value, axis)  # type: ignore[arg-type]


def test_date_parsing_preserves_date_precision() -> None:
    assert parse_provider_date("08/27/2026") == date(2026, 8, 27)
    with pytest.raises(ValueError):
        parse_provider_date("2026-08-27 00:00Z")


def test_structurally_representative_schema_fixture(tmp_path: Path) -> None:
    """Generic fixture validates provider structure; it is not an Antarctic observation."""
    fixture = tmp_path / "provider-structure.csv"
    with fixture.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_HEADERS)
        writer.writeheader()
        writer.writerow(
            {
                "Iceberg": "TEST-STRUCTURE",
                "Length (NM)": "",
                "Width (NM)": "",
                "Latitude": "10.5",
                "Longitude": "20.25",
                "Area (sqMI)": "",
                "Area (sqNM)": "",
                "Area (sqKM)": "",
                "Last Update": "08/27/2026",
            }
        )
    result = parse_registry(fixture)
    record = result.observations[0]
    assert result.total_rows == 1
    assert result.rejected_rows == []
    assert record.length_nm is None
    assert record.width_nm is None
    assert record.area_sq_nm is None
    assert record.classification is ScientificClassification.OBSERVATION


def test_real_current_registry_and_region_filter() -> None:
    path = Path(
        "data/raw/usnic/icebergs/2026-08-30/AntarcticIcebergs_20260827.csv"
    )
    result = parse_registry(path)
    regional = filter_study_region(result.observations, BHARATI_PRYDZ_BAY)
    assert result.total_rows == 33
    assert len(result.observations) == 33
    assert len(result.rejected_rows) == 0
    assert [record.iceberg_id for record in regional] == [
        "D15A",
        "D15B",
        "D15C",
        "D15D",
        "D23",
        "D34",
    ]


def test_zero_in_region_is_valid() -> None:
    result = parse_registry(
        Path("data/raw/usnic/icebergs/2026-08-30/AntarcticIcebergs_20260827.csv")
    )
    empty_region = BHARATI_PRYDZ_BAY.model_copy(
        update={
            "minimum_longitude": 0,
            "maximum_longitude": 1,
            "minimum_latitude": -80,
            "maximum_latitude": -79,
            "bharati_latitude": -79.5,
            "bharati_longitude": 0.5,
        }
    )
    assert filter_study_region(result.observations, empty_region) == []

