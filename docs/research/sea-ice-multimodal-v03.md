# Sea-ice multimodal v0.3

The task predicts Antarctic sea-ice concentration at +24, +48 and +72 hours in the existing Bharati / Prydz Bay domain. The persisted locked evaluation selects **v0.3**; v0.2 and all trained weights are preserved.

## Data and leakage controls

The Copernicus Marine / OSI-SAF processed daily observation cube spans 2015-01-01 through 2026-08-16 on a 52 x 100 grid. ERA5 u10, v10 and t2m are historical reanalysis at 00:00 UTC on initialization day, never full-day means or future observed forcing. Exact dates, midnight timestamps and grid alignment are checked. ERA5 reanalysis is not an operational future weather forecast.

Training: 2015-2023; validation: 2024; locked test: 2025-2026-08-16. All context and targets stay within their split. There are 584 matched initialization dates, 2025-01-07 through 2026-08-13. Normalization is derived exclusively from training, and was independently recomputed against the frozen metadata.

## Model and training

Persistence repeats the initialization observation. v0.1 introduced an additive residual CNN with clipping; v0.2 bounded the residual by available upward/downward concentration. v0.3 retains the bounded depthwise-separable network and adds three normalized ERA5 fields and three explicit forcing masks. Seven SIC fields, seven validity masks, ocean mask and two day-of-year channels plus six atmospheric channels give 23 inputs. The model has 10,995 parameters. Missing cells remain masked rather than open water.

Frozen CPU training used hidden_channels=24, batch_size=32, learning_rate=0.001, weight_decay=0.0001, maximum_epochs=30, patience=5, seed=26059, workers=0. Best epoch was 30 with validation MAE 4.3562331476203 pp. Validation was still improving at the epoch ceiling. This is a limitation, not a reason to retrain after viewing the locked test. No retraining occurred.

## Locked results

| Horizon | v0.3 MAE | v0.2 MAE | Persistence MAE | RMSE | Bias | Precision / Recall / F1 @15% |
|---|---:|---:|---:|---:|---:|---|
| 24H | 2.877915 | 2.965237 | 3.081866 | 5.876556 | 0.433528 | 0.988462 / 0.987772 / 0.988117 |
| 48H | 4.066660 | 4.177432 | 4.517298 | 8.164194 | 0.731748 | 0.982416 / 0.982073 / 0.982244 |
| 72H | 4.788987 | 4.916636 | 5.485350 | 9.525931 | 0.728548 | 0.979099 / 0.977634 / 0.978366 |

All error measures use percentage points. Each horizon has 1,358,384 valid pixels and 584 samples. Zero of 4,075,152 valid outputs require safety clipping. Recomputed v0.2 agrees with the frozen benchmark within 4e-9 pp. Aggregate versus daily means differ by less than 2e-8 pp due to floating-point reduction.

Mean horizon MAE: v0.3 3.911187 pp versus v0.2 4.019768 pp, a 2.7012% improvement. All three horizons improve; +48H and +72H satisfy the conservative no-degradation rule. Physical behavior and input-only forcing pass. Decision: ADOPT_V03.

## Paired daily bootstrap

10,000 paired date resamples, seed 26059. Differences below are v0.3 minus v0.2. These are IID date bootstrap intervals, not autocorrelation-aware confidence intervals; overlapping windows and temporal dependence limit inferential strength. Evidence is separate from the adoption rule.

| Horizon | Days v0.3 wins | Mean difference pp | 95% CI pp |
|---|---:|---:|---|
| 24H | 68.4932% | -0.087322 | [-0.105666, -0.069001] |
| 48H | 68.3219% | -0.110772 | [-0.135217, -0.086322] |
| 72H | 67.2945% | -0.127649 | [-0.159893, -0.095797] |

All intervals exclude zero under this bootstrap procedure. Persistence bootstrap is retained in the benchmark JSON.

## Seasons and Bharati local neighborhood

Existing target-date seasons are March-October (cold/growth) and November-February (warm/melt). The fixed local neighborhood is +/-1 degree around Bharati (-69.4068, 76.1953), using the existing evaluation mask.

| Region / season | Horizon | v0.3 | v0.2 | Persistence |
|---|---|---:|---:|---:|
| AUSTRAL_COLD_GROWTH_MAR_OCT | 24H | 3.276087 | 3.368521 | 3.518643 |
| AUSTRAL_WARM_MELT_NOV_FEB | 24H | 1.924154 | 1.999230 | 2.035633 |
| Bharati | 24H | 2.546267 | 2.575613 | 2.618233 |
| AUSTRAL_COLD_GROWTH_MAR_OCT | 48H | 4.537517 | 4.641249 | 5.075912 |
| AUSTRAL_WARM_MELT_NOV_FEB | 48H | 2.929442 | 3.057218 | 3.168130 |
| Bharati | 48H | 3.585785 | 3.673622 | 3.791964 |
| AUSTRAL_COLD_GROWTH_MAR_OCT | 72H | 5.245175 | 5.355774 | 6.069961 |
| AUSTRAL_WARM_MELT_NOV_FEB | 72H | 3.678036 | 3.847206 | 4.061649 |
| Bharati | 72H | 4.311641 | 4.405333 | 4.595633 |

## Provenance and reproduction

The existing completed locked result was reused and audited, not rerun for model selection. The evaluator refuses to overwrite an existing result. A reproduction can run `python -m scripts.evaluate_sea_ice_model_v03` in a separate checkout without an existing result after provisioning the exact ignored artifacts. Do not use a reproduction to tune against the test set.

- source_dataset_sha256: `5c14a6a05fc8c351edfb0eb3509b519be3339dc283a9e1b0dd82902ded6b0400`
- forcing_dataset_sha256: `ba09622e086ce522534ea640d9e59fe75f2b3874be4cd63063e7fdf9a72a5659`
- model_file_sha256: `aba2c90463130dae416658715f64a07a7643b89f4514045dedc8744d479e0cc7`
- normalization_period: `{'start': '2015-01-01', 'end': '2023-12-31'}`
- forcing_time_semantics: `00:00 UTC initialization-state only`

The benchmark JSON contains compact aggregate results only. No weights, NetCDF cubes, giant prediction arrays or credentials are committed. Operational behavior and API usage are documented in [Checkpoint 3](checkpoint-3-sea-ice-forecasting.md).
