from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xarray as xr

from backend.forecasting.sea_ice.dataset import PROCESSED_CUBE, sha256_file
from backend.forecasting.sea_ice.ml.atmospheric import (
    ERA5_DATASET_ID,
    ERA5_REQUEST_VARIABLES,
)
from backend.forecasting.sea_ice.ml.dataset import FORCING_VARIABLES

START_DATE = np.datetime64("2015-01-01")
END_DATE = np.datetime64("2026-08-16")

RAW_ROOT = Path("data/raw/era5/sea_ice_bharati")

OUTPUT_PATH = Path(
    "data/processed/forecasting/era5_bharati_daily_2015_2026.nc"
)

MARGIN_DEGREES = 0.5
MAX_RETRIES = 3


def request_for_year(
    year: int,
    *,
    north: float,
    west: float,
    south: float,
    east: float,
) -> dict[str, object]:
    months = list(range(1, 13))

    if year == 2026:
        months = list(range(1, 9))

    return {
        "product_type": ["reanalysis"],
        "variable": list(ERA5_REQUEST_VARIABLES),
        "year": [str(year)],
        "month": [f"{month:02d}" for month in months],
        "day": [f"{day:02d}" for day in range(1, 32)],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [north, west, south, east],
    }


def raw_target(year: int) -> Path:
    return RAW_ROOT / f"era5_u10_v10_t2m_00utc_{year}.nc"


def normalize_era5_dataset(dataset: xr.Dataset) -> xr.Dataset:
    if "valid_time" in dataset.coords and "time" not in dataset.coords:
        dataset = dataset.rename({"valid_time": "time"})

    if "time" not in dataset.coords:
        raise ValueError("ERA5 file has no time/valid_time coordinate")

    missing = set(FORCING_VARIABLES) - set(dataset.data_vars)

    if missing:
        raise ValueError(
            f"ERA5 variables missing: {sorted(missing)}"
        )

    required_coords = {"latitude", "longitude"}

    if not required_coords.issubset(dataset.coords):
        raise ValueError(
            "ERA5 latitude/longitude coordinates are missing"
        )

    return dataset[list(FORCING_VARIABLES)]


def inspect_raw(path: Path) -> dict[str, object]:
    with xr.open_dataset(path) as source:
        dataset = normalize_era5_dataset(source)

        times = dataset.time.values.astype("datetime64[h]")

        if len(times) == 0:
            raise ValueError(f"ERA5 file contains no timestamps: {path}")

        if len(np.unique(times)) != len(times):
            raise ValueError(
                f"Duplicate ERA5 timestamps detected: {path}"
            )

        hours_since_epoch = times.astype("datetime64[h]").astype(int)

        if np.any(hours_since_epoch % 24 != 0):
            raise ValueError(
                f"Non-00:00 UTC ERA5 timestamp detected: {path}"
            )

        return {
            "time_count": int(dataset.sizes["time"]),
            "first_time": str(times[0]),
            "last_time": str(times[-1]),
            "latitude_count": int(dataset.sizes["latitude"]),
            "longitude_count": int(dataset.sizes["longitude"]),
            "variables": list(FORCING_VARIABLES),
            "units": {
                name: dataset[name].attrs.get("units")
                for name in FORCING_VARIABLES
            },
        }


def download_year(
    year: int,
    *,
    north: float,
    west: float,
    south: float,
    east: float,
) -> Path:
    import cdsapi

    path = raw_target(year)

    sidecar = path.with_suffix(".nc.metadata.json")

    if path.is_file() and sidecar.is_file():
        metadata = json.loads(
            sidecar.read_text(encoding="utf-8")
        )

        if metadata.get("sha256") == sha256_file(path):
            inspect_raw(path)

            print(
                f"ERA5 {year}: verified cached file"
            )

            return path

        raise ValueError(
            f"Checksum mismatch for cached ERA5 file: {path}"
        )

    # Remove incomplete file left by an interrupted request.
    if path.exists():
        path.unlink()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    request = request_for_year(
        year,
        north=north,
        west=west,
        south=south,
        east=east,
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"ERA5 {year}: "
                f"download attempt {attempt}/{MAX_RETRIES}"
            )

            cdsapi.Client(
                quiet=True,
                progress=False,
            ).retrieve(
                ERA5_DATASET_ID,
                request,
                str(path),
            )

            inspection = inspect_raw(path)

            metadata = {
                "provider":
                    "Copernicus Climate Change Service / ECMWF",
                "dataset_id": ERA5_DATASET_ID,
                "classification": "REANALYSIS",
                "requested_variables":
                    list(ERA5_REQUEST_VARIABLES),
                "model_variables":
                    list(FORCING_VARIABLES),
                "time_semantics":
                    "00:00 UTC initialization-state only",
                "requested_area_north_west_south_east": [
                    north,
                    west,
                    south,
                    east,
                ],
                "sha256": sha256_file(path),
                "file_size_bytes": path.stat().st_size,
                "retrieved_at":
                    datetime.now(UTC).isoformat(),
                "inspection": inspection,
            }

            sidecar.write_text(
                json.dumps(
                    metadata,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            return path

        except Exception as exc:
            last_error = exc

            if path.exists():
                path.unlink()

            if attempt < MAX_RETRIES:
                wait_seconds = 5 * attempt

                print(
                    f"ERA5 {year}: retrying in "
                    f"{wait_seconds}s"
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        f"ERA5 {year} download failed after retries"
    ) from last_error


def target_grid(
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with xr.open_dataset(PROCESSED_CUBE) as source:
        times = source.time.values.astype("datetime64[D]")

        latitude = np.asarray(
            source.latitude.values,
            dtype="float64",
        )

        longitude = np.asarray(
            source.longitude.values,
            dtype="float64",
        )

    if times[0] != START_DATE:
        raise ValueError(
            f"Unexpected first sea-ice date: {times[0]}"
        )

    if times[-1] != END_DATE:
        raise ValueError(
            f"Unexpected final sea-ice date: {times[-1]}"
        )

    if len(times) != 4246:
        raise ValueError(
            f"Expected 4246 sea-ice days, "
            f"found {len(times)}"
        )

    return times, latitude, longitude


def geographic_bounds(
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> tuple[float, float, float, float]:
    north = min(
        90.0,
        float(latitude.max()) + MARGIN_DEGREES,
    )

    south = max(
        -90.0,
        float(latitude.min()) - MARGIN_DEGREES,
    )

    west = max(
        -180.0,
        float(longitude.min()) - MARGIN_DEGREES,
    )

    east = min(
        180.0,
        float(longitude.max()) + MARGIN_DEGREES,
    )

    return north, west, south, east


def load_and_regrid(
    paths: list[Path],
    target_times: np.ndarray,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
) -> xr.Dataset:
    yearly_datasets: list[xr.Dataset] = []

    for path in paths:
        print(
            f"Loading and validating {path.name}"
        )

        with xr.open_dataset(path) as source:
            dataset = normalize_era5_dataset(source).load()

        dataset = dataset.sortby("latitude")
        dataset = dataset.sortby("longitude")

        dataset = dataset.assign_coords(
            time=dataset.time.values.astype(
                "datetime64[D]"
            )
        )

        yearly_datasets.append(dataset)

    combined = xr.concat(
        yearly_datasets,
        dim="time",
    ).sortby("time")

    days = combined.time.values.astype(
        "datetime64[D]"
    )

    if len(days) != len(np.unique(days)):
        raise ValueError(
            "Duplicate ERA5 initialization dates detected"
        )

    combined = combined.sel(
        time=slice(
            START_DATE,
            END_DATE,
        )
    )

    days = combined.time.values.astype(
        "datetime64[D]"
    )

    if not np.array_equal(
        days,
        target_times,
    ):
        missing = np.setdiff1d(
            target_times,
            days,
        )

        extra = np.setdiff1d(
            days,
            target_times,
        )

        raise ValueError(
            "ERA5 days do not exactly match sea ice. "
            f"Missing={missing[:10].tolist()} "
            f"Extra={extra[:10].tolist()}"
        )

    print(
        "Regridding ERA5 to POLARIS "
        "52 x 100 sea-ice grid..."
    )

    regridded = combined.interp(
        latitude=xr.DataArray(
            target_latitude,
            dims="latitude",
        ),
        longitude=xr.DataArray(
            target_longitude,
            dims="longitude",
        ),
        method="linear",
    )

    regridded = regridded.astype(
        "float32"
    )

    regridded.attrs.update(
        {
            "title":
                "POLARIS-AI ERA5 atmospheric forcing",
            "classification":
                "REANALYSIS",
            "dataset_id":
                ERA5_DATASET_ID,
            "time_semantics":
                "00:00 UTC only; no future/full-day leakage",
            "target_grid":
                "POLARIS 52x100 Bharati/Prydz Bay grid",
            "regridding":
                "linear interpolation on regular lat/lon grid",
        }
    )

    return regridded


def forcing_statistics(
    dataset: xr.Dataset,
) -> dict[str, object]:
    payload: dict[str, object] = {}

    for name in FORCING_VARIABLES:
        values = np.asarray(
            dataset[name].values,
            dtype="float64",
        )

        finite = np.isfinite(values)

        if not finite.any():
            raise ValueError(
                f"No finite values found for {name}"
            )

        payload[name] = {
            "units":
                dataset[name].attrs.get("units"),
            "nan_fraction":
                float((~finite).mean()),
            "minimum":
                float(values[finite].min()),
            "maximum":
                float(values[finite].max()),
            "mean":
                float(values[finite].mean()),
        }

    return payload


def write_processed(
    dataset: xr.Dataset,
    *,
    overwrite: bool,
) -> None:
    if OUTPUT_PATH.exists() and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing ERA5 "
            f"forcing cube: {OUTPUT_PATH}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoding = {
        name: {
            "zlib": True,
            "complevel": 4,
            "dtype": "float32",
        }
        for name in FORCING_VARIABLES
    }

    dataset.to_netcdf(
        OUTPUT_PATH,
        engine="netcdf4",
        encoding=encoding,
    )

    metadata = {
        "provider":
            "Copernicus Climate Change Service / ECMWF",
        "dataset_id":
            ERA5_DATASET_ID,
        "classification":
            "REANALYSIS",
        "variables":
            list(FORCING_VARIABLES),
        "time_count":
            int(dataset.sizes["time"]),
        "first_date":
            str(
                dataset.time.values[0].astype(
                    "datetime64[D]"
                )
            ),
        "last_date":
            str(
                dataset.time.values[-1].astype(
                    "datetime64[D]"
                )
            ),
        "grid": {
            "latitude":
                int(dataset.sizes["latitude"]),
            "longitude":
                int(dataset.sizes["longitude"]),
        },
        "time_semantics":
            "ERA5 at 00:00 UTC on initialization day only",
        "statistics":
            forcing_statistics(dataset),
        "file_size_bytes":
            OUTPUT_PATH.stat().st_size,
        "sha256":
            sha256_file(OUTPUT_PATH),
        "created_at":
            datetime.now(UTC).isoformat(),
    }

    metadata_path = OUTPUT_PATH.with_suffix(
        ".metadata.json"
    )

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\nERA5 FORCING CUBE COMPLETE")
    print(
        json.dumps(
            metadata,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    parser.add_argument(
        "--download-only",
        action="store_true",
    )

    args = parser.parse_args()

    if not PROCESSED_CUBE.is_file():
        raise FileNotFoundError(
            "Verified POLARIS sea-ice cube "
            f"not found: {PROCESSED_CUBE}"
        )

    target_times, latitude, longitude = target_grid()

    north, west, south, east = geographic_bounds(
        latitude,
        longitude,
    )

    print(
        "ERA5 request area [N,W,S,E]: "
        f"[{north:.2f}, "
        f"{west:.2f}, "
        f"{south:.2f}, "
        f"{east:.2f}]"
    )

    paths = []

    for year in range(2015, 2027):
        path = download_year(
            year,
            north=north,
            west=west,
            south=south,
            east=east,
        )

        paths.append(path)

    if args.download_only:
        print(
            "All ERA5 yearly files downloaded "
            "and verified."
        )
        return

    forcing = load_and_regrid(
        paths,
        target_times,
        latitude,
        longitude,
    )

    expected_shape = (
        4246,
        52,
        100,
    )

    actual_shape = (
        forcing.sizes["time"],
        forcing.sizes["latitude"],
        forcing.sizes["longitude"],
    )

    if actual_shape != expected_shape:
        raise ValueError(
            "Unexpected forcing dimensions: "
            f"{actual_shape}"
        )

    write_processed(
        forcing,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()