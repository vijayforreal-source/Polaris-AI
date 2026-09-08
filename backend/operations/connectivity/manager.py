from datetime import UTC, datetime
from threading import RLock

from .models import BandwidthClass, ConnectivityState, ConnectivityStatus


class ConnectivityManager:
    def __init__(self):
        now = datetime.now(UTC)
        self._status = ConnectivityStatus(
            state=ConnectivityState.UNKNOWN,
            last_checked_at=now,
            estimated_bandwidth_class=BandwidthClass.UNKNOWN,
            network_source="NOT_MEASURED",
            reason="Connectivity has not been measured.",
            provenance={"source": "local application state"},
        )
        self._override: ConnectivityState | None = None
        self._lock = RLock()

    def status(self) -> ConnectivityStatus:
        with self._lock:
            return self._status

    def override(self, state: ConnectivityState) -> ConnectivityStatus:
        with self._lock:
            self._override = state
            now = datetime.now(UTC)
            bandwidth = (
                BandwidthClass.HIGH
                if state == ConnectivityState.ONLINE
                else BandwidthClass.LOW
                if state == ConnectivityState.SATCOM_LIMITED
                else BandwidthClass.UNKNOWN
            )
            self._status = self._status.model_copy(
                update={
                    "state": state,
                    "last_checked_at": now,
                    "last_online_at": now
                    if state == ConnectivityState.ONLINE
                    else self._status.last_online_at,
                    "last_offline_at": now
                    if state == ConnectivityState.OFFLINE
                    else self._status.last_offline_at,
                    "estimated_bandwidth_class": bandwidth,
                    "network_source": "MANUAL_TEST_OVERRIDE",
                    "reason": "Manual test/demo connectivity override.",
                    "manual_override": True,
                    "provenance": {
                        "classification": "MANUAL_INPUT",
                        "source": "MANUAL_TEST_OVERRIDE",
                    },
                }
            )
            return self._status

    def refresh(self) -> ConnectivityStatus:
        with self._lock:
            if self._override is not None:
                return self._status
            now = datetime.now(UTC)
            self._status = self._status.model_copy(
                update={
                    "state": ConnectivityState.UNKNOWN,
                    "last_checked_at": now,
                    "estimated_bandwidth_class": BandwidthClass.UNKNOWN,
                    "network_source": "LOCAL_DETECTION_NOT_CONFIGURED",
                    "reason": "No configured probe endpoint; state is unknown rather than "
                    "falsely online.",
                }
            )
            return self._status

    def clear_override(self) -> ConnectivityStatus:
        self._override = None
        return self.refresh()


MANAGER = ConnectivityManager()
