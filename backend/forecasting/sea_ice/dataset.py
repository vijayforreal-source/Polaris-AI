import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from backend.ingestion.models import ScientificClassification

from .models import BHARATI_FORECAST_DOMAIN

PRODUCT_ID = "SEAICE_GLO_SEAICE_L4_REP_OBSERVATIONS_011_009"
CDR_DATASET_ID = "osisaf_obs-si_glo_phy_sic-south_my_amsr_cdr_P1D-m"
ICDR_DATASET_ID = "osisaf_obs-si_glo_phy_sic-south_my_amsr_icdr_P1D-m"
DATASET_VERSION = "202603"
RAW_ROOT = Path("data/raw/copernicus/sea-ice-history")
PROCESSED_CUBE = Path("data/processed/forecasting/sea_ice_bharati_daily.nc")
PROCESSED_SIDECAR = PROCESSED_CUBE.with_suffix(".metadata.json")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_raw_files(root: Path = RAW_ROOT) -> list[Path]:
    return sorted(root.rglob("*.nc"))


def source_family(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "cdr" in parts:
        return "CDR"
    if "icdr" in parts:
        return "ICDR"
    raise ValueError(f"Cannot determine CDR/ICDR family for {path}")


def inspect_source_consistency(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("No historical sea-ice files were found")
    reference_coordinates: tuple[np.ndarray, np.ndarray] | None = None
    schemas: dict[str, dict[str, Any]] = {}
    first_times: list[np.datetime64] = []
    last_times: list[np.datetime64] = []
    for path in paths:
        with xr.open_dataset(path) as dataset:
            required = {"ice_conc", "total_standard_uncertainty", "status_flag"}
            if not required.issubset(dataset.data_vars):
                raise ValueError(f"Missing provider fields in {path}")
            coordinates = (dataset.latitude.values, dataset.longitude.values)
            if reference_coordinates is None:
                reference_coordinates = tuple(value.copy() for value in coordinates)
            elif not all(
                np.array_equal(current, expected)
                for current, expected in zip(coordinates, reference_coordinates, strict=True)
            ):
                raise ValueError(f"Coordinate mismatch in {path}")
            family = source_family(path)
            schemas.setdefault(
                family,
                {
                    "variables": list(dataset.data_vars),
                    "ice_units": dataset.ice_conc.attrs.get("units"),
                    "uncertainty_units": dataset.total_standard_uncertainty.attrs.get("units"),
                    "status_flag_masks": np.asarray(
                        dataset.status_flag.attrs.get("flag_masks", [])
                    ).tolist(),
                    "status_flag_meanings": dataset.status_flag.attrs.get("flag_meanings"),
                    "regrid_method": dataset.ice_conc.attrs.get("regrid_method"),
                },
            )
            first_times.append(dataset.time.values[0])
            last_times.append(dataset.time.values[-1])
    if schemas.get("CDR") != schemas.get("ICDR"):
        raise ValueError("CDR and ICDR field semantics are incompatible")
    return {
        "file_count": len(paths),
        "first_time": str(min(first_times)),
        "last_time": str(max(last_times)),
        "latitude_count": len(reference_coordinates[0]),
        "longitude_count": len(reference_coordinates[1]),
        "schemas": schemas,
        "compatible": True,
    }


def load_daily_cube(paths: list[Path] | None = None) -> xr.Dataset:
    source_paths = paths or discover_raw_files()
    inspect_source_consistency(source_paths)
    datasets: list[xr.Dataset] = []
    for path in source_paths:
        with xr.open_dataset(path) as source:
            datasets.append(source.load())
    cube = xr.concat(datasets, dim="time").sortby("time")
    times = cube.time.values.astype("datetime64[D]")
    if len(np.unique(times)) != len(times):
        raise ValueError("Duplicate daily fields detected")
    status = cube.status_flag.fillna(0).astype("uint16")
    land_or_lake = ((status & np.uint16(3)) != 0).any(dim="time")
    cube["valid_ocean_mask"] = ~land_or_lake
    cube["ice_conc"] = cube.ice_conc.astype("float32")
    cube["total_standard_uncertainty"] = cube.total_standard_uncertainty.astype(
        "float32"
    )
    cube["status_flag"] = status
    cube.attrs.update(
        {
            "title": "POLARIS-AI Bharati/Prydz Bay daily sea-ice observation cube",
            "classification": ScientificClassification.OBSERVATION.value,
            "product_id": PRODUCT_ID,
            "cdr_dataset_id": CDR_DATASET_ID,
            "icdr_dataset_id": ICDR_DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "concentration_representation": "percentage, 0 to 100",
            "grid_note": "Copernicus provider-generated regular 0.2 degree subset",
            "source_grid_note": "Source original grid is 25 km xc/yc; it was not relabeled",
            "context_buffer_degrees": BHARATI_FORECAST_DOMAIN.context_buffer_degrees,
        }
    )
    return cube


def quality_control(cube: xr.Dataset) -> dict[str, Any]:
    times = cube.time.values.astype("datetime64[D]")
    expected = np.arange(times[0], times[-1] + np.timedelta64(1, "D"))
    missing_days = np.setdiff1d(expected, times)
    duplicate_count = int(len(times) - len(np.unique(times)))
    values = np.asarray(cube.ice_conc.values)
    finite = np.isfinite(values)
    ocean = np.asarray(cube.valid_ocean_mask.values, dtype=bool)
    out_of_range = finite & ((values < 0) | (values > 100.0001))
    return {
        "daily_fields": int(cube.sizes["time"]),
        "first_date": str(times[0]),
        "last_date": str(times[-1]),
        "grid_dimensions": {
            "latitude": int(cube.sizes["latitude"]),
            "longitude": int(cube.sizes["longitude"]),
        },
        "valid_ocean_cells": int(ocean.sum()),
        "missing_days": [str(value) for value in missing_days],
        "duplicate_days": duplicate_count,
        "nan_fraction": float((~finite).mean()),
        "concentration_min_percent": float(values[finite].min()),
        "concentration_max_percent": float(values[finite].max()),
        "out_of_range_count": int(out_of_range.sum()),
    }


def write_processed_cube(cube: xr.Dataset, path: Path = PROCESSED_CUBE) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        "ice_conc": {"zlib": True, "complevel": 4, "dtype": "float32"},
        "total_standard_uncertainty": {
            "zlib": True,
            "complevel": 4,
            "dtype": "float32",
        },
        "status_flag": {"zlib": True, "complevel": 4, "dtype": "uint16"},
        "valid_ocean_mask": {"zlib": True, "complevel": 4, "dtype": "uint8"},
    }
    cube.to_netcdf(path, engine="netcdf4", encoding=encoding)
    sources = [
        {
            "path": source.as_posix(),
            "family": source_family(source),
            "size_bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        }
        for source in discover_raw_files()
    ]
    metadata = {
        "classification": ScientificClassification.OBSERVATION.value,
        "created_at": datetime.now(UTC).isoformat(),
        "local_file": path.as_posix(),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "sources": sources,
        "quality_control": quality_control(cube),
    }
    PROCESSED_SIDECAR.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
