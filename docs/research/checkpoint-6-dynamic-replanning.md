# Checkpoint 6 — Dynamic re-routing and continuous replanning

Checkpoint 6 adds manual/event-triggered replanning for an already active Checkpoint 5 route. A lightweight in-memory `ActiveVoyage` stores the route, objective, vessel, current manually supplied position/time, waypoint index, environment version, and replan timestamps. State is intentionally single-process prototype state; it is not a production voyage database.

The replanning engine evaluates only the remaining route from the current position. It queries the Checkpoint 4 risk service at expected waypoint arrival horizons and detects blocked cells, vessel constraints, unavailable data, critical risk, and forecast horizon failures. Environment versions are deterministic hashes of the existing risk source fingerprint rather than wall-clock timestamps alone.

Decision logic is deterministic. Hard invalidation produces `REROUTE_REQUIRED` when a valid alternative exists and `NO_SAFE_ALTERNATIVE` otherwise. Soft decisions use centralized `ENGINEERING_DEFAULT` thresholds: minimum risk improvement 0.05, cumulative risk improvement 10%, ETA improvement 5%, eco improvement 5%, route cooldown 30 minutes, and similarity threshold 0.85. A cooldown suppresses soft recommendations but never suppresses a hard safety reroute. Minor changes return `KEEP_CURRENT`, and unchanged inputs can be handled without autonomous polling.

Candidate routes reuse the Checkpoint 5 planner from the current manual position/time and preserve the active objective preference. Replan events record before/after metrics, deltas, environment version, reason codes, threshold configuration, and acknowledgement status. A candidate is never applied automatically; the optional acceptance endpoint requires explicit user action.

Mission Control now exposes Set as Active Route, manual position handling, Check for Safer Route, recommendation states, and captain-facing explanations. Current and candidate routes remain map-layer outputs, with no live AIS/GPS, background workers, autonomous control, or push alerts.

POLARIS-AI replanning outputs are captain-facing decision-support recommendations, not commands or certified navigation. Checkpoint 7 will address operational telemetry and data-pipeline hardening.
