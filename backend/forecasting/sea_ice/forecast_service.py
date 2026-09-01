import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ForecastProduct:
    source_type: str
    forecasts: dict[str, np.ndarray]
    provenance: dict[str, object]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def persistence_fallback(
    latest_observation: np.ndarray,
    initialization_time: datetime,
    reason: str,
) -> ForecastProduct:
    field = np.asarray(latest_observation, dtype="float32")
    return ForecastProduct(
        source_type="PERSISTENCE_FALLBACK",
        forecasts={horizon: field.copy() for horizon in ("24h", "48h", "72h")},
        provenance={
            "initialization_time": initialization_time.isoformat(),
            "model_version": None,
            "model_weight_sha256": None,
            "fallback_reason": reason,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )


def generate_forecast(
    latest_observation: np.ndarray,
    initialization_time: datetime,
    *,
    model_path: Path,
    forcing_available: bool,
    maximum_age_days: int = 3,
) -> ForecastProduct:
    """Validate operational prerequisites; inference wiring follows verified forcing."""
    age_days = (datetime.now(UTC) - initialization_time.astimezone(UTC)).total_seconds() / 86400
    if age_days > maximum_age_days:
        return persistence_fallback(latest_observation, initialization_time, "STALE_OBSERVATION")
    if not model_path.is_file():
        return persistence_fallback(
            latest_observation, initialization_time, "MODEL_WEIGHTS_MISSING"
        )
    if not forcing_available:
        return persistence_fallback(latest_observation, initialization_time, "FORCING_UNAVAILABLE")
    return persistence_fallback(
        latest_observation,
        initialization_time,
        "MODEL_INFERENCE_NOT_ENABLED_WITHOUT_VERIFIED_OPERATIONAL_FORCING",
    )
