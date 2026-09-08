from pydantic import BaseModel, ConfigDict, Field


class FreshnessConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    aging_fraction: float = Field(0.5, gt=0, lt=1)
    stale_multiplier: float = Field(1.5, gt=1)
    expired_multiplier: float = Field(3, gt=1)
    position_material_change_km: float = Field(5, gt=0)


CONFIG = FreshnessConfig()
