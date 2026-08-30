# Verified observation map

Checkpoint 3 has a deliberately one-way visualization path:

```text
SOURCE OBSERVATION (ignored, immutable NetCDF)
  -> xarray backend reader
  -> read-only Sea-Ice API
  -> OpenLayers vector cells
  -> EPSG:3031 display transformation
  -> polar-oriented mission view
```

The API publishes the coordinate vectors and a row-major concentration grid. Finite source
values remain numeric; missing source values become JSON `null`. The frontend creates display
cell footprints from adjacent coordinate midpoints and does not interpolate concentration.
Missing cells produce no feature and remain transparent rather than being presented as 0% ice.

The Copernicus file is a genuine observation, but it is a provider-generated 0.1° regional
latitude/longitude subset with `regrid_method=bilinear`. It is not the untouched OSI-SAF 10 km
polar-stereographic `xc`/`yc` product.

OpenLayers and proj4 transform WGS 84 longitude/latitude display geometry to EPSG:3031 (WGS 84 /
Antarctic Polar Stereographic). This display coordinate transformation is not scientific source
reprojection: POLARIS-AI does not alter the stored NetCDF, assign it EPSG:3031, or create a new
scientific raster in this checkpoint.

Land context is Natural Earth 1:110m land data (public domain). Sea-ice attribution remains
visible as Copernicus Marine Service and OSI-SAF / EUMETSAT.

Checkpoint 4 adds a separate read-only path for the current USNIC CSV registry. Signed source
coordinates are parsed into typed `OBSERVATION` records, filtered against the existing configured
Bharati bounds, served without prediction fields, and transformed only for OpenLayers display.
Each marker is a single current registry position—not a track, velocity estimate, or forecast.
