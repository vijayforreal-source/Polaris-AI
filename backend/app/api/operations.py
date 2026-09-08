from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from backend.operations import service
from backend.operations.models import Position

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/status")
def status():
    return service.health()


@router.get("/sources")
def sources():
    return {"sources": [source.model_dump(mode="json") for source in service.source_registry()]}


@router.get("/snapshot")
def snapshot():
    return service.current_snapshot().model_dump(mode="json")


@router.get("/capabilities")
def capability_matrix():
    return {"capabilities": service.capabilities()}


@router.get("/lineage")
def lineage():
    return {
        "risk": [
            "SEA_ICE_FORECAST",
            "ICEBERG_REGISTRY",
            "VESSEL_POSITION",
            "HISTORICAL_TRANSIT",
            "RISK_ENGINE",
        ],
        "route": ["RISK_ENGINE", "VESSEL_POSITION", "ROUTING_ENGINE"],
        "replan": ["ROUTING_ENGINE", "REPLANNING_ENGINE", "ENVIRONMENT_SNAPSHOT"],
    }


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    vessel_id: str = Field(min_length=1, max_length=80)
    origin: dict
    destination: dict
    planned_departure: AwareDatetime | None = None
    objective: str = "BALANCED"
    notes: str | None = None


@router.post("/missions")
def create_mission(request: MissionCreate):
    return service.create_mission(request.model_dump(mode="json")).model_dump(mode="json")


@router.get("/missions")
def missions():
    return {"missions": [mission.model_dump(mode="json") for mission in service.MISSIONS.values()]}


def _mission(mission_id, target):
    try:
        return service.transition(mission_id, target).model_dump(mode="json")
    except ValueError as error:
        raise HTTPException(
            404 if str(error) == "MISSION_NOT_FOUND" else 422,
            detail={"error_code": str(error), "message": str(error)},
        ) from error


@router.get("/missions/{mission_id}")
def get_mission(mission_id: str):
    mission = service.MISSIONS.get(mission_id)
    if mission is None:
        raise HTTPException(
            404, detail={"error_code": "MISSION_NOT_FOUND", "message": "Mission not found"}
        )
    return mission.model_dump(mode="json")


@router.post("/missions/{mission_id}/plan")
def plan_mission(mission_id: str):
    return _mission(mission_id, "PLANNED")


@router.post("/missions/{mission_id}/activate")
def activate_mission(mission_id: str):
    return _mission(mission_id, "ACTIVE")


@router.post("/missions/{mission_id}/pause")
def pause_mission(mission_id: str):
    return _mission(mission_id, "PAUSED")


@router.post("/missions/{mission_id}/resume")
def resume_mission(mission_id: str):
    return _mission(mission_id, "ACTIVE")


@router.post("/missions/{mission_id}/complete")
def complete_mission(mission_id: str):
    return _mission(mission_id, "COMPLETED")


@router.post("/missions/{mission_id}/abort")
def abort_mission(mission_id: str):
    return _mission(mission_id, "ABORTED")


@router.post("/missions/{mission_id}/position")
def mission_position(mission_id: str, position: Position):
    return service.update_position(mission_id, position).model_dump(mode="json")


@router.get("/events")
def events():
    return {"events": [event.model_dump(mode="json") for event in service.EVENTS[-50:]]}
