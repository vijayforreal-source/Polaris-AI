# Historical trajectory engine

Checkpoint 4 exposes the existing A76C scientific models through a reusable, typed hindcast service. It does not introduce a new model, refit a coefficient, or provide an operational forecast.

The request selects an observed starting position and UTC time, one of the supported 6/12/24/48/72-hour horizons, and a previously evaluated model. At each integration step, the engine samples Copernicus GLO12 analysis currents—and ERA5 reanalysis winds when required—at the model-predicted position. Future USNIC positions are not consulted during integration. An exact-date USNIC endpoint may be attached only after integration for historical evaluation.

## Models and status

- `P2_SURFACE_CURRENT`: production candidate for the historical demo.
- `WDE17_SURFACE`: published-physics reference implementation.
- `H0_EFFECTIVE_CURRENT_HYBRID`: experimental effective-current model.
- `H1_HYBRID_WDE17_STYLE`: experimental WDE17-style hybrid.

Only H0 exposes the existing empirical 50/80/95 percent hindcast error radii. These sparse historical error envelopes are not guaranteed operational forecast probabilities.

## Availability boundary

The service never extrapolates beyond locally verified environmental forcing. An incomplete integration returns `FORCING_DATA_UNAVAILABLE_FOR_REQUESTED_HORIZON`, the achieved partial horizon, no endpoint, and a scientific warning. The current interface is therefore an A76C **HISTORICAL HINDCAST** demonstration, not live iceberg forecasting.

The A76C analysis map is separate from the Bharati/Prydz Bay mission map. It does not place A76C in the Bharati operating region or imply geographic proximity.
