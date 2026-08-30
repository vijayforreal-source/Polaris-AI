# USNIC Antarctic iceberg registry

The live [USNIC Antarctic Iceberg Data page](https://usicecenter.gov/Products/AntarcIcebergs)
was verified on 2026-08-30 UTC. It identifies USNIC as the entity that names, tracks, and
documents Antarctic icebergs meeting its criteria: at least 20 sq NM in area or at least 10 NM
on the longest axis. It exposes PDF, CSV, and GIS shapefile products. Checkpoint 4 uses only the
official current CSV endpoint, `/File/DownloadCurrent?pId=134`.

## Acquired product

- Provider filename: `AntarcticIcebergs_20260827.csv`
- Provider report/update date: `2026-08-27`
- Retrieval time: `2026-08-30T22:22:22.182025Z`
- Size: 1,897 bytes
- SHA-256: `8d02d0697f9f07d032dbad7141531b3a926d05c83b65b28fdc564d398fc2fb50`
- Encoding: UTF-8 with BOM
- Delimiter: comma
- Rows: 33

Actual headers:

```text
Iceberg, Length (NM), Width (NM), Latitude, Longitude,
Area (sqMI), Area (sqNM), Area (sqKM), Last Update
```

All 33 rows parsed with valid signed-decimal coordinates and no missing fields. Six lie inside
the configured Bharati/Prydz Bay region: `D15A`, `D15B`, `D15C`, `D15D`, `D23`, and `D34`.

`Last Update` is supplied as `MM/DD/YYYY`. POLARIS-AI preserves that original string and a
normalized date, without adding a time of day or timezone. A current registry point is an
observation, not a trajectory.

## Limitations

The product is generally weekly according to USNIC product documentation, though cadence was
not stated in the visible live-page text during retrieval. More importantly, the named iceberg
registry covers only icebergs meeting USNIC tracking criteria. It does not represent every
smaller iceberg a vessel could encounter. Sentinel-1/SAR detection is planned as a future
complementary local layer and is not implemented at this checkpoint.
