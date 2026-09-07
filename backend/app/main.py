import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.api.historical_transit import router as historical_transit_router
from backend.app.api.icebergs import router as iceberg_router
from backend.app.api.sea_ice import router as sea_ice_router
from backend.app.api.trajectory import router as trajectory_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging

settings = get_settings()
configure_logging(logging.DEBUG if settings.debug else logging.INFO)

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        dict.fromkeys(
            [settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"]
        )
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(historical_transit_router)
app.include_router(sea_ice_router)
app.include_router(iceberg_router)
app.include_router(trajectory_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "system": settings.app_name,
        "status": "operational",
        "phase": "Checkpoint 3 - Sea-ice prediction engine; historical champion v0.3",
    }
