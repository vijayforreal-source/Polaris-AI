import math
from dataclasses import dataclass

from backend.iceberg.physics.parameters import WDE17Parameters, paper_parameters


@dataclass(frozen=True)
class DriftVelocity:
    eastward: float
    northward: float
    gamma: float
    coriolis_parameter: float
    lambda_value: float
    alpha: float
    beta: float
    wind_contribution_speed: float


def harmonic_length(length_m: float, width_m: float) -> float:
    if length_m <= 0 or width_m <= 0:
        raise ValueError("Iceberg horizontal dimensions must be positive")
    return length_m * width_m / (length_m + width_m)


def coriolis_parameter(latitude: float, rotation_rate: float = 7.2921e-5) -> float:
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90 degrees")
    return 2.0 * rotation_rate * math.sin(math.radians(latitude))


def gamma(parameters: WDE17Parameters | None = None) -> float:
    p = parameters or paper_parameters()
    rho_w = p.water_density.value
    rho_a = p.air_density.value
    rho_i = p.ice_density.value
    return math.sqrt(
        rho_a
        * (rho_w - rho_i)
        / (rho_w * rho_i)
        * p.air_drag_coefficient.value
        / p.water_drag_coefficient.value
    )


def dimensionless_lambda(
    wind_speed: float,
    latitude: float,
    length_m: float,
    width_m: float,
    parameters: WDE17Parameters | None = None,
) -> float:
    p = parameters or paper_parameters()
    f_magnitude = abs(coriolis_parameter(latitude, p.earth_rotation_rate.value))
    if f_magnitude == 0:
        raise ValueError("WDE17 Lambda is undefined at the equator")
    return (
        p.water_drag_coefficient.value
        * gamma(p)
        * wind_speed
        / (math.pi * f_magnitude * harmonic_length(length_m, width_m))
    )


def alpha_beta(lambda_value: float) -> tuple[float, float]:
    """WDE17 Eq. 8, with its Eq. 10 small-Lambda series for stability."""
    if lambda_value < 0:
        raise ValueError("Lambda cannot be negative")
    if lambda_value == 0:
        return 0.0, 0.0
    if lambda_value < 1e-3:
        # WDE17 Eq. 10: alpha~Lambda and beta~Lambda^3.
        return lambda_value, lambda_value**3
    root = math.sqrt(1.0 + 4.0 * lambda_value**4)
    alpha = 2.0 * lambda_value / (root + 1.0)
    beta_radicand = (
        (1.0 + lambda_value**4) * root - 3.0 * lambda_value**4 - 1.0
    )
    beta = math.sqrt(max(0.0, beta_radicand)) / (
        math.sqrt(2.0) * lambda_value**3
    )
    return alpha, beta


def analytical_velocity(
    ocean_east: float,
    ocean_north: float,
    wind_east: float,
    wind_north: float,
    latitude: float,
    length_m: float,
    width_m: float,
    parameters: WDE17Parameters | None = None,
) -> DriftVelocity:
    """WDE17 Eq. 6 using signed-hemisphere cross-wind orientation."""
    p = parameters or paper_parameters()
    f_value = coriolis_parameter(latitude, p.earth_rotation_rate.value)
    wind_speed = math.hypot(wind_east, wind_north)
    lambda_value = dimensionless_lambda(
        wind_speed, latitude, length_m, width_m, p
    )
    alpha, beta = alpha_beta(lambda_value)
    gamma_value = gamma(p)
    # Eq. 6 is -alpha k x va + beta va. The MATLAB code assumes f>0.
    # Reversing the cross-wind term with sign(f) extends it consistently southward.
    hemisphere = 1.0 if f_value >= 0 else -1.0
    wind_east_contribution = gamma_value * (
        hemisphere * alpha * wind_north + beta * wind_east
    )
    wind_north_contribution = gamma_value * (
        -hemisphere * alpha * wind_east + beta * wind_north
    )
    return DriftVelocity(
        eastward=ocean_east + wind_east_contribution,
        northward=ocean_north + wind_north_contribution,
        gamma=gamma_value,
        coriolis_parameter=f_value,
        lambda_value=lambda_value,
        alpha=alpha,
        beta=beta,
        wind_contribution_speed=math.hypot(
            wind_east_contribution, wind_north_contribution
        ),
    )
