import json
from datetime import UTC, datetime
from pathlib import Path

import xarray as xr

from backend.forecasting.sea_ice.dataset import (
    CDR_DATASET_ID,
    DATASET_VERSION,
    ICDR_DATASET_ID,
    PRODUCT_ID,
    sha256_file,
    source_family,
)

SOURCE = "Copernicus Marine Service / EUMETSAT OSI SAF"
VARIABLES = ("ice_conc", "total_standard_uncertainty", "status_flag")


def build_historical_subset_arguments(
    dataset_id: str, start_date: str, end_date: str
) -> list[str]:
    if dataset_id not in {CDR_DATASET_ID, ICDR_DATASET_ID}:
        raise ValueError("dataset_id is not a verified southern AMSR CDR/ICDR dataset")
    arguments = [
        "--dataset-id",
        dataset_id,
        "--dataset-version",
        DATASET_VERSION,
    ]
    for variable in VARIABLES:
        arguments.extend(["--variable", variable])
    arguments.extend(
        [
            "--minimum-longitude",
            "67.0",
            "--maximum-longitude",
            "87.0",
            "--minimum-latitude",
            "-73.5",
            "--maximum-latitude",
            "-63.0",
            "--start-datetime",
            start_date,
            "--end-datetime",
            end_date,
            "--file-format",
            "netcdf",
        ]
    )
    return arguments


def raw_source_metadata(path: Path) -> dict[str, object]:
    with xr.open_dataset(path) as dataset:
        return {
            "provider": SOURCE,
            "product_id": PRODUCT_ID,
            "dataset_id": CDR_DATASET_ID
            if source_family(path) == "CDR"
            else ICDR_DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "family": source_family(path),
            "classification": "OBSERVATION",
            "variables": list(dataset.data_vars),
            "source_period_start": str(dataset.time.values[0]),
            "source_period_end": str(dataset.time.values[-1]),
            "actual_grid": {
                "coordinate_names": ["latitude", "longitude"],
                "latitude_count": dataset.sizes["latitude"],
                "longitude_count": dataset.sizes["longitude"],
                "latitude_min": float(dataset.latitude.min()),
                "latitude_max": float(dataset.latitude.max()),
                "longitude_min": float(dataset.longitude.min()),
                "longitude_max": float(dataset.longitude.max()),
                "resolution_degrees": 0.2,
                "processing_note": "Copernicus subset service; ice fields bilinearly regridded",
            },
            "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }


def write_raw_sidecar(path: Path) -> Path:
    sidecar = path.with_suffix(".nc.metadata.json")
    if sidecar.exists():
        existing = json.loads(sidecar.read_text(encoding="utf-8"))
        if existing.get("sha256") != sha256_file(path):
            raise ValueError(f"Existing sidecar checksum mismatch for {path}")
        return sidecar
    sidecar.write_text(
        json.dumps(raw_source_metadata(path), indent=2) + "\n", encoding="utf-8"
    )
    return sidecar
