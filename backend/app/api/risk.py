from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from backend.navigation.risk import service
from backend.navigation.risk.engine import serialize_field
from backend.navigation.risk.vessel import PROFILES, VesselProfile, get_vessel

router = APIRouter(prefix="/api/risk", tags=["dynamic-risk"])


def _call(operation):
    try:
        return operation()
    except service.RiskUnavailable as error:
        raise HTTPException(503, detail={"state": "UNAVAILABLE", "reason": str(error)}) from error
    except ValueError as error:
        raise HTTPException(422, detail=str(error)) from error


@router.get("/status")
def status():
    return service.status()


@router.get("/vessels")
def vessels():
    return {
        "vessels": [v.model_dump(mode="json") for v in PROFILES.values()],
        "limitation": "Configured profiles are simulated, not real vessel certifications.",
    }


@router.get("/grid")
def grid(
    horizon_hours: float = Query(0, ge=0, le=720, allow_inf_nan=False),
    vessel_id: str = "simulated-research",
    initialization_time: AwareDatetime | None = None,
):
    return _call(
        lambda: serialize_field(
            service.get_risk_field(initialization_time, horizon_hours, get_vessel(vessel_id))
        )
    )


@router.get("/point")
def point(
    lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    lon: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    horizon_hours: float = Query(0, ge=0, le=720, allow_inf_nan=False),
    vessel_id: str = "simulated-research",
    initialization_time: AwareDatetime | None = None,
):
    return _call(
        lambda: service.get_point_risk(
            lat, lon, horizon_hours, get_vessel(vessel_id), initialization_time
        )
    )


class CustomPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    horizon_hours: float = Field(0, ge=0, le=720)
    initialization_time: AwareDatetime | None = None
    vessel_profile: VesselProfile


@router.post("/point")
def custom_point(request: CustomPointRequest):
    return _call(
        lambda: service.get_point_risk(
            request.latitude,
            request.longitude,
            request.horizon_hours,
            request.vessel_profile,
            request.initialization_time,
        )
    )
