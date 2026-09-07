# Checkpoint 3: sea-ice forecasting

The selected historical champion is the multimodal bounded residual CNN v0.3.
The frozen benchmark, selection and limitations are in [the scientific report](sea-ice-multimodal-v03.md).
The registry is `backend/forecasting/sea_ice/ml/champion.json`.

## Inference and fallback

`backend/forecasting/sea_ice/operational.py` loads local artifacts, caches weights and
the processed observation and forcing cubes in-process, and invalidates caches when
file modification times change. Weights and input checksums are checked before model
inference. Training and inference share `SeaIceWindowDataset.features_at`; this function
reads only contiguous SIC context and initialization-day atmospheric fields.
Predictions are checked before safety clipping. Invalid model output triggers an explicit
persistence fallback; the reason is exposed. No atmospheric fields are synthesized.

Latest mode prefers the newer verified NRT observation over the historical cube.
An observation older than three UTC calendar days triggers `STALE_OBSERVATION` persistence
fallback. Missing context, weights or forcing also triggers persistence. Missing all observations
returns `UNAVAILABLE`. A stale persistence grid is a demonstration of persistence anchored
to its displayed initialization, not a fresh forecast for today.

Historical requests use the chosen date and actual ERA5 initialization state, and expose
observed targets when available. ERA5 reanalysis is not an operational future weather forecast.
Historical retrospective availability does not establish real-time availability or operational skill.

## API

Start with `python -m uvicorn backend.app.main:app --reload` from the repository root.
All routes use GET:

| Endpoint | Product |
|---|---|
| `/api/sea-ice/forecast/status` | Champion, freshness, model/forcing availability, fallback, historical date bounds |
| `/api/sea-ice/forecast/latest` | Latest available prediction or explicit persistence/unavailable state |
| `/api/sea-ice/forecast/historical?date=2025-06-15` | Historical forecast and available observed targets |
| `/api/sea-ice/forecast/results` | Compact aggregate locked benchmark |

Invalid dates return HTTP 422. Missing scientific inputs are classified products, not fake grids.
Responses distinguish `HISTORICAL_FORECAST_BENCHMARK`, `LATEST_AVAILABLE_MODEL_PREDICTION`,
`PERSISTENCE_FALLBACK` and `UNAVAILABLE`. Field classifications distinguish `OBSERVATION`,
`MODEL_PREDICTION` and `PERSISTENCE_MODEL`; forcing is `REANALYSIS` when used.
Grids carry explicit latitude/longitude axes, percent concentration and null missing cells.
The historical model grid is 52 × 100; a native NRT persistence grid can have a different shape.

## Interface

Run `npm.cmd run dev` from `frontend/`. Sea-Ice Forecast uses the existing EPSG:3031
Antarctic map with actual API values, the concentration legend, NOW / +24H / +48H / +72H
controls, historical date selection, observed-target and persistence comparison, model status,
provenance, freshness and the three-model benchmark. Mission Control includes a classified
forecast status timeline. Its main map remains clearly labeled observation.
Ice Intelligence, trajectory Model Lab and existing iceberg markers retain their existing paths.

## Verification and limitations

Run `python -m pytest -q`, `python -m ruff check .` and `npm.cmd run build` in `frontend/`.
Deterministic tests cover timestamp leakage, normalization, shared feature construction,
bounded outputs, masks, missing/stale fallback and API serialization and classifications.
Tests use local fixtures and require no CDS or Copernicus network access.

The project requires its supported Python 3.11–3.13 environment, not the machine's Python 3.14.
Ignored weights and NetCDF inputs must be provisioned separately with the documented hashes.
No live data downloader is added here. The local observation's freshness remains a limitation.
The IID daily bootstrap does not adjust for temporal dependence, and validation was still
improving at epoch 30. No retraining used the locked result.

Decision-support research system. Not an autonomous ship-navigation authority.
Checkpoint 4 concerns routing and risk; none of that work is implemented by this checkpoint.

## Completion verification (2026-09-07)

- Backend: 107 tests passed; Ruff passed.
- Production Vite build passed (existing >500 kB chunk advisory).
- Live HTTP smoke: root, both observation endpoints and all four forecast endpoints returned 200.
- Historical 2025-06-15 returned three real 52 x 100 model grids; latest used the verified
  2026-08-29 NRT observation with explicit stale persistence fallback.
- Headless Chrome: Mission Control, Ice Intelligence and Model Lab loaded; forecast horizon
  controls and historical model/target/persistence layers worked with no JavaScript exceptions.
- Frozen v0.2 weights remain loadable; v0.3 and both input SHA-256 hashes match the supplied values.
- Benign warnings: Starlette/httpx and xarray/NumPy deprecations; pytest cache directory access.

The completed locked evaluation was already present at the starting revision's staged changes.
It was preserved and verified without rerunning locked selection or retraining.
