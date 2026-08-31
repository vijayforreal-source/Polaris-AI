from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.ingestion.models import ScientificClassification


class IcebergObservation(BaseModel):
    """One current provider observation; no motion or prediction is implied."""

    model_config = ConfigDict(extra="forbid")

    iceberg_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    last_updated_on: date
    provider_last_update: str
    length_nm: float | None = Field(default=None, ge=0)
    width_nm: float | None = Field(default=None, ge=0)
    area_sq_nm: float | None = Field(default=None, ge=0)
    region: str | None = None
    provider: str
    source: str
    classification: Literal[ScientificClassification.OBSERVATION] = (
        ScientificClassification.OBSERVATION
    )
    provenance: dict[str, str]


class IcebergTrackPoint(BaseModel):
    """A provider-dated historical position retained as an observation."""

    model_config = ConfigDict(extra="forbid")

    iceberg_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observation_date: date
    registry_dates: list[date]
    original_last_update: str
    length_nm: float | None = Field(default=None, ge=0)
    width_nm: float | None = Field(default=None, ge=0)
    area_sq_nm: float | None = Field(default=None, ge=0)
    source_files: list[str]
    provider: str
    classification: Literal[ScientificClassification.OBSERVATION] = (
        ScientificClassification.OBSERVATION
    )
    provenance: dict[str, str]
