from pydantic import BaseModel, ConfigDict, Field


class ReplanningConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    classification: str = "ENGINEERING_DEFAULT"
    minimum_risk_improvement: float = Field(0.05, ge=0, le=1)
    minimum_cumulative_risk_improvement_pct: float = Field(10, ge=0, le=100)
    minimum_eta_improvement_pct: float = Field(5, ge=0, le=100)
    minimum_eco_improvement_pct: float = Field(5, ge=0, le=100)
    cooldown_minutes: float = Field(30, ge=0)
    route_similarity_threshold: float = Field(0.85, ge=0, le=1)


CONFIG = ReplanningConfig()
