from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

from .manager import MANAGER
from .models import BandwidthClass, ConnectivityState, SyncPriority, SyncStatus, SyncTask


class SyncQueue:
    def __init__(self):
        self.tasks: dict[str, SyncTask] = {}
        self.lock = RLock()
        self.max_attempts = 3

    def enqueue(
        self,
        source_id,
        task_type,
        priority=SyncPriority.NORMAL,
        *,
        size=BandwidthClass.UNKNOWN,
        requires_online=True,
        payload=None,
    ):
        task = SyncTask(
            task_id=f"sync-{uuid4().hex[:10]}",
            source_id=source_id,
            task_type=task_type,
            priority=priority,
            created_at=datetime.now(UTC),
            estimated_size_class=size,
            requires_online=requires_online,
            payload_metadata=payload or {},
            provenance={"source": "local sync queue"},
        )
        self.tasks[task.task_id] = task
        return task

    def ordered(self):
        order = {
            SyncPriority.CRITICAL: 0,
            SyncPriority.HIGH: 1,
            SyncPriority.NORMAL: 2,
            SyncPriority.LOW: 3,
        }
        return sorted(self.tasks.values(), key=lambda task: (order[task.priority], task.created_at))

    def allowed(self, task: SyncTask):
        state = MANAGER.status().state
        if not task.requires_online:
            return True
        if state == ConnectivityState.OFFLINE:
            return False
        if state == ConnectivityState.SATCOM_LIMITED:
            return task.priority in {SyncPriority.CRITICAL, SyncPriority.HIGH}
        return state == ConnectivityState.ONLINE

    def run(self):
        results = []
        for task in self.ordered():
            if task.status not in {SyncStatus.PENDING, SyncStatus.DEFERRED, SyncStatus.FAILED}:
                continue
            if not self.allowed(task):
                task.status = SyncStatus.DEFERRED
                task.error = (
                    "DEFERRED_OFFLINE"
                    if MANAGER.status().state == ConnectivityState.OFFLINE
                    else "DEFERRED_BANDWIDTH_POLICY"
                )
                results.append(task)
                continue
            if task.attempts >= self.max_attempts:
                task.status = SyncStatus.FAILED
                task.error = "MAX_RETRIES_EXCEEDED"
                results.append(task)
                continue
            task.status = SyncStatus.RUNNING
            task.attempts += 1
            task.last_attempt = datetime.now(UTC)
            task.status = SyncStatus.SUCCESS
            task.error = None
            results.append(task)
        return results

    def retry(self, task_id):
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("SYNC_TASK_NOT_FOUND")
        task.status = SyncStatus.PENDING
        task.next_retry = datetime.now(UTC) + timedelta(seconds=min(300, 2**task.attempts * 10))
        return task


QUEUE = SyncQueue()
