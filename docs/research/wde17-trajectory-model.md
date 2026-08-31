# WDE17 trajectory-model traceability

## Primary sources

The implementation follows Wagner, Dell, and Eisenman (2017), *An Analytical Model of
Iceberg Drift*, Journal of Physical Oceanography 47, 1605–1616,
DOI `10.1175/JPO-D-16-0262.1`, and the authors' May 2017 MATLAB implementation
`WDE17_iceberg_model.m`. Both sources were inspected before translation.

## Published physics

WDE17 begins with iceberg momentum balance (paper Eq. 1), including acceleration,
Coriolis, pressure-gradient, water drag, air drag, wave radiation, and sea-ice drag. Its
analytical branch makes the documented approximations that acceleration is negligible,
pressure-gradient forcing is represented through geostrophic ocean velocity, iceberg
speed is small relative to wind, wave and sea-ice drag are neglected, and surface ocean
and surface-air velocities represent the forcing.

After those approximations, Eq. 3 is the steady force balance. POLARIS-AI implements its
analytical solution, Eq. 6:

`v_i = v_w + gamma * (-alpha k×v_a + beta v_a)`

where Eq. 7 defines

`gamma = sqrt[rho_a (rho_w-rho_i) C_a / (rho_w rho_i C_w)]`,

Eq. 8 defines

`alpha = (sqrt(1 + 4 Lambda^4) - 1) / (2 Lambda^3)`

and

`beta = sqrt[(1+Lambda^4)sqrt(1+4Lambda^4)-3Lambda^4-1] /
(sqrt(2) Lambda^3)`,

and Eq. 9 defines

`Lambda = C_w gamma |v_a| / (pi |f| S)`, with `S = LW/(L+W)`.

For numerical stability at `Lambda < 1e-3`, the code uses the paper's Eq. 10 series:
`alpha ≈ Lambda` and `beta ≈ Lambda^3`. The threshold is below the regime relevant to
A76C and avoids cancellation in double precision. Exact zero wind yields zero wind
contribution.

The posted MATLAB implementation evaluates only positive `|f|` and uses the
Northern-Hemisphere component form. POLARIS-AI retains the magnitude in Lambda and
reverses only the Eq. 6 cross-wind term according to the signed Coriolis parameter in the
Southern Hemisphere. It does not add another Coriolis acceleration.

## Parameters

| Parameter | Value | Unit | Source |
|---|---:|---|---|
| Seawater density | 1027 | kg m-3 | WDE17 |
| Air density | 1.2 | kg m-3 | WDE17 |
| Shelf-ice density | 850 | kg m-3 | Silva et al. (2006), cited by WDE17 |
| Water drag coefficient | 0.9 | dimensionless | Bigg et al. (1997), cited by WDE17 and authors' code |
| Air drag coefficient | 1.3 | dimensionless | Bigg et al. (1997), cited by WDE17 and authors' code |
| Earth rotation rate | 7.2921e-5 | rad s-1 | authors' reference code |

These give `gamma = 0.01874705`. Constants are immutable, named, unit-bearing, and cited
in `backend/iceberg/physics/parameters.py`. No value was fitted to A76C.

## POLARIS-AI extensions

The authors' demonstration uses nearest-neighbour spatial sampling, linear temporal
sampling, and flat degree translation. POLARIS-AI instead reuses its verified bilinear
spatial and linear temporal interpolation and performs WGS84 geodesic forward
propagation. Every integration step samples forcing at the model-predicted location.
Future USNIC positions are never passed to the sampler.

A deterministic test independently transcribes MATLAB lines 390–397 and agrees with the
Python velocity output within `1e-12 m s-1` under identical dimensions, latitude,
forcing, and constants.

## Applicability and omissions

A76C is 29,632 m long and 12,964 m wide; its WDE17 harmonic length is 9,018.435 m. The
paper identifies icebergs longer than about 12 km as a regime where wind-driven motion
is typically less than 10% of current-driven motion. A76C is therefore a relevant large
tabular test, but that regime statement is not a guarantee for each timestep.

Height, draft, thickness, and mass are not required by Eqs. 6–9 because height cancels
from the retained force ratios. They are not invented. Melt, grounding, sea-ice drag,
wave forcing, explicit pressure gradients, and the acceleration branch are not
implemented in this checkpoint.

