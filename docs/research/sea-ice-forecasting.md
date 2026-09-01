# Antarctic sea-ice forecasting dataset and deterministic baselines

## Source and classification

The target is the Copernicus Marine product `SEAICE_GLO_SEAICE_L4_REP_OBSERVATIONS_011_009`, produced by EUMETSAT OSI SAF from passive-microwave satellite observations. It is classified as **OBSERVATION**. Copernicus Marine Toolbox 2.4.1 verified version `202603` and the following live dataset identifiers on 1 September 2026:

- CDR: `osisaf_obs-si_glo_phy_sic-south_my_amsr_cdr_P1D-m`, catalogue coverage 2002-06-01 through 2020-12-31.
- ICDR: `osisaf_obs-si_glo_phy_sic-south_my_amsr_icdr_P1D-m`, catalogue coverage 2021-01-01 through 2026-08-16.

POLARIS-AI uses 2015-01-01 through 2026-08-16. Six CDR and six ICDR yearly regional NetCDF subsets are retained immutably under `data/raw/copernicus/sea-ice-history/`. Each has a checksum/provenance sidecar and remains Git-ignored.

Authoritative product documentation: [Copernicus Marine Product User Manual](https://documentation.marine.copernicus.eu/PUM/CMEMS-SI-PUM-011-009.pdf) and [Copernicus Marine Quality Information Document](https://documentation.marine.copernicus.eu/QUID/CMEMS-SEAICE-QUID-011-001-009.pdf).

## Domain, grid, variables, and masks

The operational Bharati box (70–84°E, 70.5–66°S) is expanded by a configured 3° context buffer. Provider coordinate selection returned 67.2–87.0°E and 73.4–63.2°S on a regular 0.2° latitude/longitude grid with 52 × 100 cells.

This is a Copernicus provider-generated regional subset. `ice_conc` and `total_standard_uncertainty` carry `regrid_method=bilinear`; `status_flag` carries `nearest_s2d`. The OSI SAF original product is also exposed on a 25 km `xc/yc` grid. The regional files are therefore not described as untouched native-grid files and are not relabeled EPSG:3031.

The processed cube retains:

- `ice_conc`, percent, 0–100;
- `total_standard_uncertainty`, percent;
- `status_flag`, provider bit mask;
- `valid_ocean_mask`, excluding provider land bit 1 and lake bit 2.

Percent is retained internally to avoid fraction/percentage conversion errors. Missing concentration and uncertainty remain NaN. They are never changed to zero. The provider metadata contains a legacy decoded `valid_max` attribute of 10000, but decoded real values were verified as 0–100 percent; QC uses the decoded physical values.

CDR and ICDR coordinates, variable names, units, regridding, and status-bit meanings match. ICDR adds a `cell_methods` attribute, but this does not change the field definition. The series is concatenated only after explicit compatibility checks.

## Cube quality control

- Daily fields: 4,246
- Coverage: 2015-01-01 through 2026-08-16
- Missing days: 0
- Duplicate days: 0
- Provider-valid ocean cells: 2,439
- NaN fraction over all rectangular grid cells: 0.552692 (principally masked land/non-observation cells)
- Decoded concentration range: 0–100 percent
- Values outside the physical range: 0

The compressed processed NetCDF is `data/processed/forecasting/sea_ice_bharati_daily.nc`. It and its complete source-checksum provenance sidecar remain Git-ignored.

## Chronological split and forecast samples

There is no random split:

- TRAIN: 2015-01-01 through 2023-12-31
- VALIDATION: 2024-01-01 through 2024-12-31
- LOCKED TEST: 2025-01-01 through 2026-08-16

All baselines are evaluated on a common initialization set that also has the previous day available for tendency. Locked-test sample counts are 592 (+24 h), 591 (+48 h), and 590 (+72 h). Training climatology uses TRAIN only. Leap day is keyed explicitly as calendar day `02-29` and averages only training leap years.

## Baselines and metrics

- B0 persistence: future concentration equals the initialization field.
- B1 seasonal climatology: target calendar-day mean from TRAIN only.
- B2 linear tendency: current field plus horizon-scaled most recent daily change, clipped to 0–100 percent.
- Optional climatology-anomaly persistence: target-day climatology plus the initialization anomaly, clipped to 0–100 percent.

Metrics use the intersection of finite prediction/target values and provider-valid ocean cells. MAE, RMSE, and mean bias are percentage points. Precision, recall, and F1 use the conventional 15% ice threshold documented by the [OSI SAF CDOP4 Product Requirement Document](https://osi-saf.eumetsat.int/sites/default/files/documents/public-documents/file/osisaf_cdop4_gen_prd_1.2.pdf).

## Locked-test regional results

| Horizon | Baseline | MAE pp | RMSE pp | Bias pp |
|---|---|---:|---:|---:|
| +24 h | Persistence | 3.072 | 6.266 | -0.118 |
| +24 h | Climatology | 10.725 | 17.608 | 2.781 |
| +24 h | Linear tendency | 4.043 | 8.045 | -0.001 |
| +24 h | Climatology + anomaly | 3.467 | 6.501 | 0.117 |
| +48 h | Persistence | 4.511 | 9.029 | -0.236 |
| +48 h | Climatology | 10.721 | 17.605 | 2.776 |
| +48 h | Linear tendency | 6.750 | 13.032 | -0.287 |
| +48 h | Climatology + anomaly | 5.014 | 9.240 | 0.174 |
| +72 h | Persistence | 5.482 | 10.844 | -0.356 |
| +72 h | Climatology | 10.719 | 17.605 | 2.769 |
| +72 h | Linear tendency | 8.791 | 16.659 | -0.766 |
| +72 h | Climatology + anomaly | 5.998 | 10.911 | 0.223 |

Persistence is the best baseline at every horizon and has a mean MAE of 4.355 percentage points across horizons. This is a benchmark result, not a forecast model deployed to Mission Control.

## Seasonal and Bharati-local evaluation

The fixed seasonal groups are austral cold/growth (March–October) and warm/melt (November–February). Persistence MAE is 3.516/2.040 pp (cold/warm) at +24 h, 5.075/3.192 pp at +48 h, and 6.070/4.099 pp at +72 h.

The Bharati-local mask includes the 41 provider-valid ocean cells within ±1° latitude/longitude of the verified station coordinate; it does not treat the station’s land cell as navigable water. Persistence local MAE is 2.651, 3.866, and 4.699 pp at +24/+48/+72 h.

Generated mean-error fields are stored in the ignored artifact `artifacts/sea-ice-baseline-error-maps.nc`; no smoothing or synthetic values are applied.

## Limitations

The locked test combines full 2025 with a partial 2026 through 16 August, so it is not composed of equal complete seasonal years. The regional grid is a provider-regridded subset rather than the untouched original 25 km grid. Baselines use concentration history only and do not use atmospheric/ocean forcing. No CNN, ConvLSTM, Transformer, U-Net, or other learned model has been implemented, and no sea-ice forecast is displayed in Mission Control.
