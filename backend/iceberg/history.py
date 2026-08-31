import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from backend.iceberg.models import IcebergObservation, IcebergTrackPoint
from backend.iceberg.usnic_registry import PROVIDER, parse_registry, sha256_file

ARCHIVE_PAGE = (
    "https://usicecenter.gov/Products/ArchiveSearchMulti?"
    "linkChange=ant-three&table=IcebergProducts"
)
ARCHIVE_ROOT = Path("data/raw/usnic/icebergs/archive")
_FILENAME_DATE = re.compile(r"AntarcticIcebergs_(\d{4})(\d{2})(\d{2})\.csv$")


@dataclass(frozen=True)
class HistoricalRegistry:
    points: list[IcebergTrackPoint]
    raw_record_count: int
    rejected_record_count: int
    archive_files: list[Path]


def registry_date_from_filename(path: Path) -> date:
    match = _FILENAME_DATE.fullmatch(path.name)
    if not match:
        raise ValueError(f"Unrecognized USNIC archive filename: {path.name}")
    return date(*(int(part) for part in match.groups()))


def archive_download_url(registry_date: date) -> str:
    return (
        "https://usicecenter.gov/File/DownloadArchive?prd=134"
        f"{registry_date:%m%d%Y}"
    )


def discover_archive_files(root: Path = ARCHIVE_ROOT) -> list[Path]:
    return sorted(root.glob("*/*.csv"), key=registry_date_from_filename)


def write_archive_sidecar(path: Path) -> Path:
    report_date = registry_date_from_filename(path)
    retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    payload = {
        "provider": PROVIDER,
        "source_page": ARCHIVE_PAGE,
        "download_url": archive_download_url(report_date),
        "retrieved_at": retrieved_at.isoformat().replace("+00:00", "Z"),
        "provider_report_date": report_date.isoformat(),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "classification": "OBSERVATION",
    }
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return sidecar


def load_history(paths: list[Path] | None = None) -> HistoricalRegistry:
    files = paths if paths is not None else discover_archive_files()
    grouped: dict[
        tuple[str, date, float, float], list[tuple[date, Path, IcebergObservation]]
    ] = (
        defaultdict(list)
    )
    raw_count = 0
    rejected_count = 0

    for path in files:
        registry_date = registry_date_from_filename(path)
        parsed = parse_registry(path)
        raw_count += parsed.total_rows
        rejected_count += len(parsed.rejected_rows)
        for item in parsed.observations:
            key = (item.iceberg_id, item.last_updated_on, item.latitude, item.longitude)
            grouped[key].append((registry_date, path, item))

    points: list[IcebergTrackPoint] = []
    for observations in grouped.values():
        registry_dates = sorted({entry[0] for entry in observations})
        source_files = sorted({entry[1].as_posix() for entry in observations})
        item = observations[-1][2]
        points.append(
            IcebergTrackPoint(
                iceberg_id=item.iceberg_id,
                latitude=item.latitude,
                longitude=item.longitude,
                observation_date=item.last_updated_on,
                registry_dates=registry_dates,
                original_last_update=item.provider_last_update,
                length_nm=item.length_nm,
                width_nm=item.width_nm,
                area_sq_nm=item.area_sq_nm,
                source_files=source_files,
                provider=PROVIDER,
                provenance={
                    "archive_page": ARCHIVE_PAGE,
                    "date_semantics": "USNIC Last Update is the position observation date",
                },
            )
        )
    points.sort(key=lambda point: (point.iceberg_id, point.observation_date))
    return HistoricalRegistry(points, raw_count, rejected_count, files)


def tracks_by_iceberg(points: list[IcebergTrackPoint]) -> dict[str, list[IcebergTrackPoint]]:
    tracks: dict[str, list[IcebergTrackPoint]] = defaultdict(list)
    for point in points:
        tracks[point.iceberg_id].append(point)
    return {
        iceberg_id: sorted(track, key=lambda point: point.observation_date)
        for iceberg_id, track in tracks.items()
    }
