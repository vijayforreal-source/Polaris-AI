"""Read-only adapters to frozen scientific products and a cached Checkpoint 5 field interface."""

import json
import math
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from backend.forecasting.sea_ice import operational
from backend.historical_transit.corridor import build_corridor
from backend.historical_transit.store import STORE, load_voyages
from backend.iceberg.usnic_registry import latest_registry_file, parse_registry, sha256_file

from .components import GEOD
from .config import CONFIG
from .engine import compute_risk, explain_point, field_summary
from .models import IcebergState, RiskInputs
from .vessel import PROFILES, VesselProfile, get_vessel

ROOT = Path(__file__).resolve().parents[3]
SERVICE_LOCK = RLock()


class RiskUnavailable(ValueError):
    pass


def _time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Initialization time requires a timezone")
    return value.astimezone(UTC)


def resample_grid(grid: dict, latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    """Bilinear interpolation, no extrapolation; missing input cells remain missing."""
    lat = np.asarray(grid["latitude"], dtype=float)
    lon = np.asarray(grid["longitude"], dtype=float)
    values = np.asarray(grid["concentration"], dtype=float)
    if (
        values.shape != (len(lat), len(lon))
        or len(np.unique(lat)) != len(lat)
        or len(np.unique(lon)) != len(lon)
    ):
        raise ValueError("Invalid source grid schema")
    values = np.where(np.isfinite(values) & (values >= 0) & (values <= 100), values, np.nan)
    if np.array_equal(lat, latitude) and np.array_equal(lon, longitude):
        return values
    yi, xi = np.argsort(lat), np.argsort(lon)
    interpolator = RegularGridInterpolator(
        (lat[yi], lon[xi]), values[yi][:, xi], bounds_error=False, fill_value=np.nan
    )
    yy, xx = np.meshgrid(latitude, longitude, indexing="ij")
    return interpolator(np.stack([yy, xx], axis=-1))


@lru_cache(maxsize=2)
def _registry(path: Path, modified: int, sidecar_modified: int):
    sidecar = json.loads(path.with_suffix(path.suffix + ".metadata.json").read_text())
    if sha256_file(path) != sidecar["sha256"]:
        raise ValueError("USNIC_REGISTRY_CHECKSUM_MISMATCH")
    return parse_registry(path), sidecar


def current_icebergs(latitude, longitude, now, initialization_time):
    try:
        path = latest_registry_file(ROOT / "data/raw/usnic/icebergs")
        sidecar_path = path.with_suffix(path.suffix + ".metadata.json")
        records, metadata = _registry(
            path, path.stat().st_mtime_ns, sidecar_path.stat().st_mtime_ns
        )
        report = datetime.fromisoformat(metadata["provider_report_date"]).replace(tzinfo=UTC)
        if report.date() > initialization_time.date() or report > now:
            raise ValueError("No contemporaneous iceberg registry for requested initialization")
        report_age = (now - report).total_seconds() / 86400 + 1
        states = []
        for record in records.observations:
            # Broad geodesic buffer around the risk domain, not the research-candidate list.
            _, _, meters = GEOD.inv(
                record.longitude,
                record.latitude,
                float(np.clip(record.longitude, longitude.min(), longitude.max())),
                float(np.clip(record.latitude, latitude.min(), latitude.max())),
            )
            radius = (
                math.hypot(record.length_nm, record.width_nm) * 1.852 / 2
                if (record.length_nm is not None and record.width_nm is not None)
                else None
            )
            buffer = (
                CONFIG.iceberg_caution_km * 4
                + CONFIG.iceberg_exclusion_km
                + CONFIG.iceberg_unavailable_days * CONFIG.iceberg_age_growth_km_per_day
                + 72 * CONFIG.iceberg_horizon_growth_km_per_hour
                + (radius or CONFIG.unknown_iceberg_size_km)
            )
            if meters / 1000 > buffer:
                continue
            observed = datetime.combine(record.last_updated_on, datetime.min.time(), tzinfo=UTC)
            if observed.date() > initialization_time.date():
                raise ValueError("Iceberg observation postdates initialization")
            states.append(
                IcebergState(
                    iceberg_id=record.iceberg_id,
                    latitude=record.latitude,
                    longitude=record.longitude,
                    observed_at=observed,
                    size_radius_km=radius,
                    date_precision_days=1,
                    source=record.source,
                )
            )
        state = (
            "UNAVAILABLE"
            if report_age > CONFIG.iceberg_unavailable_days or records.rejected_rows
            else ("STALE" if report_age > CONFIG.iceberg_stale_days else "AVAILABLE")
        )
        return (
            states,
            state,
            report_age,
            {
                "source": metadata["source_page"],
                "report_date": metadata["provider_report_date"],
                "sha256": metadata["sha256"],
                "source_classification": "OBSERVATION",
                "time_precision": "UTC calendar date; one-day conservative age allowance",
                "rejected_record_count": len(records.rejected_rows),
            },
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [], "UNAVAILABLE", 0, {"reason": str(error)}


def load_inputs(
    initialization_time: datetime | None = None, *, now: datetime | None = None
) -> RiskInputs:
    now = _time(now or datetime.now(UTC))
    if initialization_time:
        initialization_time = _time(initialization_time)
        if any(
            (
                initialization_time.hour,
                initialization_time.minute,
                initialization_time.second,
                initialization_time.microsecond,
            )
        ):
            raise ValueError("Sea-ice initialization must be 00:00 UTC")
    try:
        cube = operational.source_cube()
    except (OSError, ValueError) as error:
        raise RiskUnavailable(
            "Verified risk grid/ocean mask unavailable; no substitute grid generated"
        ) from error
    latitude = np.asarray(cube.latitude.values, dtype=float)
    longitude = np.asarray(cube.longitude.values, dtype=float)
    ocean = np.asarray(cube.valid_ocean_mask.values, dtype=bool)
    product = operational.forecast(
        initialization_time.date() if initialization_time else None, now=now
    )
    actual_init = datetime.fromisoformat(
        product.get("initialization_time", now.isoformat()).replace("Z", "+00:00")
    )
    source_age = (now - actual_init).total_seconds() / 86400
    fields = {}
    if product.get("observation"):
        fields[0] = resample_grid(product["observation"], latitude, longitude)
        for item in product["forecasts"]:
            fields[item["horizon_hours"]] = resample_grid(item["grid"], latitude, longitude)
    sea_state = (
        "UNAVAILABLE"
        if product["mode"] == "UNAVAILABLE"
        else (
            "STALE"
            if source_age > CONFIG.maximum_sic_age_days
            else "DEGRADED"
            if product["fallback_used"]
            else "AVAILABLE"
        )
    )
    bergs, berg_state, berg_age, berg_provenance = current_icebergs(
        latitude, longitude, now, actual_init
    )
    # Avoid future transit leakage when requesting retrospective initialization.
    cutoff = min(now, actual_init) if initialization_time else now
    voyages, errors = load_voyages()
    eligible = [v for v in voyages if v.points and max(p.timestamp_utc for p in v.points) <= cutoff]
    corridor = build_corridor(eligible, now=cutoff, tau_days=CONFIG.historical_tau_days)
    historical_state = (
        "DEGRADED" if errors else "AVAILABLE" if corridor["cells"] else "NO_VERIFIED_DATA"
    )
    benchmark = operational.results()
    mae = tuple(benchmark["horizons"][f"{h}H"]["ai"]["mae_percentage_points"] for h in (24, 48, 72))
    return RiskInputs(
        latitude,
        longitude,
        ocean,
        fields,
        actual_init,
        now,
        sea_ice_state=sea_state,
        forecast_mode=product["mode"],
        sea_ice_age_days=source_age,
        icebergs=bergs,
        iceberg_state=berg_state,
        iceberg_report_age_days=berg_age,
        historical_cells=corridor["cells"],
        historical_state=historical_state,
        mae_pp=mae,
        provenance={
            "sea_ice": product.get("provenance", {}),
            "sea_ice_source": product.get("source_observation"),
            "sea_ice_classification": product["classification"],
            "forcing_classification": product.get("forcing_classification"),
            "fallback_reason": product.get("fallback_reason"),
            "icebergs": berg_provenance,
            "historical_transit": corridor["method"],
            "historical_load_errors": errors,
            "ocean_mask": "Frozen SIC valid_ocean_mask; false includes land/invalid cells. "
            "Not bathymetry.",
            "alignment": "Canonical 52x100 SIC grid; bilinear source regridding without "
            "extrapolation.",
            "mode": "RETROSPECTIVE_INPUT_ASSESSMENT"
            if initialization_time
            else "LATEST_AVAILABLE_STATE",
        },
    )


def source_fingerprint() -> tuple:
    paths = [
        ROOT / operational.CONFIG.source_cube,
        ROOT / operational.CONFIG.forcing_path,
        ROOT / operational.CONFIG.model_path,
        operational.REGISTRY,
        operational.REGISTRY.parent / "model_results_v03.json",
    ]
    for folder, pattern in (
        (ROOT / "data/raw/copernicus/osi_saf_sic_south", "*/*"),
        (ROOT / "data/raw/usnic/icebergs", "*/*"),
        (STORE, "**/*.json"),
    ):
        paths.extend(p for p in folder.glob(pattern) if p.is_file())
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.is_file())


@lru_cache(maxsize=8)
def _cached_field(
    initialization: str | None, horizon: float, profile_json: str, fingerprint: tuple, minute: int
):
    inputs = load_inputs(
        datetime.fromisoformat(initialization) if initialization else None,
        now=datetime.fromtimestamp(minute * 60, UTC),
    )
    return compute_risk(inputs, horizon, VesselProfile.model_validate_json(profile_json))


def get_risk_field(
    initialization_time: datetime | None = None,
    horizon_hours: float = 0,
    vessel_profile: VesselProfile | None = None,
    *,
    now: datetime | None = None,
):
    vessel = vessel_profile or get_vessel("simulated-research")
    if now is not None:
        return compute_risk(load_inputs(initialization_time, now=now), horizon_hours, vessel)
    with SERVICE_LOCK:
        return _cached_field(
            initialization_time.isoformat() if initialization_time else None,
            horizon_hours,
            vessel.model_dump_json(),
            source_fingerprint(),
            int(datetime.now(UTC).timestamp() // 60),
        )


def get_point_risk(
    latitude: float,
    longitude: float,
    horizon_hours: float = 0,
    vessel_profile: VesselProfile | None = None,
    initialization_time: datetime | None = None,
):
    return explain_point(
        get_risk_field(initialization_time, horizon_hours, vessel_profile), latitude, longitude
    )


def status():
    try:
        field = get_risk_field()
        return {
            "checkpoint": "CHECKPOINT_4",
            "state": field.metadata["state"],
            "component_states": field.metadata["component_states"],
            "initialization_time": field.metadata["initialization_time"],
            "latest_iceberg_report": field.metadata["provenance"]["icebergs"].get("report_date"),
            "vessel_profiles": [v.model_dump(mode="json") for v in PROFILES.values()],
            "summary": field_summary(field),
            "limitations": field.metadata["limitations"],
        }
    except RiskUnavailable as error:
        return {
            "checkpoint": "CHECKPOINT_4",
            "state": "UNAVAILABLE",
            "reason": str(error),
            "component_states": {
                "sea_ice": "UNAVAILABLE",
                "icebergs": "UNAVAILABLE",
                "historical_transit": "NO_VERIFIED_DATA",
            },
            "vessel_profiles": [v.model_dump(mode="json") for v in PROFILES.values()],
            "limitations": ["No verified spatial grid available; no risk field fabricated."],
        }
