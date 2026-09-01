from fastapi import APIRouter

from backend.iceberg.engine.models import TrajectoryRequest, TrajectoryResponse
from backend.iceberg.engine.service import run_historical_hindcast

router = APIRouter(prefix="/api/trajectory", tags=["trajectory"])


@router.post("/hindcast", response_model=TrajectoryResponse)
async def trajectory_hindcast(request: TrajectoryRequest) -> TrajectoryResponse:
    return run_historical_hindcast(request)
