from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from backend.operations.connectivity.cache import CACHE
from backend.operations.connectivity.manager import MANAGER
from backend.operations.connectivity.models import ConnectivityState
from backend.operations.connectivity.sync import QUEUE

router = APIRouter(tags=["connectivity"])


@router.get("/api/connectivity/status")
def connectivity_status():
    return MANAGER.status().model_dump(mode="json")


@router.get("/api/connectivity/policy")
def connectivity_policy():
    return {
        "bandwidth_policy": {
            "HIGH": ["CRITICAL", "HIGH", "NORMAL", "LOW"],
            "MEDIUM": ["CRITICAL", "HIGH", "NORMAL"],
            "LOW": ["CRITICAL", "HIGH"],
            "OFFLINE": [],
        },
        "network_architecture": (
            "POLARIS connects to the vessel onboard network; it does not control "
            "satellite hardware."
        ),
    }


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: ConnectivityState


@router.post("/api/connectivity/override")
def connectivity_override(request: Override):
    return MANAGER.override(request.state).model_dump(mode="json")


@router.post("/api/connectivity/refresh")
def connectivity_refresh():
    return MANAGER.refresh().model_dump(mode="json")


@router.get("/api/sync/status")
def sync_status():
    return {
        "connectivity": MANAGER.status().state,
        "pending": sum(task.status in {"PENDING", "DEFERRED"} for task in QUEUE.tasks.values()),
        "tasks": len(QUEUE.tasks),
    }


@router.get("/api/sync/tasks")
def sync_tasks():
    return {"tasks": [task.model_dump(mode="json") for task in QUEUE.ordered()]}


@router.post("/api/sync/run")
def sync_run():
    return {"results": [task.model_dump(mode="json") for task in QUEUE.run()]}


@router.post("/api/sync/retry/{task_id}")
def sync_retry(task_id: str):
    try:
        return QUEUE.retry(task_id).model_dump(mode="json")
    except ValueError as error:
        raise HTTPException(
            404, detail={"error_code": str(error), "message": str(error)}
        ) from error


@router.get("/api/cache/status")
def cache_status():
    return {
        "sources": [entry.model_dump(mode="json") for entry in CACHE.status()],
        "cache_size_bytes": sum(entry.size_bytes for entry in CACHE.status()),
    }


@router.get("/api/cache/sources")
def cache_sources():
    return {"sources": [entry.model_dump(mode="json") for entry in CACHE.status()]}
