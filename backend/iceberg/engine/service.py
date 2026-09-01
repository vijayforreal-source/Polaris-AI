from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from backend.iceberg.history import load_history, tracks_by_iceberg
from backend.iceberg.hybrid.model import effective_current_sampler
from backend.iceberg.hybrid.results import load_hybrid_results
from backend.iceberg.motion import geodesic_inverse
from backend.iceberg.physics.evaluation import A76CForcing
from backend.iceberg.physics.integrator import integrate_trajectory
from backend.iceberg.physics.parameters import NM_TO_METRES, paper_parameters

from .models import (
    ActualObservation,
    AvailabilityStatus,
    Position,
    PublicTrajectoryPoint,
    TrajectoryModel,
    TrajectoryRequest,
    TrajectoryResponse,
    UncertaintyEnvelope,
)

ForcingFactory = Callable[[], A76CForcing]

MODEL_STATUS = {
    TrajectoryModel.P2_SURFACE_CURRENT: "PRODUCTION_CANDIDATE",
    TrajectoryModel.WDE17_SURFACE: "REFERENCE",
    TrajectoryModel.H0_EFFECTIVE_CURRENT_HYBRID: "EXPERIMENTAL",
    TrajectoryModel.H1_HYBRID_WDE17_STYLE: "EXPERIMENTAL",
}


def _uncertainty(model: TrajectoryModel) -> UncertaintyEnvelope:
    results = load_hybrid_results()
    radii = results["uncertainty"]["radii_km"]
    if model == TrajectoryModel.H0_EFFECTIVE_CURRENT_HYBRID:
        return UncertaintyEnvelope(
            label="EMPIRICAL HINDCAST ERROR ENVELOPE",
            applicable=True,
            radius_50_km=radii["50"],
            radius_80_km=radii["80"],
            radius_95_km=radii["95"],
            note=(
                "Sparse historical endpoint-error radii; these are not guaranteed "
                "forecast probabilities."
            ),
        )
    return UncertaintyEnvelope(
        label="EMPIRICAL HINDCAST ERROR ENVELOPE",
        applicable=False,
        note="The existing empirical envelope was calibrated only for H0 effective current.",
    )


def _actual_observation(
    request: TrajectoryRequest, endpoint: Position | None
) -> ActualObservation | None:
    if endpoint is None or request.iceberg_id.upper() != "A76C":
        return None
    target_time = request.initial_time.astimezone(UTC) + timedelta(
        hours=request.prediction_horizon_hours
    )
    if target_time.time() != datetime.min.time():
        return None
    points = tracks_by_iceberg(load_history().points).get("A76C", [])
    match = next(
        (point for point in points if point.observation_date == target_time.date()), None
    )
    if match is None:
        return None
    error_km, _ = geodesic_inverse(
        endpoint.latitude, endpoint.longitude, match.latitude, match.longitude
    )
    return ActualObservation(
        observed_on=match.observation_date.isoformat(),
        latitude=match.latitude,
        longitude=match.longitude,
        endpoint_error_km=error_km,
    )


def run_historical_hindcast(
    request: TrajectoryRequest,
    forcing_factory: ForcingFactory = A76CForcing,
) -> TrajectoryResponse:
    start_time = request.initial_time.astimezone(UTC)
    end_time = start_time + timedelta(hours=request.prediction_horizon_hours)
    hybrid_results = load_hybrid_results()
    blend_lambda = float(hybrid_results["selected_lambda"])
    warnings = [
        "Historical forcing is used; this is not an operational future forecast.",
        "Future observed USNIC positions are not used during trajectory integration.",
    ]

    with forcing_factory() as forcing:
        surface = forcing.ocean_sampler(0)
        ocean_sampler = surface
        integrator_model = "P2_SURFACE_CURRENT"
        wind_sampler = None
        if request.model in {
            TrajectoryModel.H0_EFFECTIVE_CURRENT_HYBRID,
            TrajectoryModel.H1_HYBRID_WDE17_STYLE,
        }:
            ocean_sampler = effective_current_sampler(
                surface, forcing.ocean_sampler(1), blend_lambda
            )
            warnings.append(
                "The 29.445 m blend is empirical and must not be interpreted as iceberg draft."
            )
        if request.model in {
            TrajectoryModel.WDE17_SURFACE,
            TrajectoryModel.H1_HYBRID_WDE17_STYLE,
        }:
            integrator_model = "P3_WDE17"
            wind_sampler = forcing.wind_sampler

        trajectory = integrate_trajectory(
            integrator_model,
            start_time,
            end_time,
            request.initial_latitude,
            request.initial_longitude,
            ocean_sampler,
            wind_sampler,
            16.0 * NM_TO_METRES,
            7.0 * NM_TO_METRES,
            1.0,
            None,
            paper_parameters(),
        )

    points = [
        PublicTrajectoryPoint(
            time=point.valid_at,
            latitude=point.latitude,
            longitude=point.longitude,
        )
        for point in trajectory.points
    ]
    endpoint = (
        Position(latitude=points[-1].latitude, longitude=points[-1].longitude)
        if trajectory.status == "COMPLETE"
        else None
    )
    actual_hours = (
        (points[-1].time - start_time).total_seconds() / 3600 if points else 0.0
    )
    status = (
        AvailabilityStatus.AVAILABLE
        if trajectory.status == "COMPLETE"
        else AvailabilityStatus.FORCING_UNAVAILABLE
    )
    if status == AvailabilityStatus.FORCING_UNAVAILABLE:
        warnings.append(
            "FORCING DATA UNAVAILABLE FOR REQUESTED HORIZON; trajectory was not "
            "extrapolated or silently completed."
        )
    return TrajectoryResponse(
        model=request.model,
        model_status=MODEL_STATUS[request.model],
        iceberg_id=request.iceberg_id.upper(),
        start_time=start_time,
        requested_horizon_hours=request.prediction_horizon_hours,
        actual_horizon_hours=actual_hours,
        start_position=Position(
            latitude=request.initial_latitude, longitude=request.initial_longitude
        ),
        trajectory_points=points,
        endpoint=endpoint,
        actual_historical_observation=(
            _actual_observation(request, endpoint)
            if status == AvailabilityStatus.AVAILABLE
            else None
        ),
        environment_sources={
            "ocean": "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i / ANALYSIS",
            "wind": (
                "reanalysis-era5-single-levels / REANALYSIS"
                if wind_sampler is not None
                else "not required by selected model"
            ),
        },
        uncertainty=_uncertainty(request.model),
        availability_status=status,
        scientific_warnings=warnings,
    )
