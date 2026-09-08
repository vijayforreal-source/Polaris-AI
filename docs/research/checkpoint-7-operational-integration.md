# Checkpoint 7 — Operational integration and data-pipeline hardening

Checkpoint 7 adds a centralized operational layer around the existing scientific and navigation services. It classifies source provenance, separates data freshness from software health, creates deterministic environment snapshots, reports capabilities, records operational events, and provides a lightweight mission lifecycle.

Freshness states are `FRESH`, `AGING`, `STALE`, `EXPIRED`, `UNAVAILABLE`, and `NOT_APPLICABLE`. Health states are `HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `ERROR`, and `NOT_CONFIGURED`. Existing Checkpoint 4 scientific staleness behavior remains authoritative; operational status wraps it without presenting stale data as current.

Environment snapshots fingerprint meaningful sea-ice, iceberg, historical-transit, and risk versions. Snapshot comparison detects source/version/freshness changes while ignoring refresh timestamps. The capability matrix reports what can be viewed, forecast, risk-assessed, routed, replanned, and tracked under current conditions.

Missions use explicit `DRAFT`, `PLANNED`, `ACTIVE`, `PAUSED`, `COMPLETED`, `ABORTED`, and `BLOCKED` states. Readiness is `READY`, `DEGRADED`, or `BLOCKED` based on operational health. Mission state is in-memory single-process prototype state and references the existing route/replanning architecture rather than creating a competing active-route store.

Telemetry is an adapter interface with manual and local file test providers. No AIS, GPS socket, satellite stream, credentials, or external network feed is connected. File telemetry is explicitly classified as simulated test data.

The API exposes operations status, sources, snapshots, capabilities, lineage, events, and mission lifecycle endpoints. Mission Control shows operational state, source freshness labels, capability status, route planning, and replanning together. The prototype remains regional Bharati / Prydz Bay, forecast-limited to +72H, without bathymetry or autonomous control.

POLARIS-AI remains a research decision-support prototype and is not a certified navigation system.
