"""Repeatable local benchmark; values are measurements, not SLAs."""

import json
import platform
import statistics
import time
from datetime import UTC, datetime

from backend.navigation.risk import service as risk_service
from backend.navigation.risk.vessel import get_vessel
from backend.navigation.routing.engine import RoutePlanner
from backend.operations.service import health


def measure(function, iterations=3):
    values = []
    failures = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            function()
        except Exception as error:
            failures.append(type(error).__name__)
        values.append((time.perf_counter() - start) * 1000)
    values.sort()
    return {
        "iterations": iterations,
        "min_ms": values[0],
        "median_ms": statistics.median(values),
        "p95_ms": values[min(len(values) - 1, max(0, int(len(values) * 0.95) - 1))],
        "max_ms": values[-1],
        "failures": failures,
    }


if __name__ == "__main__":
    vessel = get_vessel("simulated-research")

    def grid():
        return risk_service.get_risk_field(horizon_hours=0, vessel_profile=vessel)

    def planner(objective):
        return RoutePlanner(
            lambda horizon: risk_service.get_risk_field(
                horizon_hours=horizon, vessel_profile=vessel
            ),
            vessel,
            datetime.now(UTC),
        ).plan((-69.4, 76.2), (-68.8, 77.1), objective)
    results = {
        "hardware": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
        },
        "measurements_ms": {
            "operations_status": measure(health),
            "risk_grid": measure(grid),
            "routes": {
                objective: measure(lambda objective=objective: planner(objective))
                for objective in ("SAFE", "FAST", "ECO", "BALANCED")
            },
        },
    }
    print(json.dumps(results, indent=2, default=str))
