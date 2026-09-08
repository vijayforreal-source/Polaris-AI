import hashlib
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from .models import CacheEntry


class CacheIndex:
    def __init__(self):
        self.entries: dict[str, CacheEntry] = {}
        self.lock = RLock()

    def register(self, entry: CacheEntry) -> CacheEntry:
        with self.lock:
            self.entries[entry.source_id] = entry
        return entry

    def validate(self, source_id: str) -> CacheEntry:
        entry = self.entries.get(source_id)
        if entry is None:
            raise ValueError("CACHE_UNAVAILABLE")
        if entry.cache_path and entry.checksum:
            path = Path(entry.cache_path)
            if not path.is_file():
                return entry.model_copy(
                    update={
                        "valid": False,
                        "usable_offline": False,
                        "error": "CACHE_ARTIFACT_MISSING",
                    }
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry.checksum:
                return entry.model_copy(
                    update={"valid": False, "usable_offline": False, "error": "CHECKSUM_MISMATCH"}
                )
        return entry

    def status(self) -> list[CacheEntry]:
        return [self.validate(source_id) for source_id in self.entries]


CACHE = CacheIndex()
now = datetime.now(UTC)
for source_id, version in (
    ("SEA_ICE_OBSERVATION", "local-artifact"),
    ("SEA_ICE_FORECAST", "local-artifact"),
    ("ICEBERG_REGISTRY", "local-artifact"),
    ("HISTORICAL_TRANSIT", "local-store"),
):
    CACHE.register(
        CacheEntry(
            source_id=source_id,
            cache_path=None,
            cached_at=now,
            version=version,
            size_bytes=0,
            freshness="STALE",
            usable_offline=True,
            last_known_good=True,
        )
    )
