from backend.operations.connectivity.manager import ConnectivityManager
from backend.operations.connectivity.models import ConnectivityState, SyncPriority, SyncStatus
from backend.operations.connectivity.sync import SyncQueue


def test_connectivity_overrides():
    manager = ConnectivityManager()
    assert manager.override(ConnectivityState.ONLINE).state == ConnectivityState.ONLINE
    assert manager.override(ConnectivityState.SATCOM_LIMITED).manual_override
    assert manager.override(ConnectivityState.OFFLINE).state == ConnectivityState.OFFLINE


def test_satcom_priority_and_offline_deferral():
    manager = ConnectivityManager()
    queue = SyncQueue()
    from backend.operations.connectivity import sync

    old = sync.MANAGER
    sync.MANAGER = manager
    try:
        critical = queue.enqueue("ICE", "metadata", SyncPriority.CRITICAL)
        low = queue.enqueue("SAR", "imagery", SyncPriority.LOW)
        manager.override(ConnectivityState.SATCOM_LIMITED)
        queue.run()
        assert critical.status == SyncStatus.SUCCESS and low.status == SyncStatus.DEFERRED
        manager.override(ConnectivityState.OFFLINE)
        queue.run()
        assert low.error == "DEFERRED_OFFLINE"
    finally:
        sync.MANAGER = old
