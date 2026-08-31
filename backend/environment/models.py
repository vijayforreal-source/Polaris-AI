from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.ingestion.models import ScientificClassification


class EnvironmentalForcingSample(BaseModel):
    """Environmental fields sampled at a dated observed iceberg position."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime
    iceberg_id: str
    iceberg_latitude: float = Field(ge=-90, le=90)
    iceberg_longitude: float = Field(ge=-180, le=180)
    ocean_u: float | None
    ocean_v: float | None
    ocean_depth: float
    wind_u10: float | None = None
    wind_v10: float | None = None
    sea_ice_concentration: float | None = None
    source_ocean: str
    source_wind: str | None = None
    source_sea_ice: str | None = None
    classification_ocean: ScientificClassification = ScientificClassification.ANALYSIS
    classification_wind: ScientificClassification | None = None
    classification_sea_ice: ScientificClassification | None = None
    spatial_interpolation_method: str = "bilinear on regular latitude/longitude grid"
    temporal_interpolation_method: str = "linear between bracketing source timestamps"
    quality_flags: list[str]
    provenance: dict[str, str]
