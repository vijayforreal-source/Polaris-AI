from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskConfig(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    classification: str = "ENGINEERING_DEFAULT / NOT_NAVIGATIONAL_CERTIFICATION"
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10)
    category_edges: tuple[float, ...] = (0.20, 0.40, 0.60, 0.80)
    sic_breakpoints: tuple[float, ...] = (0, 15, 40, 70, 100)
    sic_hazards: tuple[float, ...] = (0, 0.10, 0.40, 0.80, 1)
    reference_recommended_sic: float = Field(40, gt=0, le=100)
    maximum_sic_age_days: float = Field(3, gt=0)
    iceberg_stale_days: float = Field(7, gt=0)
    iceberg_unavailable_days: float = Field(30, gt=0)
    iceberg_exclusion_km: float = Field(2, gt=0)
    iceberg_caution_km: float = Field(20, gt=0)
    unknown_iceberg_size_km: float = Field(10, gt=0)
    iceberg_age_growth_km_per_day: float = Field(5, ge=0)
    iceberg_horizon_growth_km_per_hour: float = Field(1, ge=0)
    iceberg_uncertainty_scale_km: float = Field(100, gt=0)
    mae_uncertainty_scale_pp: float = Field(20, gt=0)
    observation_uncertainty: float = Field(0.05, ge=0, le=1)
    persistence_penalty: float = Field(0.20, ge=0, le=1)
    unknown_vessel_penalty: float = Field(0.35, ge=0, le=1)
    incomplete_vessel_penalty: float = Field(0.10, ge=0, le=1)
    iceberg_coverage_penalty: float = Field(0.10, ge=0, le=1)
    sic_age_penalty_max: float = Field(0.40, ge=0, le=1)
    iceberg_age_penalty_max: float = Field(0.30, ge=0, le=1)
    uncertainty_cost_weight: float = Field(0.25, ge=0)
    experience_bonus_max: float = Field(0.08, ge=0, le=0.10)
    experience_risk_ceiling: float = Field(0.40, gt=0, le=1)
    historical_tau_days: float = Field(180, gt=0)
    historical_frequency_scale: float = Field(3, gt=0)

    @model_validator(mode="after")
    def ordered_and_normalized(self):
        if any(w < 0 for w in self.weights) or abs(sum(self.weights) - 1) > 1e-9:
            raise ValueError("Risk weights must be non-negative and sum to one")
        for values in (self.category_edges, self.sic_breakpoints, self.sic_hazards):
            if any(b <= a for a, b in zip(values, values[1:], strict=False)):
                raise ValueError("Thresholds must strictly increase")
        if (
            len(self.category_edges) != 4
            or not 0 < self.category_edges[0] < self.category_edges[-1] < 1
        ):
            raise ValueError("Four category boundaries must lie strictly inside (0,1)")
        if len(self.sic_breakpoints) != len(self.sic_hazards):
            raise ValueError("SIC breakpoints and hazard values must align")
        if self.sic_breakpoints[0] != 0 or self.sic_breakpoints[-1] != 100:
            raise ValueError("SIC mapping must span 0 through 100 percent")
        if self.sic_hazards[0] < 0 or self.sic_hazards[-1] > 1:
            raise ValueError("SIC hazard values must lie in [0,1]")
        if self.iceberg_caution_km <= self.iceberg_exclusion_km:
            raise ValueError("Caution radius must exceed exclusion radius")
        if self.iceberg_unavailable_days <= self.iceberg_stale_days:
            raise ValueError("Unavailable iceberg age must exceed stale age")
        return self


CONFIG = RiskConfig()
CATEGORY_LABELS = ("LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL")
DOMINANT_LABELS = (
    "SEA_ICE",
    "ICEBERG",
    "UNCERTAINTY",
    "VESSEL_CONSTRAINT",
    "LAND",
    "DATA_UNAVAILABLE",
)
HARD_REASONS = {
    1: "LAND_OR_INVALID_OCEAN_MASK",
    2: "INVALID_GEOGRAPHIC_CELL",
    4: "MISSING_OR_INVALID_SEA_ICE",
    8: "STALE_SEA_ICE",
    16: "ICEBERG_LAYER_UNAVAILABLE",
    32: "ICEBERG_EXCLUSION_ZONE",
    64: "VESSEL_SIC_LIMIT",
    128: "VESSEL_CAPABILITY_UNKNOWN",
    256: "FORECAST_HORIZON_EXCEEDED",
    512: "ENVIRONMENT_UNAVAILABLE",
}
