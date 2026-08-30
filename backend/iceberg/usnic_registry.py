import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from backend.iceberg.models import IcebergObservation
from backend.ingestion.config import StudyRegion

PROVIDER = "U.S. National Ice Center (USNIC)"
SOURCE_PAGE = "https://usicecenter.gov/Products/AntarcIcebergs"
DOWNLOAD_URL = "https://usicecenter.gov/File/DownloadCurrent?pId=134"
TRACKING_CRITERIA = "20 square nautical miles or greater OR 10 nautical miles on longest axis"
EXPECTED_HEADERS = [
    "Iceberg",
    "Length (NM)",
    "Width (NM)",
    "Latitude",
    "Longitude",
    "Area (sqMI)",
    "Area (sqNM)",
    "Area (sqKM)",
    "Last Update",
]


@dataclass(frozen=True)
class RegistryParseResult:
    observations: list[IcebergObservation]
    rejected_rows: list[dict[str, str]]
    total_rows: int


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_coordinate(value: str, axis: Literal["latitude", "longitude"]) -> float:
    """Parse signed decimals or explicit degree/minute hemisphere coordinates."""
    text = value.strip().upper()
    limit = 90.0 if axis == "latitude" else 180.0
    allowed_hemispheres = {"N", "S"} if axis == "latitude" else {"E", "W"}

    try:
        coordinate = float(text)
    except ValueError:
        match = re.fullmatch(
            r"(\d{1,3})(?:°|\s)+\s*(\d{1,2}(?:\.\d+)?)\s*['′]?\s*([NSEW])",
            text,
        )
        if not match:
            raise ValueError(f"Malformed {axis} coordinate: {value!r}") from None
        degrees, minutes, hemisphere = match.groups()
        if hemisphere not in allowed_hemispheres:
            raise ValueError(f"Hemisphere {hemisphere} is invalid for {axis}") from None
        if float(minutes) >= 60:
            raise ValueError("Coordinate minutes must be less than 60") from None
        coordinate = float(degrees) + float(minutes) / 60
        if hemisphere in {"S", "W"}:
            coordinate *= -1

    if not -limit <= coordinate <= limit:
        raise ValueError(f"{axis} coordinate outside valid range: {coordinate}")
    return coordinate


def parse_provider_date(value: str) -> date:
    """Parse USNIC date precision without inventing a time or timezone."""
    return datetime.strptime(value.strip(), "%m/%d/%Y").date()


def _optional_float(value: str | None) -> float | None:
    text = (value or "").strip()
    return float(text) if text else None


def parse_registry(path: Path) -> RegistryParseResult:
    observations: list[IcebergObservation] = []
    rejected_rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            raise ValueError(f"Unexpected USNIC CSV schema: {reader.fieldnames!r}")
        rows = list(reader)

    for row in rows:
        try:
            observations.append(
                IcebergObservation(
                    iceberg_id=row["Iceberg"].strip(),
                    latitude=parse_coordinate(row["Latitude"], "latitude"),
                    longitude=parse_coordinate(row["Longitude"], "longitude"),
                    last_updated_on=parse_provider_date(row["Last Update"]),
                    provider_last_update=row["Last Update"].strip(),
                    length_nm=_optional_float(row["Length (NM)"]),
                    width_nm=_optional_float(row["Width (NM)"]),
                    area_sq_nm=_optional_float(row["Area (sqNM)"]),
                    provider=PROVIDER,
                    source=SOURCE_PAGE,
                    provenance={
                        "raw_file": path.as_posix(),
                        "provider_schema": "USNIC AntarcticIcebergs CSV",
                    },
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            rejected_rows.append({"iceberg_id": row.get("Iceberg", ""), "reason": str(error)})
    return RegistryParseResult(observations, rejected_rows, len(rows))


def in_study_region(observation: IcebergObservation, region: StudyRegion) -> bool:
    return (
        region.minimum_latitude <= observation.latitude <= region.maximum_latitude
        and region.minimum_longitude <= observation.longitude <= region.maximum_longitude
    )


def filter_study_region(
    observations: list[IcebergObservation], region: StudyRegion
) -> list[IcebergObservation]:
    return [observation for observation in observations if in_study_region(observation, region)]


def latest_registry_file(raw_root: Path = Path("data/raw/usnic/icebergs")) -> Path:
    candidates = sorted(raw_root.glob("*/*.csv"))
    if not candidates:
        raise FileNotFoundError("No verified local USNIC iceberg registry found")
    return candidates[-1]


def write_sidecar(
    path: Path,
    retrieved_at: datetime,
    provider_report_date: date | None,
) -> Path:
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    payload = {
        "provider": PROVIDER,
        "source_page": SOURCE_PAGE,
        "download_url": DOWNLOAD_URL,
        "retrieved_at": retrieved_at.isoformat().replace("+00:00", "Z"),
        "provider_report_date": provider_report_date.isoformat()
        if provider_report_date
        else None,
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "classification": "OBSERVATION",
    }
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return sidecar
