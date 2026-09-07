from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VesselProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    vessel_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    vessel_type: str = Field(min_length=1, max_length=80)
    length_m: float | None = Field(None, gt=0)
    beam_m: float | None = Field(None, gt=0)
    draft_m: float | None = Field(None, gt=0)
    nominal_speed_knots: float | None = Field(None, gt=0)
    ice_class: str | None = None
    polar_category: str | None = None
    maximum_recommended_sic_percent: float | None = Field(None, gt=0, le=100)
    maximum_operational_sic_percent: float | None = Field(None, gt=0, le=100)
    minimum_clearance_km: float | None = Field(None, ge=0)
    classification: Literal["SIMULATED_VESSEL_PROFILE", "USER_SUPPLIED_PROFILE"] = (
        "USER_SUPPLIED_PROFILE"
    )
    source: str = Field(min_length=1, max_length=500)
    provenance: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def ordered_limits(self):
        recommended = self.maximum_recommended_sic_percent
        maximum = self.maximum_operational_sic_percent
        if recommended is not None and maximum is not None and recommended >= maximum:
            raise ValueError("Recommended SIC must be strictly below operational SIC limit")
        return self


PROFILES = {
    "simulated-research": VesselProfile(
        vessel_id="simulated-research",
        name="Research Vessel - Simulated Profile",
        vessel_type="SIMULATED_RESEARCH",
        length_m=100,
        beam_m=20,
        draft_m=7,
        nominal_speed_knots=12,
        maximum_recommended_sic_percent=40,
        maximum_operational_sic_percent=70,
        minimum_clearance_km=2,
        classification="SIMULATED_VESSEL_PROFILE",
        source="POLARIS engineering demonstration",
        provenance="Invented capability scenario, not a real vessel or ice certification.",
    ),
    "simulated-open-water": VesselProfile(
        vessel_id="simulated-open-water",
        name="Open-water Vessel - Simulated Profile",
        vessel_type="SIMULATED_OPEN_WATER",
        length_m=80,
        beam_m=16,
        draft_m=5,
        nominal_speed_knots=10,
        maximum_recommended_sic_percent=15,
        maximum_operational_sic_percent=40,
        minimum_clearance_km=3,
        classification="SIMULATED_VESSEL_PROFILE",
        source="POLARIS engineering demonstration",
        provenance="Invented capability scenario, not a real vessel or ice certification.",
    ),
}


def get_vessel(vessel_id: str) -> VesselProfile:
    if vessel_id not in PROFILES:
        raise ValueError("UNKNOWN_VESSEL_PROFILE")
    return PROFILES[vessel_id]
