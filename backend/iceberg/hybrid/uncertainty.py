import numpy as np


def empirical_radii(errors_km: list[float]) -> dict[str, float]:
    if not errors_km or any(error < 0 for error in errors_km):
        raise ValueError("Non-negative calibration residuals are required")
    values = np.asarray(errors_km, dtype=float)
    return {
        "50": float(np.quantile(values, 0.50, method="higher")),
        "80": float(np.quantile(values, 0.80, method="higher")),
        "95": float(np.quantile(values, 0.95, method="higher")),
    }


def empirical_coverage(errors_km: list[float], radii_km: dict[str, float]) -> dict[str, float]:
    if not errors_km:
        raise ValueError("Test residuals are required")
    return {
        level: sum(error <= radius for error in errors_km) / len(errors_km)
        for level, radius in radii_km.items()
    }


def paired_bootstrap(
    hybrid_errors: list[float],
    reference_errors: list[float],
    seed: int = 26059,
    resamples: int = 10_000,
) -> dict[str, float | int | bool]:
    if len(hybrid_errors) != len(reference_errors) or not hybrid_errors:
        raise ValueError("Paired bootstrap requires equal non-empty error vectors")
    differences = np.asarray(hybrid_errors) - np.asarray(reference_errors)
    generator = np.random.default_rng(seed)
    indexes = generator.integers(0, len(differences), size=(resamples, len(differences)))
    means = differences[indexes].mean(axis=1)
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "seed": seed,
        "resamples": resamples,
        "mean_difference_km": float(differences.mean()),
        "ci95_lower_km": float(lower),
        "ci95_upper_km": float(upper),
        "conclusive_improvement": bool(upper < 0),
    }
