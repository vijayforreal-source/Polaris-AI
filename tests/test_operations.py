from datetime import UTC, datetime, timedelta

from backend.operations.models import EnvironmentSnapshot, Freshness
from backend.operations.service import classify_freshness, compare_environment_snapshots


def test_freshness_policy():
    assert classify_freshness(1, 24) == Freshness.FRESH
    assert classify_freshness(15, 24) == Freshness.AGING
    assert classify_freshness(30, 24) == Freshness.STALE
    assert classify_freshness(80, 24) == Freshness.EXPIRED
    assert classify_freshness(None, 24, available=False) == Freshness.UNAVAILABLE


def snapshot(version="one", freshness="FRESH"):
    return EnvironmentSnapshot(
        snapshot_id=version,
        created_at=datetime.now(UTC),
        sea_ice_observation_version=version,
        sea_ice_forecast_version="f",
        iceberg_registry_version="i",
        iceberg_forecast_version="if",
        historical_transit_version="h",
        risk_config_version="r",
        source_states={"SEA_ICE_OBSERVATION": "HEALTHY"},
        source_freshness={"SEA_ICE_OBSERVATION": freshness},
        geographic_domain="regional",
        forecast_initialization=None,
        valid_horizon_hours=72,
        fingerprint=version,
    )


def test_snapshot_changes_are_material():
    result = compare_environment_snapshots(snapshot("one"), snapshot("two"))
    assert result.material_change is True
    assert "SEA_ICE_UPDATED" in result.changes


def test_refresh_timestamp_only_is_not_material():
    old = snapshot("one")
    new = old.model_copy(update={"created_at": old.created_at + timedelta(seconds=2)})
    result = compare_environment_snapshots(old, new)
    assert result.material_change is False
