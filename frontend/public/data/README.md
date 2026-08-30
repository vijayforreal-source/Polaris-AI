# Geographic context asset

`ne_110m_land.geojson` is Natural Earth 1:110m land data, retrieved on 2026-08-31 from the
[Natural Earth vector repository](https://github.com/nvkelso/natural-earth-vector). Natural
Earth data is public domain.

SHA-256: `9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9`

The frontend selects only source features extending south of 60°S before transforming them for
EPSG:3031 display. No substitute Antarctic geometry is generated.
