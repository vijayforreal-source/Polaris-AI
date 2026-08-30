import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging

settings = get_settings()
configure_logging(logging.DEBUG if settings.debug else logging.INFO)

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "system": settings.app_name,
        "status": "operational",
        "phase": "Day 1 - Foundation",
    }

