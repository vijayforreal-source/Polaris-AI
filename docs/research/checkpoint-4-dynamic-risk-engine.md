# Checkpoint 4: dynamic vessel-aware risk engine

Checkpoint 4 computes a time-aware engineering risk field for a specified vessel profile.
It combines sea-ice hazard, iceberg hazard, data/forecast uncertainty, vessel constraints,
and historical transit evidence. The result is decision support, not a certified navigational
safety probability.

## Architecture

`backend/navigation/risk/` is deliberately independent of route generation. `RiskInputs`
contains aligned latitude/longitude axes, the frozen SIC observation/forecast fields, the
frozen ocean mask, operational USNIC iceberg observations, historical-transit corridor bins,
timestamps, data states, and v0.3 locked MAE values. `service.py` is the future Checkpoint 5
interface: `get_risk_field()` and `get_point_risk()` return a complete risk field without
searching for a route. Model loading and risk fields are cached in-process using data
fingerprints and minute-level current-state keys.

No bathymetry is inferred. No A*, Dijkstra, route search, SAFE/FAST/ECO/BALANCED profile,
fuel/ETA optimization, or automatic rerouting is present.

## Vessel profiles

`VesselProfile` requires explicit provenance and uses unknown values as unknown. The two
profiles currently exposed by `/api/risk/vessels` are clearly `SIMULATED_VESSEL_PROFILE`;
they are engineering test scenarios, not real vessels or certifications. A profile with
unknown ice limits, clearance, or capability is uncertain and hard-blocked by the current
engineering policy so missing capability cannot lower risk. Custom point requests validate
the same schema.

## Sea ice and horizon handling

The engine calls frozen Checkpoint 3 operational inference and never retrains or alters its
weights. SIC percent is mapped through configurable breakpoints 0/15/40/70/100 to hazards
0/0.10/0.40/0.80/1.00 after vessel-aware recommended limits. The same SIC is more hazardous
for the simulated open-water profile. Forecast horizons 0, 24, 48 and 72 are supported;
12/36/60 are linear interpolations with metadata naming both bounding horizons and the
fraction. Horizons over 72H do not extrapolate: SIC is unavailable, uncertainty is 1,
`FORECAST_HORIZON_EXCEEDED` is recorded and cells are blocked.

Locked v0.3 MAE values (2.877915, 4.066660, 4.788987 pp) supply an error-scale proxy that
grows with horizon. It is explicitly not interpreted as probability. Stale SIC, fallback
mode, missing masks, unavailable states, and missing forcing add uncertainty; critical
unavailability blocks cells.

## Icebergs

The engine consumes the verified USNIC registry, not the historical A76C research candidate.
It validates checksums, prevents observations newer than the requested retrospective
initialization, uses geodesic WGS84 distance, and expands a transparent provisional envelope
for observation age, horizon, reported size and uncertainty. Configured engineering defaults
are 2 km exclusion plus vessel clearance and a 20 km caution band; they are explicitly
`ENGINEERING_DEFAULT / NOT_NAVIGATIONAL_CERTIFICATION`, not official safe distances. A hard
exclusion sets `navigable=false`; stale or unavailable registry data increases uncertainty
and can block the field. Provider coverage remains incomplete.

## Historical transit interaction

The completed historical-transit module is read-only here. It remains honest with zero
verified voyages in production. Eligible verified corridor cells are converted to confidence
from recency and unique-voyage frequency. The maximum preference bonus is 0.08. It applies
only to navigation cost when the cell is otherwise navigable and risk is below 0.40. It never
reduces safety risk and never overrides land, invalid cells, missing data, vessel limits,
iceberg exclusion, or horizon constraints. Historical transit confidence is not a safety
probability.

## Formula, hard constraints, and cost

With defaults `(w_ice, w_iceberg, w_uncertainty, w_vessel) = (0.40, 0.30, 0.20, 0.10)`:

```text
safety_risk = clamp(
  0.40 * sea_ice_hazard +
  0.30 * iceberg_hazard +
  0.20 * uncertainty_hazard +
  0.10 * vessel_constraint_hazard, 0, 1)
```

Risk is then set to 1 for land/invalid cells, missing or stale critical SIC, unavailable
icebergs/environment, hard iceberg exclusion, vessel SIC violation/unknown capability, and
horizon exceeded. Categories use 0.20/0.40/0.60/0.80 boundaries: LOW, GUARDED, ELEVATED,
HIGH, CRITICAL. Navigable cells receive:

```text
navigation_cost = max(0, safety_risk + 0.25 * uncertainty_hazard - experience_bonus)
```

Blocked cells serialize as `null`, which is the future A* cost-compatible representation.
Experience is bounded and cannot create navigability.

## API

- `GET /api/risk/status`: checkpoint state, component states, vessel profiles, timestamps and limits.
- `GET /api/risk/vessels`: simulated profiles and provenance.
- `GET /api/risk/grid?horizon_hours=24&vessel_id=simulated-research`: compact arrays, categories,
  navigable mask, hard-constraint bits, components, interpolation and provenance.
- `GET /api/risk/point?lat=-69&lon=76&horizon_hours=24&vessel_id=simulated-research`: nearest-cell
  explanation, component values, dominant factor, constraints, score and cost.
- `POST /api/risk/point`: the same explanation for a validated custom vessel profile.

Coordinates are nearest grid-center samples, never silently extrapolated. Invalid coordinates,
unknown vessels and malformed profiles return validation errors. Current local data may be
stale; API metadata states this explicitly.

## Frontend

Mission Control has a Dynamic Risk toggle, horizon selector NOW/+24H/+48H/+72H, simulated-vessel
selector, component-status block, engineering legend, blocked-cell rendering, and click-to-
explain point panel. The existing sea-ice, iceberg, historical-transit and forecast modules
remain separate layers. The disclaimer states that risk is decision support, not certified
safety and that no route is generated.

## Validation and limitations

`scripts/evaluate_risk_engine.py` prints deterministic engineering summaries (risk range,
categories, blocked cells, means, dominant factors and provenance) for four horizons. It does
not claim navigational validation. Focused unit/API tests cover monotonic SIC hazard, capability,
interpolation, bounds, hard no-go rules, iceberg geodesic decay/exclusion, stale data, missing
capability, historical-cost separation, API serialization and explainability. No current vessel
or fake route data is created. Future Checkpoint 5 may consume the grid, but route search remains
out of scope.
