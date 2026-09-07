from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class IcebergState(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    iceberg_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_at: AwareDatetime
    size_radius_km: float | None = Field(None, ge=0)
    uncertainty_radius_km: float = Field(0, ge=0)
    date_precision_days: float = Field(0, ge=0, le=1)
    source: str
    # A provider may supply an actual prediction for precisely this valid time.
    predicted_latitude: float | None = Field(None, ge=-90, le=90)
    predicted_longitude: float | None = Field(None, ge=-180, le=180)
    prediction_valid_time: AwareDatetime | None = None


@dataclass
class RiskInputs:
    latitude: np.ndarray
    longitude: np.ndarray
    ocean_mask: np.ndarray
    sic: dict[int, np.ndarray]
    initialization_time: datetime
    as_of: datetime
    sea_ice_state: str = "AVAILABLE"
    forecast_mode: str = "MODEL_PREDICTION"
    sea_ice_age_days: float = 0
    icebergs: list[IcebergState] = field(default_factory=list)
    iceberg_state: str = "AVAILABLE"
    iceberg_report_age_days: float = 0
    iceberg_coverage_incomplete: bool = True
    historical_cells: list[dict] = field(default_factory=list)
    historical_state: str = "NO_VERIFIED_DATA"
    mae_pp: tuple[float, float, float] = (2.8779149296126323, 4.0666596431003255, 4.788987137609075)
    provenance: dict = field(default_factory=dict)


@dataclass
class RiskField:
    latitude: np.ndarray
    longitude: np.ndarray
    risk_grid: np.ndarray
    navigation_cost_grid: np.ndarray
    navigable_mask: np.ndarray
    risk_category_grid: np.ndarray
    dominant_factor_grid: np.ndarray
    hard_constraint_grid: np.ndarray
    component_grids: dict[str, np.ndarray]
    sic_percent: np.ndarray
    metadata: dict
