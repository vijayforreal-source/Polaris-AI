# Checkpoint 8 — External adapters, connectivity, and offline sync

POLARIS connects to the vessel’s onboard network. That network may use cellular, shore Wi-Fi, VSAT, Starlink, Iridium, or other communications infrastructure. POLARIS does not directly control satellite hardware.

Connectivity is represented as `ONLINE`, `SATCOM_LIMITED`, `OFFLINE`, or `UNKNOWN`, with explicit bandwidth policy and a manual test override. Offline operation continues locally where cached scientific data remains valid: maps, mission state, historical transit, local risk, routing, replanning, and manual telemetry. Connectivity loss alone does not block local inference; stale or invalid critical data does.

The cache index tracks source, version, checksum, size, freshness, offline usability, and last-known-good status. Cache validation rejects missing or checksum-mismatched artifacts without deleting the previous valid artifact. The synchronization queue uses CRITICAL/HIGH/NORMAL/LOW priorities. Limited connectivity runs critical/high tasks and defers low priority; offline mode defers all online-required tasks. Retry attempts are bounded.

External adapters expose status, metadata, provenance, cache support, and payload size without forcing existing scientific modules to change. Sea ice, USNIC icebergs, historical transit, and ERA5 reanalysis adapters are explicit. ERA5 remains historical reanalysis, not future weather. A future weather provider, AIS provider, and onboard GPS provider remain unconfigured hooks with no credentials or network calls.

Mission Control displays connection state, manual override status, pending synchronization, and cached source count alongside operational health, mission, routing, and replanning panels. The existing local vector coastline remains the offline basemap fallback; no remote tile dependency is introduced.

These features are a research prototype. There is no live AIS, GPS socket, satellite stream, autonomous control, cloud deployment, or production synchronization service.
