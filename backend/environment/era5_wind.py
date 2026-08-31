import calendar
import json
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import xarray as xr

from backend.iceberg.usnic_registry import sha256_file

DATASET_ID = "reanalysis-era5-single-levels"
VARIABLES = ("10m_u_component_of_wind", "10m_v_component_of_wind")
RAW_ROOT = Path("data/raw/era5/wind/a76c")
BBOX = (-51.08333206176758, -39.5, -61.5, -28.5)


def cds_credentials_available(home: Path | None = None) -> bool:
    base = home if home is not None else Path.home()
    return (base / ".cdsapirc").is_file()


def monthly_request(year: int, month: int) -> dict[str, object]:
    """Return a credential-free, deterministic CDS request description."""
    return {
        "product_type": ["reanalysis"],
        "variable": list(VARIABLES),
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": [
            f"{day:02d}"
            for day in range(
                2 if (year, month) == (2026, 1) else 1,
                (27 if (year, month) == (2026, 8) else calendar.monthrange(year, month)[1])
                + 1,
            )
        ],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": list(BBOX),
    }


def monthly_target(year: int, month: int, root: Path = RAW_ROOT) -> Path:
    return root / f"{year}-{month:02d}" / f"era5_u10_v10_{year}{month:02d}.nc"


def download_month(year: int, month: int, root: Path = RAW_ROOT) -> Path:
    """Acquire one official ERA5 month; credentials remain owned by cdsapi."""
    import cdsapi

    target = monthly_target(year, month, root)
    sidecar = target.with_suffix(target.suffix + ".metadata.json")
    if target.is_file() and sidecar.is_file():
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if metadata.get("sha256") == sha256_file(target):
            return target
        raise ValueError(f"Existing ERA5 checksum mismatch: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    cdsapi.Client(quiet=True, progress=False).retrieve(
        DATASET_ID, monthly_request(year, month), str(target)
    )
    return target


def write_sidecar(path: Path) -> Path:
    year = int(path.parent.name[:4])
    month = int(path.parent.name[5:7])
    request = monthly_request(year, month)
    inspection = inspect_file(path)
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    payload = {
        "provider": "Copernicus Climate Change Service / ECMWF",
        "dataset_id": DATASET_ID,
        "classification": "REANALYSIS",
        "variables": list(VARIABLES),
        "requested_bbox_north_west_south_east": list(BBOX),
        "requested_days": request["day"],
        "requested_hours": request["time"],
        "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "actual_file_metadata": inspection,
    }
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return sidecar


def expected_months() -> list[date]:
    return [date(2026, month, 1) for month in range(1, 9)]


def wind_files(root: Path = RAW_ROOT) -> list[Path]:
    files = sorted(root.glob("*/*.nc"))
    if len(files) != 8:
        raise FileNotFoundError(f"Expected eight ERA5 monthly files, found {len(files)}")
    return files


def inspect_file(path: Path) -> dict[str, object]:
    with xr.open_dataset(path) as dataset:
        if not {"u10", "v10"}.issubset(dataset.data_vars):
            raise ValueError(f"ERA5 wind variables missing from {path}")
        time_name = "valid_time" if "valid_time" in dataset.coords else "time"
        times = dataset[time_name].values
        if len(times) == 0 or len(np.unique(times)) != len(times):
            raise ValueError(f"Empty or duplicate ERA5 timestamps in {path}")
        if not np.all(np.diff(times) == np.timedelta64(1, "h")):
            raise ValueError(f"Non-hourly ERA5 timestamps in {path}")
        units = {name: dataset[name].attrs.get("units") for name in ("u10", "v10")}
        if not all(str(unit).replace("**", "^") in {"m s^-1", "m s-1"} for unit in units.values()):
            raise ValueError(f"Unexpected ERA5 wind units: {units}")
        return {
            "dimensions": dict(dataset.sizes),
            "coordinate_names": list(dataset.coords),
            "time_coordinate": time_name,
            "time_start": str(times[0]),
            "time_end": str(times[-1]),
            "latitude_orientation": (
                "descending"
                if dataset.latitude.values[0] > dataset.latitude.values[-1]
                else "ascending"
            ),
            "latitude_range": [float(dataset.latitude.min()), float(dataset.latitude.max())],
            "longitude_range": [float(dataset.longitude.min()), float(dataset.longitude.max())],
            "longitude_convention": "-180_to_180",
            "grid_resolution_degrees": [
                abs(float(dataset.latitude[1] - dataset.latitude[0])),
                abs(float(dataset.longitude[1] - dataset.longitude[0])),
            ],
            "units": units,
            "missing_counts": {
                name: int(dataset[name].isnull().sum()) for name in ("u10", "v10")
            },
        }


def validate_complete_coverage(files: list[Path] | None = None) -> dict[str, object]:
    paths = files or wind_files()
    arrays: list[np.ndarray] = []
    for path in paths:
        with xr.open_dataset(path) as dataset:
            time_name = "valid_time" if "valid_time" in dataset.coords else "time"
            arrays.append(dataset[time_name].values)
    all_times = np.concatenate(arrays)
    return timestamp_coverage(
        all_times, np.datetime64("2026-01-02T00:00"), np.datetime64("2026-08-28T00:00")
    )


def timestamp_coverage(
    all_times: np.ndarray, start: np.datetime64, end_exclusive: np.datetime64
) -> dict[str, object]:
    unique_times = np.unique(all_times)
    expected = np.arange(start, end_exclusive, np.timedelta64(1, "h"))
    missing = np.setdiff1d(expected, unique_times)
    extras = np.setdiff1d(unique_times, expected)
    return {
        "expected_count": len(expected),
        "actual_count": len(all_times),
        "unique_count": len(unique_times),
        "duplicate_count": len(all_times) - len(unique_times),
        "missing_count": len(missing),
        "extra_count": len(extras),
        "start": str(unique_times[0]),
        "end": str(unique_times[-1]),
    }


def load_wind_dataset(files: list[Path] | None = None) -> xr.Dataset:
    datasets = [xr.open_dataset(path) for path in (files or wind_files())]
    time_name = "valid_time" if "valid_time" in datasets[0].coords else "time"
    combined = xr.concat(datasets, dim=time_name).sortby(time_name)
    if time_name != "time":
        combined = combined.rename({time_name: "time"})
    return combined
