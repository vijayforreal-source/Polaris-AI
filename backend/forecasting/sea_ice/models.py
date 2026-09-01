from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class BaselineName(StrEnum):
    PERSISTENCE = "PERSISTENCE"
    SEASONAL_CLIMATOLOGY = "SEASONAL_CLIMATOLOGY"
    LINEAR_TENDENCY = "LINEAR_TENDENCY"
    CLIMATOLOGY_ANOMALY = "CLIMATOLOGY_ANOMALY"


class SeaIceDomain(BaseModel):
    minimum_longitude: float = Field(ge=-180, le=180)
    maximum_longitude: float = Field(ge=-180, le=180)
    minimum_latitude: float = Field(ge=-90, le=90)
    maximum_latitude: float = Field(ge=-90, le=90)
    context_buffer_degrees: float = Field(gt=0)
    bharati_latitude: float = Field(ge=-90, le=90)
    bharati_longitude: float = Field(ge=-180, le=180)
    bharati_neighborhood_degrees: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "SeaIceDomain":
        if self.minimum_longitude >= self.maximum_longitude:
            raise ValueError("longitude bounds must be ordered")
        if self.minimum_latitude >= self.maximum_latitude:
            raise ValueError("latitude bounds must be ordered")
        return self


BHARATI_FORECAST_DOMAIN = SeaIceDomain(
    minimum_longitude=67.0,
    maximum_longitude=87.0,
    minimum_latitude=-73.5,
    maximum_latitude=-63.0,
    context_buffer_degrees=3.0,
    bharati_latitude=-69.4068,
    bharati_longitude=76.1953,
    bharati_neighborhood_degrees=1.0,
)


class SeaIceSplit(BaseModel):
    name: str
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self) -> "SeaIceSplit":
        if self.start > self.end:
            raise ValueError("split start must not follow split end")
        return self


TRAIN_SPLIT = SeaIceSplit(name="TRAIN", start=date(2015, 1, 1), end=date(2023, 12, 31))
VALIDATION_SPLIT = SeaIceSplit(
    name="VALIDATION", start=date(2024, 1, 1), end=date(2024, 12, 31)
)
TEST_SPLIT = SeaIceSplit(name="LOCKED_TEST", start=date(2025, 1, 1), end=date(2026, 8, 16))


class ForecastMetrics(BaseModel):
    valid_pixel_count: int
    mae_percentage_points: float
    rmse_percentage_points: float
    mean_bias_percentage_points: float
    precision_15_percent: float | None = None
    recall_15_percent: float | None = None
    f1_15_percent: float | None = None
