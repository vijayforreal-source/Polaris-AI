from dataclasses import asdict
from datetime import UTC, datetime

from backend.environment.track_forcing import a76c_track
from backend.iceberg.baseline import constant_velocity_baseline, persistence_baseline
from backend.iceberg.hybrid.calibration import a76c_split, lambda_grid, select_lambda
from backend.iceberg.hybrid.model import effective_current_sampler
from backend.iceberg.hybrid.uncertainty import (
    empirical_coverage,
    empirical_radii,
    paired_bootstrap,
)
from backend.iceberg.motion import geodesic_inverse
from backend.iceberg.physics.evaluation import (
    A76CForcing,
    aggregate,
    evaluate_trajectory,
)
from backend.iceberg.physics.integrator import integrate_trajectory
from backend.iceberg.physics.models import HindcastTrajectory, IntervalEvaluation
from backend.iceberg.physics.parameters import NM_TO_METRES, paper_parameters


def _time(point) -> datetime:
    return datetime.combine(point.observation_date, datetime.min.time(), UTC)


def _physics_run(
    forcing: A76CForcing,
    start,
    end,
    model: str,
    ocean_sampler,
) -> HindcastTrajectory:
    return integrate_trajectory(
        model,
        _time(start),
        _time(end),
        start.latitude,
        start.longitude,
        ocean_sampler,
        forcing.wind_sampler if model == "P3_WDE17" else None,
        16.0 * NM_TO_METRES,
        7.0 * NM_TO_METRES,
        1.0,
        None,
        paper_parameters(),
    )


def _evaluate_indexes(
    forcing: A76CForcing,
    track,
    indexes: range,
    model_name: str,
    ocean_sampler,
    integrator_model: str,
) -> list[IntervalEvaluation]:
    results: list[IntervalEvaluation] = []
    for index in indexes:
        start, end = track[index], track[index + 1]
        trajectory = _physics_run(forcing, start, end, integrator_model, ocean_sampler)
        if trajectory.status == "COMPLETE":
            result = evaluate_trajectory(trajectory, start, end)
            results.append(IntervalEvaluation(model_name, *list(asdict(result).values())[1:]))
    return results


def _baseline_indexes(track, indexes: range, model: str) -> list[IntervalEvaluation]:
    results = []
    for index in indexes:
        start, end = track[index], track[index + 1]
        if model == "P0_PERSISTENCE":
            baseline = persistence_baseline(start, end)
            predicted_latitude, predicted_longitude = start.latitude, start.longitude
        elif index > 0:
            baseline = constant_velocity_baseline(track[index - 1], start, end)
            predicted_latitude = baseline.predicted_latitude
            predicted_longitude = baseline.predicted_longitude
        else:
            continue
        observed_km, observed_bearing = geodesic_inverse(
            start.latitude, start.longitude, end.latitude, end.longitude
        )
        predicted_km, predicted_bearing = geodesic_inverse(
            start.latitude,
            start.longitude,
            predicted_latitude,
            predicted_longitude,
        )
        bearing_error = None if predicted_km == 0 else abs(
            (predicted_bearing - observed_bearing + 180) % 360 - 180
        )
        results.append(
            IntervalEvaluation(
                model,
                start.observation_date.isoformat(),
                end.observation_date.isoformat(),
                baseline.forecast_horizon_hours,
                baseline.error_km,
                baseline.error_nm,
                observed_km,
                predicted_km,
                bearing_error,
                "COMPLETE",
            )
        )
    return results


def _serialise(results: list[IntervalEvaluation]) -> list[dict[str, object]]:
    return [asdict(result) for result in results]


def _compact_trajectory(trajectory: HindcastTrajectory) -> list[dict[str, object]]:
    # Six-hour output keeps API payloads compact without changing the one-hour integration.
    return [
        {
            "valid_at": point.valid_at.isoformat().replace("+00:00", "Z"),
            "latitude": point.latitude,
            "longitude": point.longitude,
        }
        for index, point in enumerate(trajectory.points)
        if index % 6 == 0 or index == len(trajectory.points) - 1
    ]


def run_a76c_hybrid_evaluation() -> dict[str, object]:
    track = a76c_track()
    split = a76c_split(len(track) - 1)
    search: list[dict[str, float]] = []
    with A76CForcing() as forcing:
        surface = forcing.ocean_sampler(0)
        depth_29m = forcing.ocean_sampler(1)
        for blend_lambda in lambda_grid():
            sampler = effective_current_sampler(surface, depth_29m, blend_lambda)
            results = _evaluate_indexes(
                forcing, track, split.fit, "H0_EFFECTIVE_CURRENT", sampler, "P2_SURFACE_CURRENT"
            )
            metrics = aggregate(results)
            search.append(
                {
                    "lambda": blend_lambda,
                    "mean_error_km": float(metrics["mean_error_km"]),
                    "median_error_km": float(metrics["median_error_km"]),
                }
            )
        selected = select_lambda(search)
        hybrid_sampler = effective_current_sampler(surface, depth_29m, selected)

        partitions: dict[str, dict[str, list[IntervalEvaluation]]] = {}
        for partition_name, indexes in (
            ("fit", split.fit),
            ("uncertainty_calibration", split.uncertainty_calibration),
            ("final_test", split.final_test),
        ):
            partitions[partition_name] = {
                "P0_PERSISTENCE": _baseline_indexes(track, indexes, "P0_PERSISTENCE"),
                "P1_CONSTANT_VELOCITY": _baseline_indexes(
                    track, indexes, "P1_CONSTANT_VELOCITY"
                ),
                "P2_SURFACE_CURRENT": _evaluate_indexes(
                    forcing, track, indexes, "P2_SURFACE_CURRENT", surface, "P2_SURFACE_CURRENT"
                ),
                "P3_WDE17_SURFACE": _evaluate_indexes(
                    forcing, track, indexes, "P3_WDE17_SURFACE", surface, "P3_WDE17"
                ),
                "H0_EFFECTIVE_CURRENT": _evaluate_indexes(
                    forcing,
                    track,
                    indexes,
                    "H0_EFFECTIVE_CURRENT",
                    hybrid_sampler,
                    "P2_SURFACE_CURRENT",
                ),
                "H1_WDE17_EFFECTIVE_CURRENT": _evaluate_indexes(
                    forcing,
                    track,
                    indexes,
                    "H1_WDE17_EFFECTIVE_CURRENT",
                    hybrid_sampler,
                    "P3_WDE17",
                ),
            }

        calibration_errors = [
            item.endpoint_error_km
            for item in partitions["uncertainty_calibration"]["H0_EFFECTIVE_CURRENT"]
        ]
        radii = empirical_radii(calibration_errors)
        test_hybrid = partitions["final_test"]["H0_EFFECTIVE_CURRENT"]
        test_surface = partitions["final_test"]["P2_SURFACE_CURRENT"]
        test_errors = [item.endpoint_error_km for item in test_hybrid]
        bootstrap = paired_bootstrap(
            test_errors, [item.endpoint_error_km for item in test_surface]
        )
        coverage = empirical_coverage(test_errors, radii)

        calibration_means = {
            model: float(aggregate(results)["mean_error_km"])
            for model, results in partitions["uncertainty_calibration"].items()
            if results
        }
        pretest_candidate = min(
            (
                "P2_SURFACE_CURRENT",
                "H0_EFFECTIVE_CURRENT",
                "P3_WDE17_SURFACE",
                "H1_WDE17_EFFECTIVE_CURRENT",
            ),
            key=lambda model: calibration_means[model],
        )
        hybrid_test_mean = float(aggregate(test_hybrid)["mean_error_km"])
        surface_test_mean = float(aggregate(test_surface)["mean_error_km"])
        production = (
            "H0_EFFECTIVE_CURRENT"
            if pretest_candidate == "H0_EFFECTIVE_CURRENT"
            and hybrid_test_mean < surface_test_mean
            and bool(bootstrap["conclusive_improvement"])
            else "P2_SURFACE_CURRENT"
        )

        last_index = split.final_test.stop - 1
        start, end = track[last_index], track[last_index + 1]
        last_trajectory = _physics_run(
            forcing, start, end, "P2_SURFACE_CURRENT", hybrid_sampler
        )
        last_evaluation = evaluate_trajectory(last_trajectory, start, end)

    return {
        "iceberg_id": "A76C",
        "model_name": "POLARIS HYBRID v0.1",
        "evaluation_mode": "HISTORICAL HINDCAST",
        "prediction_classification": "MODEL_PREDICTION",
        "split": {
            "fit": {"intervals": 20, "start": "2026-01-02", "end": "2026-05-21"},
            "uncertainty_calibration": {
                "intervals": 7,
                "start": "2026-05-21",
                "end": "2026-07-10",
            },
            "final_test": {"intervals": 7, "start": "2026-07-10", "end": "2026-08-27"},
        },
        "lambda_search": search,
        "selected_lambda": selected,
        "parameters_fitted": ["effective_current_lambda"],
        "metrics": {
            name: {model: aggregate(results) for model, results in models.items() if results}
            for name, models in partitions.items()
        },
        "paired_test_errors": {
            "surface_current": _serialise(test_surface),
            "hybrid_effective_current": _serialise(test_hybrid),
        },
        "paired_bootstrap": bootstrap,
        "uncertainty": {
            "label": "EMPIRICAL HINDCAST ERROR ENVELOPE",
            "calibration_intervals": 7,
            "radii_km": radii,
            "final_test_coverage": coverage,
        },
        "pretest_model_selection": pretest_candidate,
        "selected_production_candidate": production,
        "scientific_interpretation": (
            "Hybrid adoption requires lower locked-test mean error and a paired bootstrap "
            "interval wholly below zero; otherwise surface current remains the candidate."
        ),
        "hindcast_example": {
            "start": {
                "date": start.observation_date.isoformat(),
                "latitude": start.latitude,
                "longitude": start.longitude,
            },
            "actual_endpoint": {
                "date": end.observation_date.isoformat(),
                "latitude": end.latitude,
                "longitude": end.longitude,
            },
            "trajectory": _compact_trajectory(last_trajectory),
            "endpoint_error_km": last_evaluation.endpoint_error_km,
            "uncertainty_radii_km": radii,
            "forcing_provenance": {
                "surface": "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i / 0.494 m",
                "depth": "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i / 29.445 m",
            },
        },
    }
