from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a machine-readable liveness response."""
    return {"status": "healthy"}

