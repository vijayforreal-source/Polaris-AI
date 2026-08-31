from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ScientificClassification(StrEnum):
    OBSERVATION = "OBSERVATION"
    ANALYSIS = "ANALYSIS"
    REANALYSIS = "REANALYSIS"
    FORECAST = "FORECAST"
    MODEL_PREDICTION = "MODEL_PREDICTION"


class ScientificMetadata(BaseModel):
    """Provenance contract shared by future scientific ingestion sources."""

    model_config = ConfigDict(extra="forbid")

    classification: ScientificClassification
    variable: str
    source: str
    product_id: str
    dataset_id: str
    observed_at: datetime | None
    valid_at: datetime | None
    downloaded_at: datetime
    native_crs: str | None
    canonical_crs: str | None = None
    spatial_resolution: str | None
    temporal_resolution: str | None
    units: str | None
    quality_flags: list[str]
    provenance: dict[str, str]
    local_file: str
    sha256: str
