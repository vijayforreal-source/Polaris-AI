import json
import math
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api import historical_transit as api
from backend.app.main import app
from backend.historical_transit.corridor import build_corridor, recency_score
from backend.historical_transit.models import (
    TrackPoint,
    Voyage,
    VoyageMetadata,
    assess,
    distance_km,
)
from backend.historical_transit.store import load_voyages, save_voyage
from scripts.import_historical_voyage_tracks import import_track, read_points

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture
def metadata():
    return VoyageMetadata(
        voyage_id="TEST_ONLY_001",
        vessel_name="Synthetic test vessel",
        origin="Test origin",
        destination="Test destination",
        source="Synthetic fixture - tests only",
        source_reference="tests/fixture",
        source_verified=True,
        verified_by="Test fixture",
    )


@pytest.fixture
def voyage(metadata):
    return Voyage(
        **metadata.model_dump(),
        points=[
            TrackPoint(
                timestamp_utc=NOW - timedelta(days=1, hours=1), latitude=-69.2, longitude=76.1
            ),
            TrackPoint(timestamp_utc=NOW - timedelta(days=1), latitude=-69.2, longitude=76.2),
            TrackPoint(timestamp_utc=NOW - timedelta(hours=23), latitude=-69.2, longitude=76.3),
        ],
    )


def test_distance_and_dateline():
    def point(lat, lon):
        return TrackPoint(timestamp_utc=NOW, latitude=lat, longitude=lon)

    assert distance_km(point(0, 0), point(0, 1)) == pytest.approx(111.19508, rel=1e-6)
    assert distance_km(point(0, 179), point(0, -179)) == pytest.approx(222.39016, rel=1e-6)
    assert distance_km(point(-90, 0), point(-90, 90)) < 1e-8


def test_valid_track_summary(voyage):
    result = assess(voyage, now=NOW)
    assert result["track_quality"] == "VERIFIED"
    assert result["point_count"] == 3
    assert result["duration_hours"] == 2
    assert result["distance_km"] > 0
    assert result["age_days"] == pytest.approx(23 / 24)
    assert result["renderable"]


@pytest.mark.parametrize(("field", "value"), [("latitude", -91), ("longitude", 181)])
def test_invalid_coordinates_are_preserved_and_rejected(voyage, field, value):
    setattr(voyage.points[1], field, value)
    result = assess(voyage, now=NOW)
    assert result["track_quality"] == "REJECTED"
    assert not result["renderable"]
    assert getattr(voyage.points[1], field) == value
    assert result["distance_km"] is None


def test_duplicate_and_disordered_timestamps_not_sorted_or_dropped(voyage):
    voyage.points[1].timestamp_utc = voyage.points[0].timestamp_utc
    assert "duplicate" in " ".join(assess(voyage, now=NOW)["quality_notes"])
    voyage.points.reverse()
    report = assess(voyage, now=NOW)
    assert report["track_quality"] == "REJECTED"
    assert report["point_count"] == 3
    assert "strictly increase" in " ".join(report["quality_notes"])


def test_jumps_future_and_minimum_count(voyage):
    voyage.points[1].latitude = -20
    assert assess(voyage, now=NOW)["track_quality"] == "REJECTED"
    voyage.points = voyage.points[:1]
    assert assess(voyage, now=NOW)["track_quality"] == "REJECTED"
    voyage.points[0].timestamp_utc = NOW + timedelta(days=1)
    assert "future timestamp" in " ".join(assess(voyage, now=NOW)["quality_notes"])


def test_reported_speed_and_unverified_source(voyage):
    voyage.points[0].speed_knots = 150
    assert assess(voyage, now=NOW)["track_quality"] == "LOW_CONFIDENCE"
    voyage.points[0].speed_knots = None
    voyage.source_verified = False
    assert not assess(voyage, now=NOW)["renderable"]
    assert build_corridor([voyage], now=NOW)["cells"] == []


def test_utc_timezone_is_required_and_normalized():
    with pytest.raises(ValidationError):
        TrackPoint(timestamp_utc="2026-01-01T00:00:00", latitude=0, longitude=0)
    p = TrackPoint(timestamp_utc="2026-01-01T05:30:00+05:30", latitude=0, longitude=0)
    assert p.timestamp_utc.hour == 0 and p.timestamp_utc.tzinfo == UTC
    with pytest.raises(ValidationError):
        TrackPoint(timestamp_utc=NOW, latitude=float("nan"), longitude=0)


def test_recency_score():
    assert recency_score(0) == 1
    assert recency_score(180) == pytest.approx(math.exp(-1))
    assert recency_score(20, 10) == pytest.approx(math.exp(-2))
    for age, tau in [(-1, 180), (1, 0), (1, float("nan"))]:
        with pytest.raises(ValueError):
            recency_score(age, tau)


def test_corridor_counts_passages_not_sampling_frequency(voyage):
    second = voyage.model_copy(deep=True, update={"voyage_id": "TEST_ONLY_002"})
    cell = build_corridor([voyage, second], now=NOW)["cells"][0]
    assert cell["transit_count"] == 2
    assert cell["unique_voyages"] == 2
    assert cell["recency_score"] == pytest.approx(math.exp(-(23 / 24) / 180))


def test_gaps_are_reported_and_excluded(voyage):
    voyage.points = [voyage.points[0], voyage.points[-1]]
    voyage.points[-1].timestamp_utc = voyage.points[0].timestamp_utc + timedelta(hours=8)
    report = assess(voyage, now=NOW)
    assert report["track_quality"] == "USABLE_WITH_GAPS"
    assert report["data_gaps"][0]["after_point"] == 0
    assert build_corridor([voyage], now=NOW)["cells"] == []


def test_csv_import_explicit_mapping_and_no_overwrite(tmp_path, metadata):
    source = tmp_path / "test.csv"
    source.write_text("when,lat,lon\n2025-01-01T00:00:00Z,-69,76\n2025-01-01T01:00:00Z,-69,76.1\n")
    mapping = {"timestamp_utc": "when", "latitude": "lat", "longitude": "lon"}
    path, report = import_track(source, metadata, mapping, tmp_path / "store")
    assert report["track_quality"] == "VERIFIED"
    assert json.loads(path.read_text())["vessel_name"] == "Synthetic test vessel"
    with pytest.raises(FileExistsError):
        import_track(source, metadata, mapping, tmp_path / "store")
    with pytest.raises(ValueError):
        read_points(source, {"timestamp_utc": "guessed"})


@pytest.mark.parametrize("geometry_type", ["Point", "LineString"])
def test_geojson_import(tmp_path, metadata, geometry_type):
    coords = [[76, -69], [76.1, -69]]
    times = ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"]
    if geometry_type == "Point":
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": c},
                    "properties": {"when": t},
                }
                for c, t in zip(coords, times, strict=True)
            ],
        }
    else:
        data = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"when": times},
        }
    source = tmp_path / "test.geojson"
    source.write_text(json.dumps(data))
    _, report = import_track(source, metadata, {"timestamp_utc": "when"}, tmp_path / "store")
    assert report["point_count"] == 2


def test_malformed_rows_quarantined_without_fake_fill(tmp_path, metadata):
    source = tmp_path / "test.csv"
    source.write_text("t,y,x\ninvalid,-69,76\n")
    root = tmp_path / "store"
    with pytest.raises(ValueError, match="preserved"):
        import_track(
            source, metadata, {"timestamp_utc": "t", "latitude": "y", "longitude": "x"}, root
        )
    rejected = json.loads((root / "rejected" / f"{metadata.voyage_id}.json").read_text())
    assert "invalid,-69,76" in rejected["raw_input"]
    records, errors = load_voyages(root)
    assert records == [] and len(errors) == 1


def test_metadata_does_not_guess_identifiers(metadata):
    assert metadata.imo is None and metadata.mmsi is None
    with pytest.raises(ValidationError):
        VoyageMetadata(**(metadata.model_dump() | {"verified_by": None}))
    with pytest.raises(ValidationError):
        VoyageMetadata(**(metadata.model_dump() | {"voyage_id": "../escape"}))


def test_api_empty_and_single_voyage(tmp_path, monkeypatch, voyage):
    monkeypatch.setattr(api, "load_voyages", lambda: load_voyages(tmp_path))
    client = TestClient(app)
    status = client.get("/api/historical-transit/status").json()
    assert not status["available"] and status["voyage_count"] == 0
    assert status["message"] == "No verified historical voyage tracks are currently loaded."
    assert client.get("/api/historical-transit/voyages").json()["voyages"] == []
    assert client.get("/api/historical-transit/corridor").json()["cells"] == []
    assert client.get("/api/historical-transit/voyage/missing").status_code == 404
    save_voyage(voyage, tmp_path)
    assert client.get("/api/historical-transit/status").json()["verified_voyage_count"] == 1
    summaries = client.get("/api/historical-transit/voyages?limit=1").json()
    assert "points" not in summaries["voyages"][0]
    response = client.get(f"/api/historical-transit/voyage/{voyage.voyage_id}")
    assert response.status_code == 200 and len(response.json()["points"]) == 3
    assert response.json()["source_classification"] == "OBSERVATION"
    assert client.get("/api/historical-transit/corridor?tau_days=0").status_code == 422
    assert client.get("/api/historical-transit/voyages?limit=101").status_code == 422


def test_invalid_storage_is_visible_as_error(tmp_path):
    (tmp_path / "broken.json").write_text("{broken")
    records, errors = load_voyages(tmp_path)
    assert not records and len(errors) == 1
    assert (tmp_path / "broken.json").read_text() == "{broken"


def test_corridor_dateline_stays_near_dateline(voyage):
    voyage.points = voyage.points[:2]
    voyage.points[0].longitude = 179.9
    voyage.points[1].longitude = -179.9
    cells = build_corridor([voyage], now=NOW)["cells"]
    assert len(cells) == 1
    assert cells[0]["bbox"][0] == -180


def test_rejected_voyage_remains_inspectable_in_api(tmp_path, monkeypatch, voyage):
    voyage.points[0].latitude = 100
    save_voyage(voyage, tmp_path)
    monkeypatch.setattr(api, "load_voyages", lambda: load_voyages(tmp_path))
    client = TestClient(app)
    status = client.get("/api/historical-transit/status").json()
    assert status["voyage_count"] == 1 and not status["available"]
    assert status["track_quality"]["REJECTED"] == 1
    record = client.get(f"/api/historical-transit/voyage/{voyage.voyage_id}").json()
    assert record["points"][0]["latitude"] == 100 and not record["renderable"]
    assert client.get("/api/historical-transit/corridor").json()["cells"] == []


def test_ambiguous_csv_mapping_is_rejected(tmp_path):
    source = tmp_path / "duplicate.csv"
    source.write_text("time,lat,lat\n2025-01-01T00:00:00Z,-69,76\n")
    with pytest.raises(ValueError, match="Duplicate CSV"):
        read_points(source, {"timestamp_utc": "time", "latitude": "lat", "longitude": "lat"})


def test_malformed_geojson_is_quarantined(tmp_path, metadata):
    source = tmp_path / "invalid.geojson"
    source.write_text('{"type":"FeatureCollection","features":[null]}')
    with pytest.raises(ValueError, match="preserved"):
        import_track(source, metadata, {"timestamp_utc": "when"}, tmp_path / "store")
    assert (tmp_path / "store/rejected" / f"{metadata.voyage_id}.json").is_file()
