import csv
from datetime import date
from pathlib import Path

import pytest

from backend.iceberg.baseline import (
    constant_velocity_baseline,
    persistence_baseline,
    rolling_origin_validation,
)
from backend.iceberg.history import load_history, registry_date_from_filename
from backend.iceberg.models import IcebergTrackPoint
from backend.iceberg.motion import (
    MotionThresholds,
    analyze_track,
    geodesic_inverse,
    motion_steps,
)
from backend.iceberg.usnic_registry import EXPECTED_HEADERS


def generic_point(day: int, latitude: float, longitude: float) -> IcebergTrackPoint:
    """Mathematical fixture only; it is not an Antarctic iceberg observation."""
    return IcebergTrackPoint(
        iceberg_id="GENERIC-TEST",
        latitude=latitude,
        longitude=longitude,
        observation_date=date(2026, 1, day),
        registry_dates=[date(2026, 1, day)],
        original_last_update=f"01/{day:02d}/2026",
        source_files=[f"generic-{day}.csv"],
        provider="Generic test fixture",
        provenance={"purpose": "geodesic unit test"},
    )


def write_generic_archive(path: Path, day: int, latitude: float, longitude: float) -> None:
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_HEADERS)
        writer.writeheader()
        writer.writerow(
            {
                "Iceberg": "GENERIC-TEST",
                "Length (NM)": "",
                "Width (NM)": "",
                "Latitude": latitude,
                "Longitude": longitude,
                "Area (sqMI)": "",
                "Area (sqNM)": "",
                "Area (sqKM)": "",
                "Last Update": f"01/{day:02d}/2026",
            }
        )


def test_archive_normalization_sorting_and_duplicate_provenance(tmp_path: Path) -> None:
    later = tmp_path / "2026-01-09" / "AntarcticIcebergs_20260109.csv"
    earlier = tmp_path / "2026-01-02" / "AntarcticIcebergs_20260102.csv"
    write_generic_archive(later, 2, 10.0, 20.0)
    write_generic_archive(earlier, 2, 10.0, 20.0)
    result = load_history([later, earlier])
    assert result.raw_record_count == 2
    assert len(result.points) == 1
    assert result.points[0].registry_dates == [date(2026, 1, 2), date(2026, 1, 9)]
    assert len(result.points[0].source_files) == 2
    assert registry_date_from_filename(earlier) == date(2026, 1, 2)


def test_geodesic_distance_bearing_and_elapsed_time() -> None:
    distance_km, bearing = geodesic_inverse(0.0, 0.0, 0.0, 1.0)
    assert distance_km == pytest.approx(111.319, rel=1e-3)
    assert bearing == pytest.approx(90.0)
    step = motion_steps([generic_point(1, 0.0, 0.0), generic_point(2, 0.0, 1.0)])[0]
    assert step.elapsed_hours == 24
    assert step.distance_km == pytest.approx(distance_km)


def test_duplicate_positions_are_not_interpreted_as_displacement() -> None:
    metrics = analyze_track(
        [generic_point(1, 10.0, 20.0), generic_point(2, 10.0, 20.0)]
    )
    assert metrics.unique_position_count == 1
    assert metrics.cumulative_displacement_km == 0
    assert metrics.classification == "APPARENTLY STATIONARY"


def test_persistence_and_constant_velocity_are_time_ordered() -> None:
    track = [
        generic_point(1, 0.0, 0.0),
        generic_point(2, 0.0, 1.0),
        generic_point(3, 0.0, 2.0),
    ]
    persistence = persistence_baseline(track[1], track[2])
    velocity = constant_velocity_baseline(*track)
    assert persistence.error_km > 100
    assert velocity.error_km == pytest.approx(0, abs=1e-8)
    assert velocity.classification == "MODEL_PREDICTION"
    assert len(rolling_origin_validation(track)) == 1
    with pytest.raises(ValueError):
        constant_velocity_baseline(track[1], track[0], track[2])


def test_malformed_jump_is_flagged() -> None:
    limits = MotionThresholds(malformed_speed_knots=1.0)
    metrics = analyze_track(
        [generic_point(1, 0.0, 0.0), generic_point(2, 0.0, 20.0)],
        thresholds=limits,
    )
    assert metrics.malformed_jump_count == 1
    assert metrics.candidate is False
