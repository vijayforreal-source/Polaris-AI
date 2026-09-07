from fastapi import APIRouter, HTTPException

from backend.navigation.replanning import service
from backend.navigation.replanning.models import ActivateRequest, PositionRequest

router = APIRouter(prefix="/api/replanning", tags=["dynamic-replanning"])


def _call(operation):
    try:
        value = operation()
        return value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    except ValueError as error:
        status = 404 if str(error) == "NO_ACTIVE_VOYAGE" else 422
        raise HTTPException(status, detail=str(error)) from error


@router.get("/status")
def status():
    return service.status()


@router.post("/activate")
def activate(request: ActivateRequest):
    return _call(lambda: service.activate(request.voyage_id, request.route, request.current_time))


@router.get("/active")
def active():
    value = service.active()
    if value is None:
        raise HTTPException(404, detail="NO_ACTIVE_VOYAGE")
    return value.model_dump(mode="json")


@router.post("/position")
def position(request: PositionRequest):
    return _call(
        lambda: service.update_position(request.latitude, request.longitude, request.current_time)
    )


@router.post("/evaluate")
def evaluate():
    return _call(service.evaluate)


@router.post("/replan")
def replan():
    return _call(service.replan)


@router.get("/events")
def events():
    return {"events": [event.model_dump(mode="json") for event in service.EVENTS]}


@router.post("/accept")
def accept(event_id: str, candidate_route_id: str):
    return _call(lambda: service.accept(event_id, candidate_route_id))
