import math
from datetime import UTC, datetime

from .models import Voyage, assess


def recency_score(age_days: float, tau_days: float = 180) -> float:
    if not math.isfinite(age_days) or age_days < 0:
        raise ValueError("Age must be finite and non-negative")
    if not math.isfinite(tau_days) or tau_days <= 0:
        raise ValueError("Tau must be finite and positive")
    return math.exp(-age_days / tau_days)


def build_corridor(
    voyages: list[Voyage],
    *,
    now: datetime | None = None,
    tau_days: float = 180,
    cell_degrees: float = 1,
) -> dict:
    now = now or datetime.now(UTC)
    recency_score(0, tau_days)
    if not math.isfinite(cell_degrees) or not 0.25 <= cell_degrees <= 10:
        raise ValueError("Cell width must be between 0.25 and 10 degrees")
    cells = {}
    for voyage in voyages:
        report = assess(voyage, now=now)
        if not report["renderable"]:
            continue
        gap_indices = {gap["after_point"] for gap in report["data_gaps"]}
        previous_cell = None
        for index, (a, b) in enumerate(zip(voyage.points, voyage.points[1:], strict=False)):
            if index in gap_indices:
                previous_cell = None
                continue
            delta_lon = (b.longitude - a.longitude + 180) % 360 - 180
            lon = (a.longitude + delta_lon / 2 + 180) % 360 - 180
            lat = (a.latitude + b.latitude) / 2
            key = (
                math.floor((lon + 180) / cell_degrees),
                min(math.floor((lat + 90) / cell_degrees), math.ceil(180 / cell_degrees) - 1),
            )
            cell = cells.setdefault(
                key, {"transit_count": 0, "voyages": set(), "latest": b.timestamp_utc}
            )
            if key != previous_cell:
                cell["transit_count"] += 1
            cell["voyages"].add(voyage.voyage_id)
            cell["latest"] = max(cell["latest"], b.timestamp_utc)
            previous_cell = key
    output = []
    for (x, y), cell in sorted(cells.items()):
        age = max(0, (now - cell["latest"]).total_seconds() / 86400)
        output.append(
            {
                "cell_id": f"{x}:{y}",
                "bbox": [
                    x * cell_degrees - 180,
                    y * cell_degrees - 90,
                    min(180, (x + 1) * cell_degrees - 180),
                    min(90, (y + 1) * cell_degrees - 90),
                ],
                "transit_count": cell["transit_count"],
                "unique_voyages": len(cell["voyages"]),
                "latest_transit_time": cell["latest"].isoformat(),
                "age_days": age,
                "recency_score": recency_score(age, tau_days),
            }
        )
    return {
        "classification": "DERIVED_HISTORICAL_EVIDENCE",
        "cells": output,
        "tau_days": tau_days,
        "cell_degrees": cell_degrees,
        "method": "Observed segment midpoints binned by degrees; repeated consecutive bins "
        "count once per passage. Long gaps excluded. Not a complete swept corridor.",
        "limitation": "Historical transit confidence is not a safety probability.",
    }
