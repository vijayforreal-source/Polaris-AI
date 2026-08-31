# USNIC Historical Iceberg Tracks and Trajectory Baseline

## Official archive and retrieval

The source is the U.S. National Ice Center (USNIC) [Antarctic Iceberg Products
archive](https://usicecenter.gov/Products/ArchiveSearchMulti?linkChange=ant-three&table=IcebergProducts).
The live archive identifies the product as `Antarctic Icebergs CSV` and exposes availability
from 7 November 2014 through 27 August 2026 at retrieval time.

The archive page submits the selected product and date range to
`/Products/DisplaySearchResults`. Its returned official links use
`/File/DownloadArchive?prd=134MMDDYYYY`. This mechanism was discovered from the live search
results; filenames and weekly dates were not assumed.

Checkpoint 5 requested 1 January through 27 August 2026. The archive returned 35 CSV files,
covering 2 January through 27 August. All were downloaded; no missing weeks were generated.
Each immutable raw file is stored below `data/raw/usnic/icebergs/archive/YYYY-MM-DD/`, with a
Git-ignored JSON sidecar recording its URL, retrieval time, report date, byte size, and SHA-256.
The 35 files contain 1,159 rows and 41 iceberg IDs. Every file uses the verified schema:

`Iceberg, Length (NM), Width (NM), Latitude, Longitude, Area (sqMI), Area (sqNM), Area (sqKM), Last Update`

All files opened successfully, all rows parsed, and no two provider files were byte-identical.

## Date semantics and deduplication

The archive-file date is the registry report/publication date. `Last Update` is retained
separately as the provider date attached to the position. Because USNIC supplies date precision
only, POLARIS-AI does not invent a time of day or timezone.

Weekly files can repeat exactly the same coordinate. Such records retain their individual source
provenance, but zero-distance repetitions do not contribute movement. Reports distinguish:

- `record_count`: provider-dated registry observations;
- `unique_position_count`: distinct latitude/longitude pairs;
- duplicates of the same iceberg, provider date, and coordinate: one normalized track point with
  all contributing archive files retained.

## Geodesic motion calculations

Distances and bearings use `pyproj.Geod` with the WGS 84 ellipsoid. Consecutive points are ordered
by the provider `Last Update` date. Each step reports ellipsoidal distance, forward azimuth,
elapsed time, and average displacement speed. These are **derived from observations**; USNIC did
not supply velocity or heading.

The configurable QC and classification defaults are intentionally explicit:

- under 10 km cumulative displacement is `LOW-MOTION`; this conservative tolerance spans several
  increments of the provider's 0.01-degree coordinate precision;
- one repeated coordinate is `APPARENTLY STATIONARY`;
- a trajectory candidate needs at least four dated points, 50 km cumulative displacement, no gap
  over 21 days, and no step averaging more than 10 knots;
- the 10-knot limit is a malformed-jump screening bound, not an iceberg-physics assertion.

No flagged jump is silently removed. Thresholds are represented by `MotionThresholds` and can be
reviewed or changed without altering the calculations.

## Regional findings

| Iceberg | Records | Unique positions | Duration (days) | Cumulative displacement (km) | Finding |
|---|---:|---:|---:|---:|---|
| D15A | 35 | 2 | 237 | 0.886 | LOW-MOTION |
| D15B | 35 | 7 | 237 | 14.575 | MOVING |
| D15C | 29 | 23 | 195 | 116.468 | MOVING |
| D15D | 17 | 11 | 111 | 17.652 | MOVING |
| D23 | 35 | 4 | 237 | 3.536 | LOW-MOTION |
| D34 | 35 | 6 | 237 | 4.375 | LOW-MOTION |

These findings do not diminish stationary or grounded iceberg hazards. They only describe
observed coordinate histories and suitability for a motion baseline.

## Candidate selection and baseline evaluation

A76C was selected automatically because it had the greatest cumulative observed displacement
among tracks satisfying the configured candidate checks: 35 dated points, 34 unique positions,
237 days, and 1,823.856 km cumulative displacement. The requested archive window was sufficient,
so it was not expanded backward.

Time order is preserved. Rolling-origin validation produces 33 held-out forecasts. For each held-
out point:

- **Persistence:** `future position = latest observed position`.
- **Constant velocity:** WGS 84 inverse geodesics determine the latest observed bearing and
  distance; distance divided by elapsed time gives speed, and WGS 84 forward geodesics propagate
  it over the forecast horizon.

Across all 33 held-out forecasts, persistence mean/median error was 53.840/44.384 km, while
constant-velocity mean/median error was 65.583/49.757 km. Constant velocity therefore performed
worse overall and is reported honestly. On the final 168-hour holdout (27 August), persistence
error was 94.628 km (51.095 NM), and constant-velocity error was 55.882 km (30.174 NM).

This is a **TRAJECTORY BASELINE**, not an AI trajectory prediction. Weekly observations are sparse;
USNIC covers named/large icebergs rather than every hazard; and constant velocity ignores ocean
currents, wind, sea-ice interaction, uncertainty, and changing grounding state. Environmental
forcing and any later residual model remain unimplemented.
