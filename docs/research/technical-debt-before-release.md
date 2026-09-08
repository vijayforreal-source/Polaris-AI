# Technical debt before release

## RC1 disposition of every former MUST FIX BEFORE RELEASE item

- Durable missions/events/sync storage: reclassified MUST FIX BEFORE operational release.
  RC1 is a research evaluation build with explicitly session-only mission, active-route,
  event and sync state. Restart clears these; no operational continuity is promised.
  Adding persistence now would expand scope and require recovery/consistency validation.
- Authenticated providers: reclassified FUTURE, subject to governance and credentials.
  Optional unconfigured providers are intentional in this local historical research RC.
- FastAPI startup deprecation: resolved by a lifespan handler; scientific evaluation unchanged.
- Browser panel smoke coverage: covered by main and historical smoke scripts; final execution
  results are recorded in docs/release/FINAL_TEST_REPORT.md.

## SHOULD FIX

- Reduce startup health latency by separating cached status from scientific evaluation.
- Add richer cache generation history and atomic artifact downloads.
- Add waypoint inspection controls.
- Split the frontend main chunk; defer refactor to avoid destabilizing RC1.

## FUTURE

- Durable operational state, authenticated providers, bathymetry, larger domains and live telemetry.
- Desktop packaging is implemented; Windows validation results are tracked in the release report.
