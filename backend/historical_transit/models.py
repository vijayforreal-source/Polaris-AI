import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class TrackQuality(StrEnum):
    VERIFIED = "VERIFIED"
    USABLE_WITH_GAPS = "USABLE_WITH_GAPS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    REJECTED = "REJECTED"


class TrackPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    timestamp_utc: AwareDatetime
    # Out-of-range coordinates are preserved and flagged by assess(), never mapped.
    latitude: float
    longitude: float
    speed_knots: float | None = None
    course_deg: float | None = None

    @field_validator("timestamp_utc")
    @classmethod
    def utc_timestamp(cls, value):
        return value.astimezone(UTC)


class VoyageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    voyage_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
    vessel_name: str = Field(min_length=1, max_length=120)
    imo: str | None = Field(default=None, pattern=r"^\d{7}$")
    mmsi: str | None = Field(default=None, pattern=r"^\d{9}$")
    expedition_id: str | None = Field(default=None, max_length=120)
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=200)
    source_classification: Literal["OBSERVATION"] = "OBSERVATION"
    source_reference: str = Field(min_length=1, max_length=1000)
    source_verified: bool = False
    verified_by: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def explicit_verification(self):
        if self.source_verified and not self.verified_by:
            raise ValueError("source_verified requires an explicit verified_by attestation")
        return self


class Voyage(VoyageMetadata):
    points: list[TrackPoint] = Field(max_length=5000)
    raw_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    imported_at: AwareDatetime | None = None


class ValidationPolicy(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    maximum_speed_knots: float = Field(default=40, gt=0, le=100)
    gap_hours: float = Field(default=6, gt=0, le=168)


def distance_km(a: TrackPoint, b: TrackPoint) -> float:
    """Spherical great-circle distance; not sailed distance between sparse fixes."""
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def assess(
    voyage: Voyage, *, now: datetime | None = None, policy: ValidationPolicy | None = None
) -> dict:
    now = now or datetime.now(UTC)
    policy = policy or ValidationPolicy()
    notes, gaps = [], []
    rejected = len(voyage.points) < 2
    low_confidence = not voyage.source_verified
    if rejected:
        notes.append("At least two timestamped positions are required.")
    if low_confidence:
        notes.append("Source has not been explicitly verified; excluded from map and corridor.")
    valid_coordinates = True
    seen = set()
    total_distance = 0.0
    for index, point in enumerate(voyage.points):
        if not -90 <= point.latitude <= 90 or not -180 <= point.longitude <= 180:
            notes.append(f"Point {index}: coordinate outside valid range.")
            rejected = True
            valid_coordinates = False
        if point.timestamp_utc in seen:
            notes.append(f"Point {index}: duplicate timestamp.")
            rejected = True
        seen.add(point.timestamp_utc)
        if point.timestamp_utc > now:
            notes.append(f"Point {index}: future timestamp is not historical evidence.")
            rejected = True
        if (
            point.speed_knots is not None
            and not 0 <= point.speed_knots <= policy.maximum_speed_knots
        ):
            notes.append(f"Point {index}: reported speed outside configured plausibility range.")
            low_confidence = True
        if point.course_deg is not None and not 0 <= point.course_deg < 360:
            notes.append(f"Point {index}: course must be in [0, 360).")
            low_confidence = True
    for index, (a, b) in enumerate(zip(voyage.points, voyage.points[1:], strict=False)):
        hours = (b.timestamp_utc - a.timestamp_utc).total_seconds() / 3600
        if hours <= 0:
            notes.append(
                f"Segment {index}: timestamps must strictly increase; input order preserved."
            )
            rejected = True
            continue
        if valid_coordinates:
            length = distance_km(a, b)
            total_distance += length
            if length / hours / 1.852 > policy.maximum_speed_knots:
                notes.append(f"Segment {index}: implausible position jump / speed.")
                rejected = True
        if hours > policy.gap_hours:
            gaps.append({"after_point": index, "duration_hours": hours})
    quality = (
        TrackQuality.REJECTED
        if rejected
        else TrackQuality.LOW_CONFIDENCE
        if low_confidence
        else TrackQuality.USABLE_WITH_GAPS
        if gaps
        else TrackQuality.VERIFIED
    )
    if gaps:
        notes.append("Long gaps are not connected on the map or counted in corridor evidence.")
    times = [point.timestamp_utc for point in voyage.points]
    start, end = (min(times), max(times)) if times else (None, None)
    return {
        "track_quality": quality,
        "point_count": len(voyage.points),
        "distance_km": round(total_distance, 3) if not rejected else None,
        "distance_semantics": "Sum of great-circle distances between fixes; sparse-track estimate.",
        "duration_hours": (end - start).total_seconds() / 3600 if times else None,
        "start_time": start.isoformat() if start else None,
        "end_time": end.isoformat() if end else None,
        "last_transit_time": end.isoformat() if end else None,
        "age_days": max(0, (now - end).total_seconds() / 86400) if end else None,
        "data_gaps": gaps,
        "quality_notes": notes,
        "renderable": quality in (TrackQuality.VERIFIED, TrackQuality.USABLE_WITH_GAPS),
        "validation_policy": policy.model_dump(),
    }


def summary(voyage: Voyage, *, now: datetime | None = None) -> dict:
    return voyage.model_dump(mode="json", exclude={"points"}) | assess(voyage, now=now)
