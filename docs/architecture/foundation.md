# Foundation architecture

POLARIS-AI uses a modular structure so future ingestion, preprocessing, forecasting,
iceberg, routing, and vessel concerns can evolve independently and be tested at clear
boundaries. Checkpoint 1 contains no scientific implementation in those areas.

## Scientific data principles

Raw source data will remain immutable under `data/raw/`. Derived products will be written
separately so every result can be traced to an unchanged source and reproduced.

Source/native CRS metadata and the future canonical Antarctic CRS (EPSG:3031) must remain
distinct. Conversion must never erase the source spatial reference or silently assume a CRS.
No reprojection is implemented in this checkpoint.

Observation time and forecast validity time describe different facts and cannot be mixed.
Future layers will preserve metadata conceptually including `variable`, `source`,
`observed_at`, `valid_at`, `downloaded_at`, `native_crs`, `canonical_crs`,
`spatial_resolution`, `temporal_resolution`, `units`, `quality_flags`, and `provenance`.
Every scientific datum or product must be categorized as `OBSERVATION`, `FORECAST`, or
`MODEL_PREDICTION`.

## Deliberate scope boundary

ML, scientific ingestion, mapping, risk, and routing layers are intentionally absent. Their
presence before trustworthy source handling and provenance rules would undermine scientific
defensibility. Empty domain directories are architectural boundaries, not claims of completed
capability.

The planned next checkpoint is verified ingestion of real sea-ice data, including source
metadata and provenance validation. No such integration is complete at Checkpoint 1.

