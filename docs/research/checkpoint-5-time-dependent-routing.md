# Checkpoint 5 — Time-dependent multi-objective routing

POLARIS-AI now provides a regional Antarctic route planning prototype for the Bharati / Prydz Bay study grid. It consumes the Checkpoint 4 `RiskField` and does not duplicate sea-ice, iceberg, vessel, or historical-transit hazard logic.

The graph uses 8-connected grid-cell centers. Search state is `(row, column, time bucket)` and each edge uses geodesic distance and nominal speed to calculate arrival time. The risk provider is queried for the estimated arrival horizon, with one-hour memoized buckets by default. Dijkstra is used for correctness and bounded expansion rather than an unsafe static shortest path.

SAFE minimizes cumulative risk exposure and uncertainty; FAST minimizes travel time; ECO minimizes `RELATIVE ECO COST`, a transparent distance and risk proxy; BALANCED uses normalized engineering defaults of time 0.30, risk 0.45, eco 0.15, and uncertainty 0.10. These weights are not scientifically optimized and no fuel or CO₂ claim is made.

All objectives share hard no-go cells from Checkpoint 4. Requests that cannot complete within the validated +72H forecast horizon return an explicit horizon/no-route status. The current domain is regional Bharati / Prydz Bay; Cape Town to Antarctica is outside the dynamic grid and is not fabricated.

The API exposes `GET /api/routes/status` and `POST /api/routes/plan`. Mission Control includes a focused route planner, objective comparison cards, and OpenLayers route lines. Outputs include waypoint arrival times, component hazards, risk categories, navigation costs, metrics, provenance, and deterministic explanation text. Historical transit is consumed only through Checkpoint 4 navigation cost and surfaced as support metadata; it is not double-counted.

These outputs are research decision-support recommendations, not certified navigational routes. Continuous live rerouting and automatic route replacement are deferred to Checkpoint 6.
