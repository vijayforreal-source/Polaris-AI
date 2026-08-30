import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from backend.ingestion.config import StudyRegion
from backend.ingestion.models import ScientificClassification, ScientificMetadata

PRODUCT_ID = "SEAICE_GLO_SEAICE_L4_NRT_OBSERVATIONS_011_001"
DATASET_ID = "osisaf_obs-si_glo_phy-sic-south_nrt_amsr2_l4_P1D-m"
SIC_VARIABLE = "ice_conc"
SOURCE = "Copernicus Marine Service / OSI-SAF"


def build_subset_arguments(region: StudyRegion, observed_at: datetime) -> list[str]:
    """Build a one-variable, one-time, geographic subset request."""
    timestamp = observed_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return [
        "--dataset-id",
        DATASET_ID,
        "--variable",
        SIC_VARIABLE,
        "--minimum-longitude",
        str(region.minimum_longitude),
        "--maximum-longitude",
        str(region.maximum_longitude),
        "--minimum-latitude",
        str(region.minimum_latitude),
        "--maximum-latitude",
        str(region.maximum_latitude),
        "--start-datetime",
        timestamp,
        "--end-datetime",
        timestamp,
        "--file-format",
        "netcdf",
    ]


def raw_observation_directory(raw_root: Path, observed_at: datetime) -> Path:
    return raw_root / "osi_saf_sic_south" / observed_at.date().isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def inspect_netcdf(path: Path, variable: str = SIC_VARIABLE) -> dict[str, Any]:
    """Read source metadata and decoded statistics without modifying the raw file."""
    with xr.open_dataset(path, decode_cf=False, mask_and_scale=False) as raw_dataset:
        raw_variable = raw_dataset[variable]
        raw_attributes = {key: _jsonable(value) for key, value in raw_variable.attrs.items()}
        grid_mapping_name = raw_variable.attrs.get("grid_mapping")
        grid_mapping_attributes = (
            {
                key: _jsonable(value)
                for key, value in raw_dataset[grid_mapping_name].attrs.items()
            }
            if grid_mapping_name and grid_mapping_name in raw_dataset
            else {}
        )
        dataset_attributes = {
            key: _jsonable(value) for key, value in raw_dataset.attrs.items()
        }
        coordinate_metadata = {
            name: {
                "dtype": str(coordinate.dtype),
                "dimensions": list(coordinate.dims),
                "attributes": {
                    key: _jsonable(value) for key, value in coordinate.attrs.items()
                },
                "minimum": _jsonable(np.asarray(coordinate.values).min()),
                "maximum": _jsonable(np.asarray(coordinate.values).max()),
            }
            for name, coordinate in raw_dataset.coords.items()
        }

    with xr.open_dataset(path, decode_cf=True, mask_and_scale=True) as dataset:
        data_array = dataset[variable]
        values = np.asarray(data_array.values)
        finite = np.isfinite(values)
        valid_count = int(finite.sum())
        missing_count = int(values.size - valid_count)
        valid_min = float(values[finite].min()) if valid_count else None
        valid_max = float(values[finite].max()) if valid_count else None
        time_values = [str(value) for value in np.atleast_1d(dataset["time"].values)]

        return {
            "dimensions": dict(dataset.sizes),
            "coordinates": list(dataset.coords),
            "coordinate_metadata": coordinate_metadata,
            "data_variables": list(dataset.data_vars),
            "dataset_attributes": dataset_attributes,
            "variable": variable,
            "dtype": str(data_array.dtype),
            "shape": list(data_array.shape),
            "dimensions_order": list(data_array.dims),
            "time": time_values,
            "units": data_array.attrs.get("units", raw_attributes.get("units")),
            "raw_variable_attributes": raw_attributes,
            "scale_factor": raw_attributes.get("scale_factor"),
            "add_offset": raw_attributes.get("add_offset"),
            "fill_value": raw_attributes.get("_FillValue"),
            "valid_min": valid_min,
            "valid_max": valid_max,
            "valid_count": valid_count,
            "missing_count": missing_count,
            "grid_mapping_variable": grid_mapping_name,
            "grid_mapping_attributes": grid_mapping_attributes,
        }


def register_raw_file(
    path: Path,
    observed_at: datetime,
    inspection: dict[str, Any],
) -> ScientificMetadata:
    downloaded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    grid_mapping = inspection["grid_mapping_attributes"]
    native_crs = (
        json.dumps(grid_mapping, sort_keys=True)
        if grid_mapping
        else "regular latitude/longitude subset grid; no grid_mapping or EPSG declared"
    )
    return ScientificMetadata(
        classification=ScientificClassification.OBSERVATION,
        variable=SIC_VARIABLE,
        source=SOURCE,
        product_id=PRODUCT_ID,
        dataset_id=DATASET_ID,
        observed_at=observed_at,
        valid_at=None,
        downloaded_at=downloaded_at,
        native_crs=native_crs,
        canonical_crs=None,
        spatial_resolution="0.1 degree provider subset grid (regrid_method=bilinear)",
        temporal_resolution="P1D",
        units=inspection["units"],
        quality_flags=[],
        provenance={
            "provider": SOURCE,
            "acquisition_method": "copernicusmarine subset",
            "classification": ScientificClassification.OBSERVATION.value,
        },
        local_file=path.as_posix(),
        sha256=sha256_file(path),
    )


def write_sidecar(path: Path, metadata: ScientificMetadata) -> Path:
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    payload = {
        **metadata.model_dump(mode="json"),
        "file_size_bytes": path.stat().st_size,
    }
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return sidecar
