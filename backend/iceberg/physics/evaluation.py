from contextlib import AbstractContextManager
from dataclasses import asdict
from datetime import UTC, datetime
from statistics import mean, median

import numpy as np
import xarray as xr

from backend.environment.copernicus_currents import current_files
from backend.environment.era5_wind import load_wind_dataset
from backend.environment.sampling import interpolate_vector
from backend.iceberg.baseline import constant_velocity_baseline, persistence_baseline
from backend.iceberg.history import load_history, tracks_by_iceberg
from backend.iceberg.motion import geodesic_inverse
from backend.iceberg.physics.integrator import integrate_trajectory
from backend.iceberg.physics.models import HindcastTrajectory, IntervalEvaluation
from backend.iceberg.physics.parameters import NM_TO_METRES, paper_parameters


class A76CForcing(AbstractContextManager):
    """Read-only environmental samplers used at each model-predicted position."""

    def __init__(self) -> None:
        self.ocean = [xr.open_dataset(path).sortby("latitude") for path in current_files()]
        self.wind = load_wind_dataset().sortby("latitude")
        self.depths = [float(dataset.depth.item()) for dataset in self.ocean]

    def ocean_sampler(self, depth_index: int):
        dataset = self.ocean[depth_index]

        def sample(latitude: float, longitude: float, valid_at: datetime):
            u_value, v_value, _ = interpolate_vector(dataset, latitude, longitude, valid_at)
            return u_value, v_value

        return sample

    def wind_sampler(self, latitude: float, longitude: float, valid_at: datetime):
        u_value, v_value, _ = interpolate_vector(
            self.wind, latitude, longitude, valid_at, u_name="u10", v_name="v10"
        )
        return u_value, v_value

    def __exit__(self, *args) -> None:
        for dataset in self.ocean:
            dataset.close()
        self.wind.close()


def _time(point) -> datetime:
    return datetime.combine(point.observation_date, datetime.min.time(), UTC)


def _bearing_difference(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def evaluate_trajectory(trajectory: HindcastTrajectory, start, actual) -> IntervalEvaluation:
    if trajectory.status != "COMPLETE":
        raise ValueError(f"Cannot evaluate incomplete trajectory: {trajectory.status}")
    endpoint = trajectory.points[-1]
    error_km, _ = geodesic_inverse(
        endpoint.latitude, endpoint.longitude, actual.latitude, actual.longitude
    )
    observed_km, observed_bearing = geodesic_inverse(
        start.latitude, start.longitude, actual.latitude, actual.longitude
    )
    predicted_km, predicted_bearing = geodesic_inverse(
        start.latitude, start.longitude, endpoint.latitude, endpoint.longitude
    )
    return IntervalEvaluation(
        model=trajectory.model,
        start_date=start.observation_date.isoformat(),
        end_date=actual.observation_date.isoformat(),
        horizon_hours=(_time(actual) - _time(start)).total_seconds() / 3600.0,
        endpoint_error_km=error_km,
        endpoint_error_nm=error_km / 1.852,
        observed_displacement_km=observed_km,
        predicted_displacement_km=predicted_km,
        bearing_error_degrees=_bearing_difference(predicted_bearing, observed_bearing),
        status=trajectory.status,
    )


def aggregate(evaluations: list[IntervalEvaluation]) -> dict[str, float | int | None]:
    errors = np.array([item.endpoint_error_km for item in evaluations], dtype=float)
    bearing_errors = [
        item.bearing_error_degrees
        for item in evaluations
        if item.bearing_error_degrees is not None
    ]
    return {
        "valid_intervals": len(errors),
        "mean_error_km": float(np.mean(errors)),
        "median_error_km": float(np.median(errors)),
        "rmse_error_km": float(np.sqrt(np.mean(errors**2))),
        "p90_error_km": float(np.percentile(errors, 90)),
        "maximum_error_km": float(np.max(errors)),
        "mean_error_nm": float(np.mean(errors) / 1.852),
        "median_bearing_error_degrees": (
            float(np.median(bearing_errors)) if bearing_errors else None
        ),
    }


def skill_against_persistence(
    model: list[IntervalEvaluation], persistence: list[IntervalEvaluation]
) -> float:
    persistence_by_interval = {
        (item.start_date, item.end_date): item.endpoint_error_km for item in persistence
    }
    paired = [
        (item.endpoint_error_km, persistence_by_interval[(item.start_date, item.end_date)])
        for item in model
        if (item.start_date, item.end_date) in persistence_by_interval
    ]
    if not paired or mean(value[1] for value in paired) == 0:
        raise ValueError("Skill requires common intervals with nonzero persistence error")
    return 1.0 - mean(value[0] for value in paired) / mean(value[1] for value in paired)


def run_a76c_evaluation(timestep_hours: float = 1.0) -> dict[str, object]:
    track = tracks_by_iceberg(load_history().points)["A76C"]
    length_m = 16.0 * NM_TO_METRES
    width_m = 7.0 * NM_TO_METRES
    evaluations: dict[str, list[IntervalEvaluation]] = {
        "P0_PERSISTENCE": [],
        "P1_CONSTANT_VELOCITY": [],
        "P2_SURFACE_CURRENT": [],
        "P3_WDE17_SURFACE": [],
        "P2W_EMPIRICAL_2_PERCENT_WIND": [],
        "P2_CURRENT_29M": [],
        "P2_CURRENT_92M": [],
        "P3_WDE17_STYLE_29M": [],
        "P3_WDE17_STYLE_92M": [],
    }
    failures: list[dict[str, str]] = []
    wind_ratios: list[float] = []
    with A76CForcing() as forcing:
        for index, (start, actual) in enumerate(zip(track, track[1:], strict=False)):
            baseline = persistence_baseline(start, actual)
            evaluations["P0_PERSISTENCE"].append(
                IntervalEvaluation(
                    "P0_PERSISTENCE",
                    start.observation_date.isoformat(),
                    actual.observation_date.isoformat(),
                    baseline.forecast_horizon_hours,
                    baseline.error_km,
                    baseline.error_nm,
                    geodesic_inverse(
                        start.latitude, start.longitude, actual.latitude, actual.longitude
                    )[0],
                    None,
                    0.0,
                    "COMPLETE",
                )
            )
            if index > 0:
                cv = constant_velocity_baseline(track[index - 1], start, actual)
                _, observed_bearing = geodesic_inverse(
                    start.latitude, start.longitude, actual.latitude, actual.longitude
                )
                _, predicted_bearing = geodesic_inverse(
                    start.latitude, start.longitude, cv.predicted_latitude, cv.predicted_longitude
                )
                predicted_km = geodesic_inverse(
                    start.latitude, start.longitude, cv.predicted_latitude, cv.predicted_longitude
                )[0]
                evaluations["P1_CONSTANT_VELOCITY"].append(
                    IntervalEvaluation(
                        "P1_CONSTANT_VELOCITY",
                        start.observation_date.isoformat(),
                        actual.observation_date.isoformat(),
                        cv.forecast_horizon_hours,
                        cv.error_km,
                        cv.error_nm,
                        geodesic_inverse(
                            start.latitude, start.longitude, actual.latitude, actual.longitude
                        )[0],
                        predicted_km,
                        _bearing_difference(predicted_bearing, observed_bearing),
                        "COMPLETE",
                    )
                )
            for depth_index, suffix in enumerate(("SURFACE", "29M", "92M")):
                current_key = "P2_SURFACE_CURRENT" if depth_index == 0 else f"P2_CURRENT_{suffix}"
                trajectory = integrate_trajectory(
                    "P2_SURFACE_CURRENT",
                    _time(start),
                    _time(actual),
                    start.latitude,
                    start.longitude,
                    forcing.ocean_sampler(depth_index),
                    timestep_hours=timestep_hours,
                    forcing_depth_m=forcing.depths[depth_index],
                )
                if trajectory.status == "COMPLETE":
                    result = evaluate_trajectory(trajectory, start, actual)
                    evaluations[current_key].append(
                        IntervalEvaluation(current_key, *list(asdict(result).values())[1:])
                    )
                else:
                    failures.append(
                        {
                            "model": current_key,
                            "date": actual.observation_date.isoformat(),
                            "status": trajectory.status,
                        }
                    )
                wde_key = "P3_WDE17_SURFACE" if depth_index == 0 else f"P3_WDE17_STYLE_{suffix}"
                wde = integrate_trajectory(
                    "P3_WDE17",
                    _time(start),
                    _time(actual),
                    start.latitude,
                    start.longitude,
                    forcing.ocean_sampler(depth_index),
                    forcing.wind_sampler,
                    length_m,
                    width_m,
                    timestep_hours,
                    forcing.depths[depth_index],
                    paper_parameters(),
                )
                if wde.status == "COMPLETE":
                    result = evaluate_trajectory(wde, start, actual)
                    evaluations[wde_key].append(
                        IntervalEvaluation(wde_key, *list(asdict(result).values())[1:])
                    )
                    if depth_index == 0:
                        wind_ratios.extend(wde.wind_contribution_ratios)
                else:
                    failures.append(
                        {
                            "model": wde_key,
                            "date": actual.observation_date.isoformat(),
                            "status": wde.status,
                        }
                    )
            empirical = integrate_trajectory(
                "P2W_EMPIRICAL_2_PERCENT_WIND",
                _time(start),
                _time(actual),
                start.latitude,
                start.longitude,
                forcing.ocean_sampler(0),
                forcing.wind_sampler,
                timestep_hours=timestep_hours,
            )
            if empirical.status == "COMPLETE":
                evaluations["P2W_EMPIRICAL_2_PERCENT_WIND"].append(
                    evaluate_trajectory(empirical, start, actual)
                )
            else:
                failures.append(
                    {
                        "model": empirical.model,
                        "date": actual.observation_date.isoformat(),
                        "status": empirical.status,
                    }
                )
    aggregates = {key: aggregate(value) for key, value in evaluations.items() if value}
    skills = {
        key: skill_against_persistence(value, evaluations["P0_PERSISTENCE"])
        for key, value in evaluations.items()
        if key != "P0_PERSISTENCE" and value
    }
    ranked = sorted(
        aggregates,
        key=lambda key: (aggregates[key]["median_error_km"], aggregates[key]["mean_error_km"]),
    )
    return {
        "iceberg_id": "A76C",
        "evaluation_mode": "HINDCAST",
        "prediction_classification": "MODEL_PREDICTION",
        "timestep_hours": timestep_hours,
        "dimensions": {
            "length_nm": 16.0,
            "width_nm": 7.0,
            "length_m": length_m,
            "width_m": width_m,
        },
        "models": aggregates,
        "skill_vs_persistence_mean_error": skills,
        "wind_contribution_ratio": {
            "mean": mean(wind_ratios),
            "median": median(wind_ratios),
            "minimum": min(wind_ratios),
            "maximum": max(wind_ratios),
        },
        "best_by_median_then_mean": ranked[0],
        "failures": failures,
        "interval_results": {
            key: [asdict(item) for item in value] for key, value in evaluations.items()
        },
    }


def run_timestep_sensitivity(interval_index: int = 16) -> dict[str, object]:
    """Compare 1/3/6-hour P3 endpoints on one fixed representative interval."""
    track = tracks_by_iceberg(load_history().points)["A76C"]
    start, end = track[interval_index], track[interval_index + 1]
    trajectories: dict[float, HindcastTrajectory] = {}
    with A76CForcing() as forcing:
        for timestep in (1.0, 3.0, 6.0):
            trajectories[timestep] = integrate_trajectory(
                "P3_WDE17",
                _time(start),
                _time(end),
                start.latitude,
                start.longitude,
                forcing.ocean_sampler(0),
                forcing.wind_sampler,
                16.0 * NM_TO_METRES,
                7.0 * NM_TO_METRES,
                timestep,
                forcing.depths[0],
                paper_parameters(),
            )
    reference = trajectories[1.0].points[-1]
    differences = {}
    for timestep, trajectory in trajectories.items():
        endpoint = trajectory.points[-1]
        differences[f"{timestep:g}h"] = {
            "status": trajectory.status,
            "endpoint_latitude": endpoint.latitude,
            "endpoint_longitude": endpoint.longitude,
            "difference_from_1h_metres": geodesic_inverse(
                reference.latitude,
                reference.longitude,
                endpoint.latitude,
                endpoint.longitude,
            )[0]
            * 1000.0,
        }
    return {
        "start_date": start.observation_date.isoformat(),
        "end_date": end.observation_date.isoformat(),
        "model": "P3_WDE17_SURFACE",
        "runs": differences,
    }
