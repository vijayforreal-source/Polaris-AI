# Scientific data sources

## Checkpoint 2 sea-ice observation

- **Provider:** Copernicus Marine Service / OSI-SAF
- **Product:** `SEAICE_GLO_SEAICE_L4_NRT_OBSERVATIONS_011_001`
- **Verified dataset:** `osisaf_obs-si_glo_phy-sic-south_nrt_amsr2_l4_P1D-m`
- **Verified variable:** `ice_conc`
- **Standard name:** `sea_ice_area_fraction`
- **Units:** `%`
- **Live catalogue coverage:** `2023-03-23T00:00:00Z` through
  `2026-08-29T00:00:00Z`, daily
- **Observation used:** `2026-08-29T00:00:00Z`
- **Study region:** configurable Bharati/Prydz Bay bounding box, 70–84°E and
  70.5–66°S

The catalogue documents an original 10 km southern polar stereographic grid with `xc` and
`yc` coordinates in kilometres. The Copernicus `subset` service returned this requested
geographic subset on a regular 0.1° `latitude`/`longitude` grid and records
`regrid_method=bilinear` on `ice_conc`. The returned NetCDF has no `grid_mapping` variable and
declares no EPSG identifier. **EPSG unresolved at Checkpoint 2.** No reprojection was performed
by POLARIS-AI.

The downloaded file is registered as an **OBSERVATION**, not a forecast and not a model
prediction. Its `canonical_crs` remains null because no POLARIS-AI canonical reprojection has
occurred.

The source file contains global `start_date`, `stop_date`, and creation-history attributes from
2025 that do not match the subset coordinate selected by the live service. POLARIS-AI therefore
uses the decoded `time` coordinate (`2026-08-29T00:00:00Z`) as the observation time and preserves
the inconsistent global attributes in the inspection record rather than silently rewriting them.

## Checkpoint 4 current iceberg registry

- **Provider:** U.S. National Ice Center (USNIC)
- **Product:** Antarctic Iceberg Data
- **Format:** official current CSV
- **Provider report date:** `2026-08-27` (date precision only)
- **Retrieved:** `2026-08-30T22:22:22.182025Z`
- **Classification:** `OBSERVATION`
- **Current records:** 33, all with valid coordinates
- **Bharati-region records:** 6

USNIC names and tracks Antarctic icebergs meeting either 20 square nautical miles or greater,
or 10 nautical miles on the longest axis. The product is generally updated weekly according to
USNIC product documentation; the live product page provides a current file and archive but did
not state a cadence in its visible text during this retrieval.

The registry covers qualifying named/tracked icebergs. It is **not a complete catalogue of all
smaller iceberg hazards**, and absence from this registry does not establish the absence of an
iceberg. Future Sentinel-1/SAR detection is planned as a complementary local hazard source; it is
not implemented.
