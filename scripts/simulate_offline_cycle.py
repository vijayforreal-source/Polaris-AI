"""Synthetic connectivity/sync cycle; no external network calls."""

from backend.operations.connectivity.manager import MANAGER
from backend.operations.connectivity.models import ConnectivityState, SyncPriority
from backend.operations.connectivity.sync import QUEUE

if __name__ == "__main__":
    for state in (
        ConnectivityState.ONLINE,
        ConnectivityState.SATCOM_LIMITED,
        ConnectivityState.OFFLINE,
        ConnectivityState.ONLINE,
    ):
        MANAGER.override(state)
        if state == ConnectivityState.ONLINE and not QUEUE.tasks:
            QUEUE.enqueue("SEA_ICE_OBSERVATION", "metadata", SyncPriority.CRITICAL)
            QUEUE.enqueue("OPTIONAL_SAR", "imagery", SyncPriority.LOW)
        print(state, [task.status for task in QUEUE.run()])
