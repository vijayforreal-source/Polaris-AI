# POLARIS Hybrid v0.1 — calibrated A76C hindcast

## Chronological design

The 34 verified A76C displacement intervals remain in time order:

| Partition | Interval count | Dates | Permitted use |
|---|---:|---|---|
| Fit | 20 | 2026-01-02 to 2026-05-21 | Fit lambda only |
| Uncertainty calibration | 7 | 2026-05-21 to 2026-07-10 | Model-selection evidence and empirical radii |
| Locked final test | 7 | 2026-07-10 to 2026-08-27 | Final evaluation only |

No interval is shuffled or shared between partitions. The final test is not used for
feature selection, lambda fitting, uncertainty-radius calibration, or pretest model
selection.

## Effective-current model

The single fitted parameter is a convex current blend:

`U_eff = (1-lambda) U_surface + lambda U_29.445m`, with `0 <= lambda <= 1`.

H0 advects with this field. H1 supplies the same field to the otherwise unchanged WDE17
analytical wind relationship. Lambda is an empirical effective-current weight—not
iceberg draft, vertical extent, or a physically measured depth.

## Calibration

A deterministic grid of `0.00, 0.05, ..., 1.00` was evaluated with one-hour true
Lagrangian integration on the 20 fit intervals. The objective was mean endpoint error;
ties would prefer smaller lambda. The selected lambda is `0.45`, with fit mean error
`32.174 km` and median error `26.048 km`. Surface current on the same intervals gives
`35.243 km` mean and `29.351 km` median.

The objective is broad near its minimum: lambda 0.40, 0.45, and 0.50 have mean errors
32.259, 32.174, and 32.187 km. The 0.05-grid selection must not be interpreted as a
precisely known physical quantity.

## Uncertainty-calibration period

On the seven middle intervals, H0 has mean error `61.774 km` and median `58.081 km`;
surface current has mean `64.572 km` and median `72.304 km`. H0 is the best mean-error
candidate within the predefined canonical/hybrid comparison before opening the final
test.

H0 residual-distance quantiles, using NumPy's conservative observed-value (`higher`)
quantile rule, define an **EMPIRICAL HINDCAST ERROR ENVELOPE**:

- 50% radius: 58.081 km
- 80% radius: 91.030 km
- 95% radius: 106.961 km

These are sparse historical residual envelopes, not guaranteed coverage probabilities.
Only endpoint error is calibrated; no intermediate-time probabilistic corridor is
claimed.

## Locked test

| Model | Valid n | Mean km | Median km | RMSE km | P90 km | Max km |
|---|---:|---:|---:|---:|---:|---:|
| Persistence | 7 | 45.846 | 44.485 | 52.055 | 71.236 | 94.628 |
| Constant velocity | 7 | 46.220 | 49.757 | 48.596 | 60.278 | 66.872 |
| Surface current | 7 | 35.538 | 34.092 | 40.476 | 59.732 | 59.914 |
| WDE17 surface | 6 | 32.320 | 27.360 | 37.130 | 55.544 | 61.050 |
| H0 effective current | 7 | 33.369 | 34.394 | 37.705 | 54.141 | 59.709 |
| H1 WDE17 effective current | 6 | 30.014 | 27.937 | 33.737 | 48.641 | 52.801 |

Wind-dependent models have six valid intervals because ERA5 does not cover the final
20–27 August interval. Their lower errors are therefore not directly comparable to the
seven-interval current-only results without acknowledging the different sample.

## Paired comparison and coverage

Across the same seven test intervals, H0 minus surface-current endpoint error averages
`-2.169 km`. A 10,000-resample paired bootstrap with fixed seed `26059` gives a 95%
interval `[-5.271, +0.535] km`. Because zero lies inside the interval, improvement is
**not conclusive**.

Observed locked-test coverage of calibration radii is:

- 50% radius: 6/7 = 85.7%
- 80% radius: 7/7 = 100%
- 95% radius: 7/7 = 100%

The sample is too small to interpret these frequencies as validation of nominal
probabilities.

## Selection and limitations

Surface-current advection remains the production candidate. H0 reduces locked mean
error, but not conclusively, and adds a fitted parameter. No wind/drag coefficient,
depth weight beyond lambda, draft, thickness, mass, or final-test quantity is fitted.
This remains historical hindcast evaluation using GLO12 `ANALYSIS`, ERA5 `REANALYSIS`,
USNIC `OBSERVATION`, and `MODEL_PREDICTION` outputs—not an operational forecast.
