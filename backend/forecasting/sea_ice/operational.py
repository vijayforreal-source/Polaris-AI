"""Cached, classified forecast products from verified local scientific artifacts."""

import json
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock

import numpy as np
import torch
import xarray as xr

from .forecast_service import _sha256
from .ml.atmospheric import load_daily_forcing
from .ml.config import SeaIceV03TrainingConfig
from .ml.dataset import FORCING_VARIABLES, SeaIceWindowDataset
from .ml.network import BoundedPersistenceResidualCNN
from .models import BHARATI_FORECAST_DOMAIN, TEST_SPLIT

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "backend/forecasting/sea_ice/ml/champion.json"
CONFIG = SeaIceV03TrainingConfig()
NETCDF_LOCK = RLock()
LIMITATIONS = [
    "Decision-support research system. Not an autonomous ship-navigation authority.",
    "ERA5 reanalysis is not an operational future weather forecast.",
    "Validation was still improving at the epoch-30 ceiling; no locked-test retraining.",
]


@lru_cache(maxsize=8)
def _artifact_hash(path, modified):
    return _sha256(path)


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def results():
    return json.loads((REGISTRY.parent / "model_results_v03.json").read_text())


@lru_cache(maxsize=2)
def _cube(path, modified):
    with NETCDF_LOCK, xr.open_dataset(path) as source:
        return source.load()


def source_cube():
    path = ROOT / CONFIG.source_cube
    return _cube(path, path.stat().st_mtime_ns)


def latest_source(cube):
    """Prefer a newer verified NRT observation; never substitute an older training cube."""
    from backend.app.api.sea_ice import load_latest_observation

    try:
        with NETCDF_LOCK:
            metadata, grid = load_latest_observation()
    except (OSError, ValueError, KeyError):
        return cube
    day = np.datetime64(metadata["observation_time"][:10], "D")
    if cube is not None and day <= cube.time.values[-1].astype("datetime64[D]"):
        return cube
    values = np.asarray(grid["concentration"], dtype="float32")
    return xr.Dataset(
        {
            "ice_conc": (("time", "latitude", "longitude"), values[None]),
            "valid_ocean_mask": (("latitude", "longitude"), np.isfinite(values)),
        },
        coords={"time": [day], "latitude": grid["latitude"], "longitude": grid["longitude"]},
        attrs={"source": "Verified Copernicus Marine / OSI-SAF NRT observation"},
    )


@lru_cache(maxsize=2)
def _model(path, modified, metadata_path):
    metadata = json.loads(metadata_path.read_text())
    if _sha256(path) != metadata["model_file_sha256"]:
        raise ValueError("MODEL_CHECKSUM_MISMATCH")
    model = BoundedPersistenceResidualCNN(context_days=7, hidden_channels=24, forcing_variables=3)
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    model.eval()
    return model, metadata


@lru_cache(maxsize=2)
def _forcing(path, modified, cube_modified):
    cube = source_cube()
    with NETCDF_LOCK:
        return load_daily_forcing(
            path, cube.time.values, cube.latitude.values, cube.longitude.values
        )


def _grid(values, cube):
    return {
        "latitude": cube.latitude.values.tolist(),
        "longitude": cube.longitude.values.tolist(),
        "concentration": [[float(v) if np.isfinite(v) else None for v in row] for row in values],
        "missing_value": None,
    }


def forecast(initialization: date | None = None, *, now: datetime | None = None):
    champion = registry()
    now = now or datetime.now(UTC)
    try:
        cube = source_cube()
    except (OSError, ValueError):
        cube = None
    if initialization is None:
        cube = latest_source(cube)
    if cube is None:
        return {
            "classification": "UNAVAILABLE",
            "mode": "UNAVAILABLE",
            "champion": champion,
            "fallback_used": False,
            "fallback_reason": "OBSERVATIONS_UNAVAILABLE",
            "warnings": LIMITATIONS,
            "forecasts": [],
        }
    days = cube.time.values.astype("datetime64[D]")
    day = np.datetime64(initialization) if initialization else days[-1]
    indices = np.flatnonzero(days == day)
    if len(indices) != 1:
        raise ValueError("Historical initialization date is outside the available observations")
    index = int(indices[0])
    if initialization and index < 6:
        raise ValueError("Historical initialization requires seven observation days")
    ocean = cube.valid_ocean_mask.values.astype(bool)
    observation = np.where(ocean, cube.ice_conc.values[index], np.nan)
    valid = np.isfinite(observation) & (observation >= 0) & (observation <= 100)
    observation = np.where(valid, observation, np.nan)
    age = (now.date() - date.fromisoformat(str(day))).days
    reason = None
    forcing_used = False
    prediction = np.repeat(observation[None], 3, axis=0)
    if not valid.any():
        return {
            "classification": "UNAVAILABLE",
            "mode": "UNAVAILABLE",
            "champion": champion,
            "initialization_time": str(day) + "T00:00:00Z",
            "fallback_used": False,
            "fallback_reason": "NO_VALID_OBSERVATION",
            "warnings": LIMITATIONS,
            "forecasts": [],
        }
    elif initialization is None and (age > 3 or age < 0):
        reason = "STALE_OBSERVATION" if age > 3 else "FUTURE_OBSERVATION"
    elif index < 6:
        reason = "INSUFFICIENT_CONTIGUOUS_OBSERVATION_HISTORY"
    else:
        try:
            weights = ROOT / champion["weights_path"]
            model, metadata = _model(
                weights, weights.stat().st_mtime_ns, ROOT / champion["metadata_path"]
            )
            for path, key in (
                (ROOT / CONFIG.source_cube, "source_dataset_sha256"),
                (ROOT / CONFIG.forcing_path, "forcing_dataset_sha256"),
            ):
                if (
                    key in metadata
                    and _artifact_hash(path, path.stat().st_mtime_ns) != metadata[key]
                ):
                    raise ValueError("INPUT_ARTIFACT_CHECKSUM_MISMATCH")
            forcing_path = ROOT / CONFIG.forcing_path
            if not forcing_path.is_file():
                raise ValueError("FORCING_UNAVAILABLE")
            forcing = _forcing(
                forcing_path,
                forcing_path.stat().st_mtime_ns,
                (ROOT / CONFIG.source_cube).stat().st_mtime_ns,
            )
            if not np.all(np.isfinite(forcing[index, :, ocean])):
                raise ValueError("FORCING_INCOMPLETE_AT_INITIALIZATION")
            stats = metadata["forcing_normalization"]
            dataset = SeaIceWindowDataset(
                cube.ice_conc.values,
                cube.time.values,
                ocean,
                TEST_SPLIT,
                forcing=forcing,
                forcing_mean=np.array(
                    [stats[v]["mean"] for v in FORCING_VARIABLES], dtype="float32"
                ),
                forcing_std=np.array([stats[v]["std"] for v in FORCING_VARIABLES], dtype="float32"),
            )
            features = torch.from_numpy(dataset.features_at(index)).unsqueeze(0)
            with torch.no_grad():
                output = model.raw_prediction(features).numpy()[0] * 100
            if output.shape != (3, *ocean.shape) or not np.all(np.isfinite(output[:, valid])):
                raise ValueError("INVALID_MODEL_OUTPUT")
            if np.any((output[:, valid] < 0) | (output[:, valid] > 100)):
                raise ValueError("MODEL_OUTPUT_OUT_OF_BOUNDS")
            prediction = np.where(valid[None], output, np.nan)
            forcing_used = True
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            reason = str(error)
    classification = (
        "PERSISTENCE_FALLBACK"
        if reason
        else "HISTORICAL_FORECAST_BENCHMARK"
        if initialization
        else "LATEST_AVAILABLE_MODEL_PREDICTION"
    )
    domain = BHARATI_FORECAST_DOMAIN
    lat, lon = cube.latitude.values, cube.longitude.values
    forecasts = []
    for h in range(1, 4):
        target_day = day + np.timedelta64(h, "D")
        target_index = np.flatnonzero(days == target_day)
        target = None
        if initialization and len(target_index):
            target = _grid(np.where(ocean, cube.ice_conc.values[target_index[0]], np.nan), cube)
        forecasts.append(
            {
                "horizon_hours": h * 24,
                "forecast_valid_time": str(target_day) + "T00:00:00Z",
                "classification": "PERSISTENCE_MODEL" if reason else "MODEL_PREDICTION",
                "grid": _grid(prediction[h - 1], cube),
                "observed_target": target,
                "target_classification": "OBSERVATION" if target else None,
                "persistence": _grid(observation, cube),
            }
        )
    return {
        "mode": "PERSISTENCE" if reason else "MODEL_PREDICTION",
        "classification": classification,
        "champion": champion,
        "champion_used": not bool(reason),
        "model_name": "Persistence" if reason else champion["model_name"],
        "model_version": "persistence" if reason else champion["model_version"],
        "initialization_time": str(day) + "T00:00:00Z",
        "age_days": age,
        "freshness": "HISTORICAL" if initialization else "STALE" if age > 3 else "CURRENT",
        "units": "percent sea-ice concentration",
        "grid_shape": list(ocean.shape),
        "source_observation": "Copernicus Marine / OSI-SAF",
        "observation": _grid(observation, cube),
        "observation_classification": "OBSERVATION",
        "forcing_source": "ERA5" if forcing_used else None,
        "forcing_classification": "REANALYSIS" if forcing_used else None,
        "fallback_used": bool(reason),
        "fallback_reason": reason,
        "provenance": {
            "source_cube": cube.attrs.get("source", str(CONFIG.source_cube)),
            "model_sha256": champion["weights_sha256"] if not reason else None,
            "forcing_time_semantics": "00:00 UTC initialization-state only",
        },
        "warnings": LIMITATIONS + ([reason] if reason else []),
        "forecasts": forecasts,
        "map_metadata": {
            "bbox": {
                "minimum_latitude": float(lat.min()),
                "maximum_latitude": float(lat.max()),
                "minimum_longitude": float(lon.min()),
                "maximum_longitude": float(lon.max()),
            },
            "bharati": {
                "latitude": domain.bharati_latitude,
                "longitude": domain.bharati_longitude,
                "name": "BHARATI",
            },
        },
    }


def status():
    product = forecast()
    try:
        days = source_cube().time.values.astype("datetime64[D]")
        bounds = {"minimum": str(days[0] + np.timedelta64(6, "D")), "maximum": str(days[-1])}
    except (OSError, ValueError):
        bounds = None
    return {
        key: value
        for key, value in product.items()
        if key not in {"forecasts", "observation", "map_metadata"}
    } | {
        "historical_dates": bounds,
        "model_available": (ROOT / registry()["weights_path"]).is_file(),
        "forcing_available": (ROOT / CONFIG.forcing_path).is_file(),
    }
