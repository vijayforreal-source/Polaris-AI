# Technical debt before release

## MUST FIX BEFORE RELEASE

- Replace in-memory missions/events/sync state with durable, atomic local storage.
- Add real authenticated provider adapters only after governance and credentials are approved.
- Replace deprecated FastAPI startup event with a lifespan handler.
- Add browser-level automated smoke coverage for every Mission Control panel.

## SHOULD FIX

- Reduce startup health latency by separating cached status from full scientific evaluation.
- Add richer cache generation history and atomic artifact download implementation.
- Add explicit route/candidate styling and waypoint inspection controls.

## FUTURE

- Desktop packaging, bundled runtime, larger-domain preparation, bathymetry, live telemetry, and production deployment are deferred to later checkpoints.
