import math
from datetime import UTC, datetime, timedelta

import pytest
from pyproj import Geod

from backend.iceberg.physics.evaluation import skill_against_persistence
from backend.iceberg.physics.integrator import geodesic_step, integrate_trajectory
from backend.iceberg.physics.models import IntervalEvaluation
from backend.iceberg.physics.parameters import (
    NM_TO_METRES,
    paper_parameters,
    reference_code_parameters,
)
from backend.iceberg.physics.wde17 import (
    alpha_beta,
    analytical_velocity,
    coriolis_parameter,
    dimensionless_lambda,
    gamma,
    harmonic_length,
)


def test_published_constants_and_unit_conversion() -> None:
    parameters = paper_parameters()
    assert parameters.water_density.value == 1027.0
    assert parameters.air_density.value == 1.2
    assert parameters.ice_density.value == 850.0
    assert parameters.air_drag_coefficient.value == 1.3
    assert parameters.water_drag_coefficient.value == 0.9
    assert 16 * NM_TO_METRES == 29632.0
    assert gamma(parameters) == pytest.approx(0.018747, rel=1e-4)


def test_harmonic_length_and_coriolis_sign() -> None:
    assert harmonic_length(300.0, 200.0) == 120.0
    assert coriolis_parameter(-60.0) == pytest.approx(-coriolis_parameter(60.0))
    with pytest.raises(ValueError):
        harmonic_length(0, 10)


def test_lambda_and_alpha_beta_limits_are_finite() -> None:
    value = dimensionless_lambda(8.0, -55.0, 29632.0, 12964.0)
    assert value > 0
    for lambda_value in (0.0, 1e-12, 0.5, 1.0, 1e3):
        alpha, beta = alpha_beta(lambda_value)
        assert math.isfinite(alpha) and math.isfinite(beta)
        assert alpha >= 0 and beta >= 0
    assert alpha_beta(1e-8)[0] == pytest.approx(1e-8)
    assert alpha_beta(1e-4)[1] == pytest.approx(1e-12)


def test_python_equation_matches_authors_matlab_expression() -> None:
    """Independent transcription of posted MATLAB lines 390-397; tolerance 1e-12 m/s."""
    ocean_u, ocean_v = 0.11, -0.04
    wind_u, wind_v = 6.2, -2.7
    latitude, length, width = 55.0, 1500.0, 1000.0
    parameters = reference_code_parameters()
    wind_speed = math.hypot(wind_u, wind_v)
    ga = math.sqrt(
        1.2 * (1027.0 - 850.0) / 1027.0 / 850.0 * 1.3 / 0.9
    )
    harmonic = length * width / (length + width)
    ff = 2 * 7.2921e-5 * math.sin(math.radians(abs(latitude)))
    la = 0.9 * ga / ff * wind_speed / harmonic / math.pi
    a = (math.sqrt(1 + 4 * la**4) - 1) / (2 * la**3)
    b = math.sqrt((1 + la**4) * math.sqrt(1 + 4 * la**4) - 3 * la**4 - 1) / (
        math.sqrt(2) * la**3
    )
    expected_u = ocean_u + ga * (a * wind_v + b * wind_u)
    expected_v = ocean_v + ga * (-a * wind_u + b * wind_v)
    actual = analytical_velocity(
        ocean_u, ocean_v, wind_u, wind_v, latitude, length, width, parameters
    )
    assert actual.eastward == pytest.approx(expected_u, abs=1e-12)
    assert actual.northward == pytest.approx(expected_v, abs=1e-12)


def test_southern_hemisphere_crosswind_term_reverses() -> None:
    north = analytical_velocity(0, 0, 5, 0, 60, 1500, 1000)
    south = analytical_velocity(0, 0, 5, 0, -60, 1500, 1000)
    assert north.eastward == pytest.approx(south.eastward)
    assert north.northward == pytest.approx(-south.northward)


def test_zero_wind_is_current_only() -> None:
    result = analytical_velocity(0.2, -0.1, 0, 0, -55, 29632, 12964)
    assert result.eastward == 0.2
    assert result.northward == -0.1
    assert result.wind_contribution_speed == 0


def test_large_iceberg_has_smaller_wind_contribution_than_small_iceberg() -> None:
    small = analytical_velocity(0, 0, 8, 2, -55, 300, 200)
    large = analytical_velocity(0, 0, 8, 2, -55, 29632, 12964)
    assert large.wind_contribution_speed < small.wind_contribution_speed


def test_geodesic_step_matches_wgs84_forward() -> None:
    latitude, longitude = geodesic_step(-55, -35, 1, 0, 3600)
    expected_lon, expected_lat, _ = Geod(ellps="WGS84").fwd(-35, -55, 90, 3600)
    assert latitude == pytest.approx(expected_lat)
    assert longitude == pytest.approx(expected_lon)


def test_integrator_samples_predicted_position_without_future_track() -> None:
    sampled_positions: list[tuple[float, float]] = []

    def ocean(latitude: float, longitude: float, _time: datetime):
        sampled_positions.append((latitude, longitude))
        return 0.5, 0.0

    start = datetime(2026, 1, 1, tzinfo=UTC)
    trajectory = integrate_trajectory(
        "P2_SURFACE_CURRENT", start, start + timedelta(hours=3), 10, 20, ocean
    )
    assert trajectory.classification == "MODEL_PREDICTION"
    assert trajectory.evaluation_mode == "HINDCAST"
    assert len(sampled_positions) == 3
    assert sampled_positions[1] == pytest.approx(
        (trajectory.points[1].latitude, trajectory.points[1].longitude)
    )
    assert sampled_positions[1] != sampled_positions[0]


def test_forcing_domain_exit_is_not_clamped() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    trajectory = integrate_trajectory(
        "P2_SURFACE_CURRENT",
        start,
        start + timedelta(hours=2),
        10,
        20,
        lambda *_: (None, None),
    )
    assert trajectory.status == "OUT_OF_FORCING_DOMAIN"
    assert len(trajectory.points) == 1


def test_timestep_consistency_under_constant_forcing() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    runs = [
        integrate_trajectory(
            "P2_SURFACE_CURRENT",
            start,
            start + timedelta(hours=24),
            -55,
            -35,
            lambda *_: (0.2, 0.1),
            timestep_hours=step,
        )
        for step in (1, 3, 6)
    ]
    endpoints = [run.points[-1] for run in runs]
    for endpoint in endpoints[1:]:
        _, _, distance = Geod(ellps="WGS84").inv(
            endpoints[0].longitude,
            endpoints[0].latitude,
            endpoint.longitude,
            endpoint.latitude,
        )
        assert distance < 25.0


def test_skill_metric_uses_common_interval_mean_error() -> None:
    def item(model: str, error: float) -> IntervalEvaluation:
        return IntervalEvaluation(model, "a", "b", 1, error, error / 1.852, 1, 1, 0, "COMPLETE")

    assert skill_against_persistence([item("model", 5)], [item("persistence", 10)]) == 0.5
