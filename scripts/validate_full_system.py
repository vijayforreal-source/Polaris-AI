"""Compact integrated validation report for the local prototype."""

import json

from backend.demo.scenarios import scenario_report
from backend.operations.connectivity.manager import MANAGER
from backend.operations.connectivity.models import ConnectivityState
from backend.operations.connectivity.sync import QUEUE
from backend.operations.service import current_snapshot, health

if __name__ == "__main__":
    report = health()
    MANAGER.override(ConnectivityState.OFFLINE)
    offline = {"connectivity": MANAGER.status().state, "cached_tasks": len(QUEUE.tasks)}
    MANAGER.override(ConnectivityState.ONLINE)
    print(
        json.dumps(
            {
                "status": report["overall_status"],
                "snapshot": current_snapshot().snapshot_id,
                "capabilities": report["capabilities"],
                "offline": offline,
                "scenarios": scenario_report(),
            },
            indent=2,
            default=str,
        )
    )
