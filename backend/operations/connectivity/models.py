from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ConnectivityState(StrEnum):
    ONLINE = "ONLINE"
    SATCOM_LIMITED = "SATCOM_LIMITED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class BandwidthClass(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ConnectivityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: ConnectivityState
    last_checked_at: AwareDatetime
    last_online_at: AwareDatetime | None = None
    last_offline_at: AwareDatetime | None = None
    estimated_bandwidth_class: BandwidthClass
    network_source: str
    latency_ms: float | None = None
    reason: str
    manual_override: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class CacheEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    cache_path: str | None
    cached_at: AwareDatetime
    observation_time: AwareDatetime | None = None
    version: str
    checksum: str | None = None
    size_bytes: int = Field(ge=0)
    freshness: str
    usable_offline: bool
    expires_at: AwareDatetime | None = None
    valid: bool = True
    last_known_good: bool = True
    error: str | None = None


class SyncPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class SyncStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"


class SyncTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    source_id: str
    task_type: str
    priority: SyncPriority
    created_at: AwareDatetime
    status: SyncStatus = SyncStatus.PENDING
    attempts: int = 0
    last_attempt: AwareDatetime | None = None
    next_retry: AwareDatetime | None = None
    error: str | None = None
    payload_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_online: bool = True
    estimated_size_class: BandwidthClass = BandwidthClass.UNKNOWN
    provenance: dict[str, Any] = Field(default_factory=dict)


class ExternalProviderStatus(BaseModel):
    source_id: str
    configured: bool
    available: bool
    classification: str
    latest_timestamp: AwareDatetime | None = None
    cache: CacheEntry | None = None
    refresh_supported: bool
    estimated_size_class: BandwidthClass
    provenance: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
