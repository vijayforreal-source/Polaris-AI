# Historical Transit Intelligence

This feature stores previous vessel movements as historical observational evidence and
displays them in Mission Control. It does not plan routes, predict vessel motion, or judge
current environmental conditions. **Historical transit confidence is not a safety probability.**

## Source policy and current state

The local repository was searched for AIS, voyage/expedition routes, vessel GPS, CSV,
GeoJSON, GPX and KML data. Existing time-stamped tracks are USNIC iceberg observations,
not vessel movements. No verified historical vessel tracks are currently loaded. Production
shows the honest empty state; synthetic fixtures exist only in tests.

Use Cape Town to Bharati, Bharati to Maitri, and Maitri to Cape Town as voyage-corridor
terminology. These names neither define fixed maritime routes nor imply that an inland
station is directly reachable by ship. Import actual landing/port names in the metadata
when supplied by the source. Do not relabel the maritime leg as a fixed India-to-Bharati route.

## Schema and validation

`backend/historical_transit/models.py` defines Pydantic voyage metadata and points:

- Required metadata: `voyage_id`, `vessel_name`, `origin`, `destination`, `source`,
  `source_reference`. Optional identifiers: `imo` (7 digits), `mmsi` (9 digits), `expedition_id`.
- `source_classification` is `OBSERVATION`. `source_verified` defaults to false;
  true requires `verified_by`, an explicit source-review attestation. Plausible coordinates
  alone never establish source authenticity. Reference may be a URL or archive/document identifier.
- Points: `timestamp_utc` with explicit timezone, latitude, longitude; optional `speed_knots`
  and `course_deg`. Times normalize to UTC. Input order is retained.
- Import provenance: raw-file SHA-256 and import time. Derived API metadata includes
  quality, count, start/end, distance estimate, duration, latest transit, age, gaps and notes.

Coordinate ranges, duplicate/non-increasing timestamps, future timestamps, minimum two
positions, implied speeds and supplied speed/course are checked. The configurable validation
policy defaults to a 40-knot plausibility ceiling and a six-hour gap threshold. These are
screening thresholds, not vessel-specific limits or safety criteria. Distance is the sum of
great-circle distances between fixes using radius 6371.0088 km, not measured sailed distance.

Quality is `VERIFIED`, `USABLE_WITH_GAPS`, `LOW_CONFIDENCE`, or `REJECTED`. Missing source
verification and suspect reported speed/course give low confidence. Invalid coordinates,
ordering, jumps, or too few points reject the track. Questionable coordinates and order
are preserved, not silently sorted or removed. Malformed rows are quarantined with the
original input and diagnostics. Map/corridor output uses only source-verified, acceptable
tracks. Long gaps remain visibly disconnected and are excluded from corridor counts.

## Import and storage

From the repository root, with the project virtual environment active:

```powershell
python -m scripts.import_historical_voyage_tracks path/to/actual-track.csv --metadata path/to/voyage-metadata.json --field-map path/to/field-map.json
```

Metadata must describe the actual supplied voyage; identifiers are never guessed.
The mapping JSON maps canonical fields to actual input column/property names, for example:

```json
{"timestamp_utc": "utc_time", "latitude": "lat", "longitude": "lon"}
```

CSV requires all three mappings. GeoJSON accepts Point Features/FeatureCollections, or a
LineString with one mapped timestamp per coordinate in a property array; optional speed
and course arrays must have matching lengths. GeoJSON always uses geometry coordinates
in `[longitude, latitude]` order, so its mapping contains timestamp and optional speed/course
properties only. Bare LineStrings without timestamps are rejected. There is no invented timing.

The default store is `data/processed/historical_transit/{voyage_id}.json`, already Git-ignored.
Malformed input goes to its `rejected/` subdirectory. Existing voyage files cannot be
overwritten. Inputs are limited to 20 MB and 5,000 points per explicit voyage leg; there is
no silent thinning. Keep larger raw AIS files under ignored `data/raw/`. API reads are cached
by path, modification time and size; invalid stored files remain visible as status errors.
No database or external AIS credentials are required for the empty-state implementation.

## API and recency

| GET endpoint | Response |
|---|---|
| `/api/historical-transit/status` | Availability, voyage/verified counts, latest transit, sources, quality counts, limitations, load errors |
| `/api/historical-transit/voyages?offset=0&limit=25` | Compact summaries; maximum page size 100 |
| `/api/historical-transit/voyage/{voyage_id}` | Points, provenance and derived metadata; unknown ID returns 404 |
| `/api/historical-transit/corridor?tau_days=180&cell_degrees=1` | Derived evidence bins; paginated with `offset`/`limit`, maximum 5,000 cells |

Corridor evidence bins the midpoints of consecutive acceptable observed segments into
longitude/latitude cells. Consecutive hits in the same cell count once per voyage passage;
re-entry counts again. Unique voyages are counted separately. Each cell reports passage
count, unique voyages, latest transit, age and `exp(-age_days / tau_days)`. Tau defaults to
180 days and is query-configurable. Dateline midpoint arithmetic follows the short longitude
arc. This is a transparent, approximate segment-bin summary, not a full swept corridor;
sampling density and observation gaps affect counts. No sea-ice or iceberg hazard is included.

## Frontend and demonstration

Mission Control has a **Historical Vessel Tracks** checkbox and **Historical Transit
Intelligence** card. With no data it says: "No verified historical voyage tracks are currently
loaded." It draws no example routes. With accepted imports, up to 25 voyages per page load
as dashed amber lines; map extent includes the tracks. A line click or voyage-list selection
shows vessel, expedition, origin/destination, dates, distance, source/reference, review,
quality, age and the historical-evidence explanation. Long gaps are not connected.

The panel states: "Historical vessel track — not a current safety guarantee." It explicitly
separates historical evidence from AI predictions and navigation authority. The main sea-ice
map, iceberg markers and existing Sea-Ice Forecast remain on their existing data paths.
There is no optional HIGH/MEDIUM/LOW corridor overlay in this version; quantitative corridor
evidence is available through the API without suggesting environmental safety.

## Verification and future boundary

Run `python -m pytest -q`, `python -m ruff check .`, then `npm.cmd run build` in `frontend/`.
Focused tests use synthetic fixtures only in temporary stores, with no live AIS calls.
The browser smoke test uses the real empty API and isolated mocked test responses for track
interaction; it never writes synthetic voyages to the production store.
With Vite/FastAPI running and an isolated headless Chrome instance exposing CDP on port 9223,
run `node tests/browser_historical_transit.mjs`. This uses Node's built-in APIs and the existing
browser; it adds no frontend test framework or package dependency. Its screenshots are ignored.

Future Checkpoint 4 may evaluate historical evidence alongside separately validated current
environmental information. This feature implements no risk engine, hazard fusion, routing,
bathymetry, vessel risk, fuel optimization or rerouting. Frozen Checkpoint 3 logic is unchanged.
