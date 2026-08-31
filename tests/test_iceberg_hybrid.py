from datetime import UTC, datetime

import pytest

from backend.iceberg.hybrid.calibration import a76c_split, lambda_grid, select_lambda
from backend.iceberg.hybrid.model import blend_components, effective_current_sampler
from backend.iceberg.hybrid.uncertainty import (
    empirical_coverage,
    empirical_radii,
    paired_bootstrap,
)


def test_chronological_split_is_ordered_complete_and_disjoint() -> None:
    split = a76c_split()
    assert list(split.fit) == list(range(20))
    assert list(split.uncertainty_calibration) == list(range(20, 27))
    assert list(split.final_test) == list(range(27, 34))
    assert set(split.fit).isdisjoint(split.final_test)
    assert max(split.uncertainty_calibration) < min(split.final_test)


def test_lambda_grid_is_bounded_and_deliberately_coarse() -> None:
    grid = lambda_grid()
    assert grid[0] == 0.0 and grid[-1] == 1.0
    assert len(grid) == 21
    assert all(0 <= value <= 1 for value in grid)


def test_effective_current_convex_blend() -> None:
    assert blend_components(1, 2, 3, 6, 0.25) == pytest.approx((1.5, 3.0))
    with pytest.raises(ValueError):
        blend_components(1, 2, 3, 4, 1.1)


def test_effective_sampler_preserves_missing_values() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    valid = effective_current_sampler(lambda *_: (1.0, 2.0), lambda *_: (3.0, 4.0), 0.5)
    missing = effective_current_sampler(lambda *_: (1.0, 2.0), lambda *_: (None, None), 0.5)
    assert valid(0, 0, now) == (2.0, 3.0)
    assert missing(0, 0, now) == (None, None)


def test_calibration_selection_is_deterministic_and_prefers_simple_tie() -> None:
    search = [
        {"lambda": 0.5, "mean_error_km": 10.0, "median_error_km": 9.0},
        {"lambda": 0.0, "mean_error_km": 10.0, "median_error_km": 8.0},
    ]
    assert select_lambda(search) == 0.0


def test_empirical_radii_and_coverage() -> None:
    radii = empirical_radii([1, 2, 3, 4, 5])
    assert radii == {"50": 3.0, "80": 5.0, "95": 5.0}
    assert empirical_coverage([2, 4, 6], radii) == pytest.approx(
        {"50": 1 / 3, "80": 2 / 3, "95": 2 / 3}
    )


def test_paired_bootstrap_is_reproducible() -> None:
    first = paired_bootstrap([8, 9, 10], [10, 10, 10], seed=42, resamples=500)
    second = paired_bootstrap([8, 9, 10], [10, 10, 10], seed=42, resamples=500)
    assert first == second
    assert first["mean_difference_km"] == pytest.approx(-1.0)
