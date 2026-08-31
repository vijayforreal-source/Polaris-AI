# Verified Environmental Forcing Along A76C

This checkpoint aligns environmental fields with the observed A76C track. It does not implement a
trajectory predictor.

## Classification

- USNIC iceberg positions are `OBSERVATION`.
- Copernicus Mercator GLO12 currents are numerical-model `ANALYSIS`.
- ERA5 atmospheric fields are `REANALYSIS`, not direct measurements.
- OSI-SAF satellite sea-ice concentration is `OBSERVATION`.

## Ocean currents

The live Copernicus catalogue verified product `GLOBAL_ANALYSISFORECAST_PHY_001_024`, dataset
`cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i`, version `202406`. Its `uo` and `vo` fields are
eastward and northward sea-water velocity in `m s-1` on a regular approximately 1/12-degree grid.

The requested A76C envelope is longitude -39.50 to -28.50 and latitude -61.50 to -51.083332.
Three exact source levels are retained independently: 0.494025, 29.444731, and 92.326073 m. They do
not imply a known A76C draft, and no vertical interpolation or depth weighting is performed.

## ERA5 wind

Eight official monthly NetCDF files were retrieved with `cdsapi` 0.7.7 from CDS dataset
`reanalysis-era5-single-levels`. Only `10m_u_component_of_wind` and
`10m_v_component_of_wind` were requested. The real files expose `u10`, `v10`, native time
coordinate `valid_time`, units `m s**-1`, descending latitude, and longitude in the -180-to-180
convention. The regular grid is 0.25 degrees with 42 latitude by 45 longitude points.

The request extended from 2 January 00:00 through 27 August 23:00. CDS returned continuous hourly
data through 26 August 12:00: 5,677 unique timestamps, no duplicates, and a final 35-hour provider
availability gap. This gap is preserved and flagged rather than extrapolated. Every raw monthly file
has a Git-ignored checksum/provenance sidecar. Credentials remain outside the repository.

## Sampling and coverage

USNIC supplies date precision only. Sampling at 00:00 UTC is an explicit convention, and samples
retain `USNIC_DATE_PRECISION_ONLY`. The sampler uses four-neighbour bilinear spatial interpolation
and linear interpolation between bracketing source times. Exact provider timestamps are retained
when available. Descending latitude is sorted together with its data; data axes are never reversed
independently. Requests outside source coverage remain missing.

All 105 ocean point/depth samples are valid. Wind covers 34 of 35 dated positions, or 102 of 105
depth-repeated samples; the 27 August position is outside returned ERA5 coverage. Ocean interval
summaries use six-hourly samples and wind summaries use hourly samples along the WGS 84 geodesic
between observations. Mean wind interval coverage is 99.7912%, with 92.8994% in the final interval.
These are `TRACK-ALIGNED ENVIRONMENTAL SUMMARY` values, not an exact reconstruction of motion.

## Exploratory comparison

| Forcing | East correlation | North correlation | Mean alignment | Median alignment |
|---|---:|---:|---:|---:|
| Ocean 0.494 m | 0.5002 | 0.4937 | 0.5124 | 0.9208 |
| Ocean 29.445 m | 0.5713 | 0.4857 | 0.4931 | 0.8831 |
| Ocean 92.326 m | 0.5508 | 0.4438 | 0.3599 | 0.7394 |
| ERA5 10 m wind | -0.1059 | 0.0016 | 0.1139 | 0.1888 |

The 29.445 m current has the strongest east-component relationship. The surface current has the
strongest north-component relationship and directional alignment. Valid aligned wind speed averages
10.2417 m/s and ranges from 2.1911 to 18.5502 m/s. Direction means the direction **toward** which
the vector points, clockwise from north; it is not meteorological wind-from direction. Correlation
does not establish causation or physical dominance.

The existing OSI-SAF Prydz Bay file does not cover A76C's longitude range, so sea-ice context remains
`not covered`, never zero. No 2% wind rule, current-depth weighting, drag coefficient, draft,
thickness, mass, force balance, Coriolis integration, uncertainty model, ML, or trajectory prediction
is implemented.
