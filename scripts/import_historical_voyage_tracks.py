"""Import one explicitly identified voyage from CSV or timestamped GeoJSON."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from backend.historical_transit.models import Voyage, VoyageMetadata, assess
from backend.historical_transit.store import STORE, save_voyage

POINT_FIELDS = {"timestamp_utc", "latitude", "longitude", "speed_knots", "course_deg"}


def read_points(path: Path, field_map: dict[str, str]) -> list[dict]:
    if not isinstance(field_map, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and value.strip()
        for key, value in field_map.items()
    ):
        raise ValueError("Field mapping must be a JSON object of non-empty column/property names")
    if not set(field_map) <= POINT_FIELDS or "timestamp_utc" not in field_map:
        raise ValueError("Explicit canonical field mapping with timestamp_utc is required")
    if path.stat().st_size > 20_000_000:
        raise ValueError("Input exceeds 20 MB; split into explicit voyage legs before import")
    if path.suffix.lower() == ".csv":
        if not {"latitude", "longitude"} <= set(field_map):
            raise ValueError("CSV requires explicit latitude and longitude field mapping")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
                raise ValueError("Duplicate CSV column names are ambiguous")
            if not set(field_map.values()) <= set(reader.fieldnames or []):
                raise ValueError("Mapped CSV columns are missing")
            rows = list(reader)
        points = [
            {key: row[column] if row[column] != "" else None for key, column in field_map.items()}
            for row in rows
        ]
    elif path.suffix.lower() in {".geojson", ".json"}:
        if {"latitude", "longitude"} & set(field_map):
            raise ValueError("GeoJSON positions use geometry [longitude, latitude], not properties")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("GeoJSON root must be an object")
        features = data["features"] if data.get("type") == "FeatureCollection" else [data]
        if not isinstance(features, list):
            raise ValueError("GeoJSON features must be an array")
        points = []
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError("GeoJSON must contain Features")
            geometry = feature["geometry"]
            properties = feature.get("properties") or {}
            if not isinstance(geometry, dict) or not isinstance(properties, dict):
                raise ValueError("GeoJSON geometry and properties must be objects")
            if geometry["type"] == "Point":
                coords = [geometry["coordinates"]]
                values = {
                    key: [properties[column]]
                    for key, column in field_map.items()
                    if key not in {"latitude", "longitude"}
                }
            elif geometry["type"] == "LineString":
                coords = geometry["coordinates"]
                values = {
                    key: properties[column]
                    for key, column in field_map.items()
                    if key not in {"latitude", "longitude"}
                }
                if any(not isinstance(v, list) or len(v) != len(coords) for v in values.values()):
                    raise ValueError(
                        "LineString requires one mapped timestamp/value per coordinate"
                    )
            else:
                raise ValueError("Only Point and timestamped LineString GeoJSON are supported")
            for index, coordinate in enumerate(coords):
                if len(coordinate) < 2:
                    raise ValueError("GeoJSON position requires longitude and latitude")
                points.append(
                    {
                        "longitude": coordinate[0],
                        "latitude": coordinate[1],
                        **{key: value[index] for key, value in values.items()},
                    }
                )
    else:
        raise ValueError("Input format must be CSV or GeoJSON")
    if len(points) > 5000:
        raise ValueError("At most 5000 points per explicit voyage leg; no silent thinning")
    return points


def import_track(
    path: Path, metadata: VoyageMetadata, field_map: dict[str, str], output: Path = STORE
) -> tuple[Path, dict]:
    # Hash and keep the original external source reference; never infer vessel identity.
    if path.stat().st_size > 20_000_000:
        raise ValueError("Input exceeds the 20 MB import limit")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        points = read_points(path, field_map)
        voyage = Voyage(
            **metadata.model_dump(), points=points, raw_sha256=digest, imported_at=datetime.now(UTC)
        )
    except (ValueError, KeyError, TypeError, IndexError) as error:
        rejected = output / "rejected"
        rejected.mkdir(parents=True, exist_ok=True)
        report_path = rejected / f"{metadata.voyage_id}.json"
        # Preserve malformed source verbatim in quarantine; never expose it through map APIs.
        with report_path.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "metadata": metadata.model_dump(),
                    "raw_sha256": digest,
                    "track_quality": "REJECTED",
                    "reason": str(error),
                    "field_mapping": field_map,
                    "raw_input": path.read_text(encoding="utf-8-sig"),
                },
                handle,
                indent=2,
            )
        raise ValueError(
            f"Import rejected; source and diagnostics preserved at {report_path}"
        ) from error
    target = save_voyage(voyage, output)
    return target, assess(voyage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--metadata",
        type=Path,
        required=True,
        help="JSON matching VoyageMetadata; explicit source verification required",
    )
    parser.add_argument(
        "--field-map",
        type=Path,
        required=True,
        help="JSON mapping canonical point fields to CSV columns / GeoJSON properties",
    )
    parser.add_argument("--output", type=Path, default=STORE)
    args = parser.parse_args()
    metadata = VoyageMetadata.model_validate_json(args.metadata.read_text(encoding="utf-8"))
    mapping = json.loads(args.field_map.read_text(encoding="utf-8"))
    target, report = import_track(args.input, metadata, mapping, args.output)
    print(json.dumps({"stored": str(target), **report}, indent=2))
    if report["track_quality"] == "REJECTED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
