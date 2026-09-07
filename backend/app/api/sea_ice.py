import json
from datetime import date as Date
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from fastapi import APIRouter, HTTPException

from backend.forecasting.sea_ice import operational
from backend.ingestion.config import BHARATI_PRYDZ_BAY
from backend.ingestion.copernicus_sea_ice import SIC_VARIABLE, inspect_netcdf

router = APIRouter(prefix="/api/sea-ice", tags=["sea-ice"])

RAW_ROOT = Path("data/raw/copernicus/osi_saf_sic_south")


def latest_observation_file(raw_root: Path = RAW_ROOT) -> Path:
    candidates = sorted(raw_root.glob("*/*.nc"))
    if not candidates:
        raise FileNotFoundError("No verified local Copernicus sea-ice observation found")
    return candidates[-1]


def load_latest_observation() -> tuple[dict[str, Any], dict[str, Any]]:
    path = latest_observation_file()
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    if not sidecar.exists():
        raise FileNotFoundError(f"Observation sidecar is missing: {sidecar}")
    return _load_observation(path, path.stat().st_mtime_ns, sidecar.stat().st_mtime_ns)


@lru_cache(maxsize=2)
def _load_observation(path: Path, modified: int, sidecar_modified: int):
    with operational.NETCDF_LOCK:
        return _read_observation(path)


def _read_observation(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sidecar = path.with_suffix(path.suffix + ".metadata.json")

    registration = json.loads(sidecar.read_text(encoding="utf-8"))
    inspection = inspect_netcdf(path)
    with xr.open_dataset(path, decode_cf=True, mask_and_scale=True) as dataset:
        latitudes = np.asarray(dataset["latitude"].values, dtype=float)
        longitudes = np.asarray(dataset["longitude"].values, dtype=float)
        values = np.asarray(dataset[SIC_VARIABLE].isel(time=0).values, dtype=float)

    concentration = [
        [float(value) if np.isfinite(value) else None for value in row] for row in values
    ]
    bbox = {
        "minimum_longitude": float(longitudes.min()),
        "maximum_longitude": float(longitudes.max()),
        "minimum_latitude": float(latitudes.min()),
        "maximum_latitude": float(latitudes.max()),
    }
    metadata = {
        "classification": registration["classification"],
        "provider": registration["source"],
        "product_id": registration["product_id"],
        "dataset_id": registration["dataset_id"],
        "variable": registration["variable"],
        "standard_name": "sea_ice_area_fraction",
        "units": registration["units"],
        "observation_time": registration["observed_at"],
        "bbox": bbox,
        "grid_shape": inspection["shape"],
        "valid_min": inspection["valid_min"],
        "valid_max": inspection["valid_max"],
        "valid_count": inspection["valid_count"],
        "missing_count": inspection["missing_count"],
        "source_processing_note": (
            "Provider-generated regular 0.1 degree regional subset; ice_conc records "
            "regrid_method=bilinear. This is not the untouched original 10 km grid."
        ),
        "native_grid": registration["native_crs"],
        "canonical_crs": registration["canonical_crs"],
        "study_area": "Bharati / Prydz Bay",
        "bharati": {
            "name": "BHARATI",
            "country": "India",
            "latitude": BHARATI_PRYDZ_BAY.bharati_latitude,
            "longitude": BHARATI_PRYDZ_BAY.bharati_longitude,
        },
    }
    grid = {
        "classification": registration["classification"],
        "variable": registration["variable"],
        "units": registration["units"],
        "observation_time": registration["observed_at"],
        "latitude": latitudes.tolist(),
        "longitude": longitudes.tolist(),
        "concentration": concentration,
        "missing_value": None,
        "missing_semantics": "null means missing/no-data; it does not mean 0% ice",
    }
    return metadata, grid


def _observation_or_503(index: int) -> dict[str, Any]:
    try:
        return load_latest_observation()[index]
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/latest/metadata")
async def latest_metadata() -> dict[str, Any]:
    return _observation_or_503(0)


@router.get("/latest/grid")
async def latest_grid() -> dict[str, Any]:
    return _observation_or_503(1)


@router.get("/forecast/status")
def forecast_status() -> dict:
    return operational.status()


@router.get("/forecast/latest")
def forecast_latest() -> dict:
    return operational.forecast()


@router.get("/forecast/historical")
def forecast_historical(date: Date) -> dict:
    try:
        return operational.forecast(date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/forecast/results")
def forecast_results() -> dict:
    return operational.results()
