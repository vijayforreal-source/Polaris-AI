# POLARIS-AI demo guide

Start the backend with `uvicorn backend.app.main:app --reload`, then run the frontend with `npm.cmd run dev` from `frontend`. Open Mission Control and begin with the Operational Status and Connection panels. Explain provider, classification, freshness, and the regional Bharati / Prydz Bay scope.

For a real-data demonstration, show the latest sea-ice observation, iceberg registry, +24/+48/+72 forecast states, Dynamic Risk, and historical transit. If the current field is stale or blocked, say so and do not fabricate a route.

For the route/reroute demonstration, run the opt-in synthetic scenario scripts. These are labeled `DEMO / SIMULATED`, isolated in memory, and show route alternatives, active-route recommendation, captain acceptance, offline deferral, and reconnect readiness. Use the phrases “decision-support recommendation”, “latest available”, “forecast horizon”, and “mission readiness”. Do not claim certified safety, live AIS/GPS, autonomous navigation, or direct satellite control.
