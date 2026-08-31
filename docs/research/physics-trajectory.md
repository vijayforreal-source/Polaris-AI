# A76C physics-guided trajectory hindcast

## Evaluation design

This is historical **hindcast validation**, not an operational forecast. For each
consecutive pair among 35 USNIC A76C observations, a model starts from the first real
position, integrates over the exact interval, and reveals the second real position only
for endpoint evaluation. Forcing is Copernicus GLO12 `ANALYSIS` and ERA5
`REANALYSIS`; trajectory output is `MODEL_PREDICTION`.

Models are P0 persistence, P1 constant velocity, P2 surface-current advection, and P3
canonical WDE17 using the surface current. P2W is a separately labelled empirical
2%-wind comparator. Replacing the surface current with the verified 29.445 m and 92.326
m currents is reported only as depth sensitivity, not canonical WDE17.

The integrator uses a one-hour step and WGS84 geodesic forward propagation. Sampling is
bilinear in space and linear in time. It stops with `OUT_OF_FORCING_DOMAIN`; coordinates
are never clamped and missing forcing is never replaced with zero.

On the fixed 24–30 April representative interval, the 3-hour P3 endpoint differed from
the 1-hour endpoint by 1.090 km and the 6-hour endpoint by 2.909 km. These differences
are not negligible enough to justify coarsening, so the one-hour timestep was retained;
it also matches the finest forcing cadence and was not selected by endpoint tuning.

## Rolling one-interval results

| Model | Valid n | Mean error km | Median error km | RMSE km | P90 km | Max km |
|---|---:|---:|---:|---:|---:|---:|
| P0 persistence | 34 | 53.643 | 44.434 | 71.395 | 138.284 | 184.885 |
| P1 constant velocity | 33 | 65.583 | 49.757 | 81.924 | 144.423 | 201.767 |
| P2 surface current | 34 | 41.342 | 32.767 | 48.755 | 76.205 | 105.948 |
| P3 WDE17 surface | 33 | 41.599 | 33.861 | 49.447 | 83.364 | 108.187 |
| P2W 2%-wind comparator | 33 | 101.699 | 97.064 | 110.489 | 157.832 | 190.089 |

The final 20–27 August interval is unavailable to wind-dependent models because ERA5
ends on 26 August at 12:00 UTC. P0/P2 retain 34 intervals; P1 requires a preceding
velocity observation and has 33. P3/P2W have 33 because of wind coverage.

## Depth sensitivity

| Exploratory run | Valid n | Mean error km | Median error km |
|---|---:|---:|---:|
| P2 current at 29.445 m | 34 | 39.375 | 30.002 |
| P2 current at 92.326 m | 34 | 43.507 | 36.945 |
| WDE17-style at 29.445 m | 33 | 39.883 | 30.837 |
| WDE17-style at 92.326 m | 33 | 42.507 | 33.943 |

The 29 m sensitivity run is numerically best, but it is not selected as canonical physics:
A76C draft is unknown and no vertical weighting or draft model has been fitted.

## Skill and wind contribution

Skill is `1 - mean(model endpoint error) / mean(persistence endpoint error)`, calculated
only on intervals shared by the model and persistence. P2 surface skill is `+0.2293`, P3
surface skill is `+0.2061`, P1 skill is `-0.2181`, and P2W skill is `-0.9408`.

For canonical P3 integration steps, the wind-induced speed divided by sampled ocean
speed has mean `0.1018`, median `0.0692`, minimum `0.000009`, and maximum `5.0323`.
The large maximum occurs when local ocean speed approaches zero, so it must not be read
as typical wind dominance; the median is the robust summary.

## Model selection and limitations

P2 surface-current advection is the best canonical physics baseline: it has lower mean
and median error, one more valid interval, fewer assumptions, and better coverage than
canonical P3. The more complex published model is not declared the winner. The poor
P2W result supports caution about applying the 2% rule to this large Antarctic iceberg,
but a single track does not establish universal causation.

Weekly/date-only USNIC positions are sparse and aligned to 00:00 UTC by an explicit
quality convention. GLO12 is model analysis and ERA5 is reanalysis. This checkpoint
does not fit parameters or represent iceberg draft, mass, thickness, acceleration,
grounding, sea-ice drag, waves, uncertainty, or operational future forcing.

See `wde17-trajectory-model.md` for exact equations, constants, source attribution, and
the boundary between published physics and POLARIS-AI extensions.
