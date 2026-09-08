"""Reset only in-memory demo/connectivity state; never deletes scientific data."""

from backend.operations import service
from backend.operations.connectivity.manager import MANAGER
from backend.operations.connectivity.sync import QUEUE

if __name__ == "__main__":
    service.MISSIONS.clear()
    service.EVENTS.clear()
    QUEUE.tasks.clear()
    MANAGER.clear_override()
    print("DEMO STATE RESET: missions, events, sync queue, connectivity override")
