"""Report deterministic connectivity and offline policy scenarios."""

import json

from backend.operations.connectivity.manager import MANAGER
from backend.operations.connectivity.models import ConnectivityState
from backend.operations.connectivity.sync import QUEUE

if __name__ == "__main__":
    scenarios = []
    for state in (
        ConnectivityState.ONLINE,
        ConnectivityState.SATCOM_LIMITED,
        ConnectivityState.OFFLINE,
    ):
        status = MANAGER.override(state)
        scenarios.append(
            {
                "connectivity": status.model_dump(mode="json"),
                "sync_tasks": [task.model_dump(mode="json") for task in QUEUE.ordered()],
            }
        )
    print(json.dumps(scenarios, indent=2))
