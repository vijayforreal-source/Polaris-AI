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
