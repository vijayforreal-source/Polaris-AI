import json
from datetime import UTC, datetime
from pathlib import Path

import xarray as xr

from backend.iceberg.usnic_registry import sha256_file

PRODUCT_ID = "GLOBAL_ANALYSISFORECAST_PHY_001_024"
DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
DATASET_VERSION = "202406"
VARIABLES = ("uo", "vo")
DEPTHS_METRES = (0.49402499198913574, 29.444730758666992, 92.3260726928711)
RAW_ROOT = Path(
    "data/raw/copernicus/ocean-currents/a76c/2026-01-02_to_2026-08-27"
)


def current_files(root: Path = RAW_ROOT) -> list[Path]:
    files = sorted(root.rglob("*.nc"))
    if len(files) != len(DEPTHS_METRES):
        raise FileNotFoundError(f"Expected three verified depth files, found {len(files)}")
    return files


def inspect_current_file(path: Path) -> dict[str, object]:
    with xr.open_dataset(path) as dataset:
        return {
            "dimensions": dict(dataset.sizes),
            "depth": float(dataset.depth.item()),
            "time_start": str(dataset.time.min().values),
            "time_end": str(dataset.time.max().values),
            "latitude_range": [float(dataset.latitude.min()), float(dataset.latitude.max())],
            "longitude_range": [float(dataset.longitude.min()), float(dataset.longitude.max())],
            "variables": {
                name: {
                    "standard_name": dataset[name].attrs["standard_name"],
                    "units": dataset[name].attrs["units"],
                }
                for name in VARIABLES
            },
            "source": dataset.attrs["source"],
        }


def write_current_sidecar(path: Path) -> Path:
    inspection = inspect_current_file(path)
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    payload = {
        "provider": "Copernicus Marine Service / Mercator Ocean International",
        "product_id": PRODUCT_ID,
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "classification": "ANALYSIS",
        "variables": list(VARIABLES),
        "depth_metres": inspection["depth"],
        "bbox": [-39.5, -61.5, -28.5, -51.08333206176758],
        "time_range": [inspection["time_start"], inspection["time_end"]],
        "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "source_metadata": inspection,
    }
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return sidecar
