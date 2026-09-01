from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.iceberg.engine.models import (
    AvailabilityStatus,
    TrajectoryModel,
    TrajectoryRequest,
)
from backend.iceberg.engine.service import run_historical_hindcast

client = TestClient(app)


class GenericForcing:
    def __init__(self, cutoff: datetime | None = None) -> None:
        self.cutoff = cutoff
        self.sampled_positions: list[tuple[float, float]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def ocean_sampler(self, depth_index: int):
        def sample(latitude: float, longitude: float, valid_at: datetime):
            self.sampled_positions.append((latitude, longitude))
            if self.cutoff is not None and valid_at >= self.cutoff:
                return None, None
            return 0.1 + depth_index * 0.02, 0.04

        return sample

    def wind_sampler(self, latitude: float, longitude: float, valid_at: datetime):
        if self.cutoff is not None and valid_at >= self.cutoff:
            return None, None
        return 3.0, -1.0


def request(horizon: int, model: TrajectoryModel | None = None) -> TrajectoryRequest:
    values = {
        "iceberg_id": "GENERIC_TEST_FIXTURE",
        "initial_latitude": -55.0,
        "initial_longitude": -35.0,
        "initial_time": datetime(2026, 4, 1, tzinfo=UTC),
        "prediction_horizon_hours": horizon,
    }
    if model is not None:
        values["model"] = model
    return TrajectoryRequest(**values)


@pytest.mark.parametrize("horizon", [6, 12, 24, 48, 72])
def test_supported_horizons_return_exact_actual_horizon(horizon: int) -> None:
    result = run_historical_hindcast(request(horizon), GenericForcing)
    assert result.availability_status == AvailabilityStatus.AVAILABLE
    assert result.actual_horizon_hours == horizon
    assert result.trajectory_points[-1].time == result.start_time + timedelta(hours=horizon)


def test_default_model_and_hindcast_classification() -> None:
    result = run_historical_hindcast(request(6), GenericForcing)
    assert result.model == TrajectoryModel.P2_SURFACE_CURRENT
    assert result.model_status == "PRODUCTION_CANDIDATE"
    assert result.mode == "HISTORICAL HINDCAST"
    assert result.classification == "MODEL_PREDICTION"


def test_sampling_follows_predicted_position_not_future_observation() -> None:
    forcing = GenericForcing()
    result = run_historical_hindcast(request(6), lambda: forcing)
    assert result.actual_historical_observation is None
    assert len(forcing.sampled_positions) == 6
    assert forcing.sampled_positions[1] != forcing.sampled_positions[0]
    assert forcing.sampled_positions[1] == pytest.approx(
        (
            result.trajectory_points[1].latitude,
            result.trajectory_points[1].longitude,
        )
    )


def test_insufficient_forcing_is_explicit_and_not_completed() -> None:
    cutoff = datetime(2026, 4, 1, 3, tzinfo=UTC)
    result = run_historical_hindcast(request(12), lambda: GenericForcing(cutoff))
    assert result.availability_status == AvailabilityStatus.FORCING_UNAVAILABLE
    assert result.actual_horizon_hours == 3
    assert result.endpoint is None
    assert any("not extrapolated" in warning for warning in result.scientific_warnings)


def test_uncertainty_applies_only_to_calibrated_h0() -> None:
    h0 = run_historical_hindcast(
        request(6, TrajectoryModel.H0_EFFECTIVE_CURRENT_HYBRID), GenericForcing
    )
    p2 = run_historical_hindcast(request(6), GenericForcing)
    assert h0.uncertainty.applicable is True
    assert h0.uncertainty.radius_50_km == pytest.approx(58.0809823812134)
    assert p2.uncertainty.applicable is False
    assert p2.uncertainty.radius_95_km is None


def test_request_rejects_unsupported_horizon_and_naive_time() -> None:
    with pytest.raises(ValueError):
        request(18)
    with pytest.raises(ValueError):
        TrajectoryRequest(
            iceberg_id="GENERIC_TEST_FIXTURE",
            initial_latitude=0,
            initial_longitude=0,
            initial_time=datetime(2026, 1, 1),
            prediction_horizon_hours=6,
        )


def test_hindcast_api_schema_and_default_model() -> None:
    response = client.post(
        "/api/trajectory/hindcast",
        json={
            "iceberg_id": "A76C",
            "initial_latitude": -58.35,
            "initial_longitude": -36.47,
            "initial_time": "2026-04-24T00:00:00Z",
            "prediction_horizon_hours": 6,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "P2_SURFACE_CURRENT"
    assert payload["mode"] == "HISTORICAL HINDCAST"
    assert payload["classification"] == "MODEL_PREDICTION"
    assert payload["requested_horizon_hours"] == 6
    assert payload["availability_status"] == "AVAILABLE"
    assert len(payload["trajectory_points"]) == 7


def test_hindcast_api_allows_frontend_post_preflight() -> None:
    response = client.options(
        "/api/trajectory/hindcast",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
