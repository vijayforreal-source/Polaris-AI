# POLARIS Sea-Ice Residual CNN v0.1

## Scope and scientific status

This checkpoint evaluates a compact learned sea-ice model in a historical forecast benchmark. Inputs and targets are verified Copernicus Marine / OSI SAF observations. Model outputs are classified as `MODEL_PREDICTION`; targets remain `OBSERVATION`. The model is not an operational forecast service, and no forecast field is exposed in the frontend or API.

## Dataset and chronological design

The immutable processed source is `data/processed/forecasting/sea_ice_bharati_daily.nc`, SHA-256 `5c14a6a05fc8c351edfb0eb3509b519be3339dc283a9e1b0dd82902ded6b0400`. It contains 4,246 daily fields on a 52 by 100 provider-regridded regional grid from 2015-01-01 through 2026-08-16. The provider-valid ocean mask contains 2,439 cells.

The split was not randomized:

- training: 2015-01-01 through 2023-12-31;
- validation: 2024-01-01 through 2024-12-31;
- locked test: 2025-01-01 through 2026-08-16.

Each sample and all of its seven context days and three targets remain wholly inside its split. Architecture and epoch selection used validation data only. The locked test was evaluated once after the weights were frozen.

## Architecture and residual formulation

The network is a 5,443-parameter persistence-residual CNN. It uses one standard 3 by 3 convolution, three depthwise-separable convolution blocks, and a three-channel residual head. Spatial padding preserves the 52 by 100 grid. The three predictions are

`prediction(h) = clamp(latest observation + learned residual(h), 0, 1)`

for +24 h, +48 h, and +72 h. This skip connection makes persistence the model's explicit starting point. The compact design was selected to provide a practical CPU benchmark rather than introduce an unnecessarily large U-Net or Transformer.

## Inputs, normalization, and missing data

Seventeen input channels are used:

- seven daily concentration fields;
- seven matching finite-value masks;
- the static provider-valid ocean mask;
- sine and cosine of initialization day-of-year.

Concentration is divided by 100 for internal 0 to 1 representation. NaN is replaced numerically by zero only inside the tensor while explicit validity channels preserve its meaning. Invalid target cells are excluded from masked MAE and all evaluation metrics. Missing data is never interpreted scientifically as open water.

## Training and model selection

PyTorch 2.13.0 CPU was used with seed 26059, AdamW, learning rate 0.001, weight decay 0.0001, batch size 32, equal horizon weights, and early-stopping patience 3. A two-epoch smoke run verified decreasing finite loss and acceptable memory use. One serious run was then performed for at most 10 epochs. Validation MAE improved through epoch 10, which was selected at 4.529 percentage points; the run reached its configured epoch ceiling before early stopping fired. No test-guided hyperparameter tuning was performed.

## Locked-test results

The seven-day context and common three-day target requirement produce 584 initialization dates for every horizon. Metrics use the same finite provider-valid cells for the CNN and persistence.

| Horizon | CNN MAE (pp) | CNN RMSE (pp) | CNN bias (pp) | Persistence MAE (pp) | MAE skill |
|---|---:|---:|---:|---:|---:|
| +24 h | 2.986 | 6.095 | 0.195 | 3.082 | 3.10% |
| +48 h | 4.253 | 8.542 | 0.390 | 4.517 | 5.84% |
| +72 h | 5.041 | 10.030 | 0.468 | 5.485 | 8.10% |

Mean MAE across horizons is 4.094 pp for the CNN and 4.362 pp for sample-matched persistence. For reference, the original Checkpoint-1 persistence MAEs were 3.072, 4.511, and 5.482 pp, with a 4.355 pp horizon mean; the slight differences are caused by the common seven-day-context sample set.

At the 15% concentration threshold, CNN precision/recall/F1 are 0.9881/0.9871/0.9876 at +24 h, 0.9821/0.9805/0.9813 at +48 h, and 0.9780/0.9760/0.9770 at +72 h.

## Paired and bootstrap comparison

The CNN beats persistence on 61.1%, 65.4%, and 69.2% of initialization days at +24/+48/+72 h. Mean paired MAE improvements are 0.096, 0.264, and 0.444 pp respectively.

A paired bootstrap over initialization dates used seed 26059 and 10,000 resamples. The mean CNN-minus-persistence daily MAE differences and 95% intervals are:

- +24 h: -0.096 pp, interval [-0.118, -0.073];
- +48 h: -0.264 pp, interval [-0.314, -0.215];
- +72 h: -0.444 pp, interval [-0.514, -0.376].

All intervals exclude zero for this locked test. This supports an improvement over persistence on this regional historical benchmark, but does not establish operational generalization.

## Seasonal and Bharati-local performance

| Horizon | Cold/growth CNN / persistence MAE (pp) | Warm/melt CNN / persistence MAE (pp) | Bharati-local CNN / persistence MAE (pp) |
|---|---:|---:|---:|
| +24 h | 3.390 / 3.519 | 2.019 / 2.036 | 2.577 / 2.618 |
| +48 h | 4.733 / 5.076 | 3.095 / 3.168 | 3.654 / 3.792 |
| +72 h | 5.507 / 6.070 | 3.906 / 4.062 | 4.366 / 4.596 |

Cold/growth is March through October; warm/melt is November through February. The fixed Bharati neighborhood contains the same 41 valid-ocean cells used in Checkpoint 1. Improvement occurs in both seasonal groups and at all three local horizons, with a larger absolute regional gain at longer lead time.

## Artifacts and reproducibility

Weights are stored in the ignored file `models/sea_ice/polaris_sea_ice_residual_cnn_v0_1.pt`, SHA-256 `aa16f47643572dbc8f802f325aca7be1a8b7157de5733fa445f024de57c6c55d`. Adjacent safe metadata records architecture, source checksum, training configuration, epoch history, framework version, and model checksum. `scripts/train_sea_ice_model.py` refuses to overwrite an existing model without an explicit flag. `scripts/evaluate_sea_ice_model.py` loads frozen weights without retraining.

Ignored NetCDF analysis artifacts contain mean absolute-error maps, AI-minus-persistence maps, and deterministic +72 h examples for the first, middle, and largest-persistence-error initialization dates. These contain only verified observations and model predictions; no synthetic observations are created.

## Output clipping and limitations

The final persistence-plus-residual output is constrained to 0 to 100%. Across valid locked-test output pixels, 31.95% were affected by clipping. This is high and is reported explicitly; a bounded residual parameterization is a priority for later model improvement.

The model uses concentration history, masks, and seasonal encoding only. It does not use wind, ocean currents, or other multimodal forcing. The regional dataset is a provider-regridded subset, the test period ends in August 2026 rather than covering two complete years, and performance is demonstrated only for this historical Bharati/Prydz Bay benchmark. Persistence remains retained as the mandatory fallback and comparator even though the CNN satisfies the stated benchmark adoption rule.
