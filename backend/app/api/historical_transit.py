from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from backend.historical_transit.corridor import build_corridor
from backend.historical_transit.models import summary
from backend.historical_transit.store import load_voyages

router = APIRouter(prefix="/api/historical-transit", tags=["historical-transit"])
LIMITATIONS = [
    "Historical vessel track - not a current safety guarantee.",
    "Historical transit confidence is not a safety probability.",
    "Current environmental safety must be evaluated separately.",
    "Verification records source review and track plausibility, not navigation approval.",
]


@router.get("/status")
def status():
    voyages, errors = load_voyages()
    now = datetime.now(UTC)
    reports = [summary(v, now=now) for v in voyages]
    usable = [v for v in reports if v["renderable"]]
    return {
        "available": bool(usable),
        "voyage_count": len(reports),
        "verified_voyage_count": len(usable),
        "latest_transit": max((v["last_transit_time"] for v in usable), default=None),
        "data_sources": sorted({v["source"] for v in usable}),
        "track_quality": {
            q: sum(v["track_quality"] == q for v in reports)
            for q in ("VERIFIED", "USABLE_WITH_GAPS", "LOW_CONFIDENCE", "REJECTED")
        },
        "classification": "OBSERVATION",
        "limitations": LIMITATIONS,
        "load_errors": errors,
        "message": None if usable else "No verified historical voyage tracks are currently loaded.",
    }


@router.get("/voyages")
def voyages(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    records, errors = load_voyages()
    now = datetime.now(UTC)
    return {
        "voyages": [summary(v, now=now) for v in records[offset : offset + limit]],
        "total": len(records),
        "offset": offset,
        "limit": limit,
        "load_errors": errors,
    }


@router.get("/voyage/{voyage_id}")
def voyage(voyage_id: str):
    records, _ = load_voyages()
    for record in records:
        if record.voyage_id == voyage_id:
            return summary(record) | {
                "points": [p.model_dump(mode="json") for p in record.points],
                "limitations": LIMITATIONS,
            }
    raise HTTPException(status_code=404, detail="Historical voyage not found")


@router.get("/corridor")
def corridor(
    tau_days: float = Query(180, gt=0, le=36500, allow_inf_nan=False),
    cell_degrees: float = Query(1, ge=0.25, le=10, allow_inf_nan=False),
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
):
    records, errors = load_voyages()
    product = build_corridor(records, tau_days=tau_days, cell_degrees=cell_degrees)
    cells = product["cells"]
    return product | {
        "cells": cells[offset : offset + limit],
        "total": len(cells),
        "offset": offset,
        "limit": limit,
        "load_errors": errors,
    }
