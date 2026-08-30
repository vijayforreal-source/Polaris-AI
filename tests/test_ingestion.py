from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.ingestion.config import BHARATI_PRYDZ_BAY, StudyRegion
from backend.ingestion.copernicus_sea_ice import (
    DATASET_ID,
    build_subset_arguments,
    raw_observation_directory,
    sha256_file,
)
from backend.ingestion.models import ScientificClassification, ScientificMetadata


def test_scientific_classification_and_metadata_contract() -> None:
    timestamp = datetime(2026, 8, 29, tzinfo=UTC)
    metadata = ScientificMetadata(
        classification=ScientificClassification.OBSERVATION,
        variable="generic_measurement",
        source="test fixture",
        product_id="product",
        dataset_id="dataset",
        observed_at=timestamp,
        valid_at=None,
        downloaded_at=timestamp,
        native_crs=None,
        canonical_crs=None,
        spatial_resolution=None,
        temporal_resolution=None,
        units=None,
        quality_flags=[],
        provenance={},
        local_file="generic.nc",
        sha256="0" * 64,
    )

    assert metadata.classification is ScientificClassification.OBSERVATION
    assert metadata.canonical_crs is None


def test_study_region_validation() -> None:
    assert BHARATI_PRYDZ_BAY.minimum_longitude == 70.0
    with pytest.raises(ValidationError):
        StudyRegion(
            minimum_longitude=84,
            maximum_longitude=70,
            minimum_latitude=-70.5,
            maximum_latitude=-66,
            bharati_latitude=-69.4068,
            bharati_longitude=76.1953,
        )


def test_sha256_file(tmp_path: Path) -> None:
    fixture = tmp_path / "generic.bin"
    fixture.write_bytes(b"POLARIS-AI")

    assert sha256_file(fixture) == (
        "5e57e949e4bd17e847e899c4a32a6452b399ee54f4289a86c720b52ee3157588"
    )


def test_raw_path_and_subset_are_single_observation() -> None:
    observed_at = datetime(2026, 8, 29, tzinfo=UTC)

    assert raw_observation_directory(Path("raw"), observed_at) == Path(
        "raw/osi_saf_sic_south/2026-08-29"
    )
    arguments = build_subset_arguments(BHARATI_PRYDZ_BAY, observed_at)
    assert arguments.count("2026-08-29T00:00:00Z") == 2
    assert DATASET_ID in arguments
    assert arguments[arguments.index("--variable") + 1] == "ice_conc"
