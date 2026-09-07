"""Deterministic engineering summary for the Checkpoint 4 risk field."""

import json
from datetime import UTC, datetime

import numpy as np

from backend.navigation.risk.service import get_risk_field
from backend.navigation.risk.vessel import get_vessel


def main():
    now = datetime.now(UTC)
    reports = []
    for horizon in (0, 24, 48, 72):
        field = get_risk_field(
            horizon_hours=horizon, vessel_profile=get_vessel("simulated-research"), now=now
        )
        reports.append(
            {
                "horizon_hours": horizon,
                "summary": {
                    "cell_count": int(field.risk_grid.size),
                    "blocked_cell_count": int((~field.navigable_mask).sum()),
                    "risk_min": float(field.risk_grid.min()),
                    "risk_max": float(field.risk_grid.max()),
                    "risk_mean": float(field.risk_grid.mean()),
                    "category_counts": {
                        name: int((field.risk_category_grid == i).sum())
                        for i, name in enumerate(field.metadata["category_labels"])
                    },
                    "dominant_factor_counts": {
                        name: int((field.dominant_factor_grid == i).sum())
                        for i, name in enumerate(field.metadata["dominant_factor_labels"])
                    },
                    "mean_components": {
                        key: float(np.nanmean(value))
                        for key, value in field.component_grids.items()
                    },
                },
                "state": field.metadata["state"],
                "provenance": field.metadata["provenance"],
            }
        )
    print(
        json.dumps(
            {
                "classification": "ENGINEERING_VALIDATION_ONLY",
                "generated_at": now.isoformat(),
                "reports": reports,
                "limitation": "Not navigational safety validation.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
