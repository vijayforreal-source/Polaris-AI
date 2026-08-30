import json

from backend.iceberg.usnic_registry import (
    PROVIDER,
    filter_study_region,
    latest_registry_file,
    parse_registry,
    sha256_file,
)
from backend.ingestion.config import BHARATI_PRYDZ_BAY


def main() -> None:
    path = latest_registry_file()
    sidecar = json.loads(path.with_suffix(path.suffix + ".metadata.json").read_text())
    result = parse_registry(path)
    regional = filter_study_region(result.observations, BHARATI_PRYDZ_BAY)

    print("POLARIS-AI — USNIC ANTARCTIC ICEBERG REGISTRY")
    print(f"Provider: {PROVIDER}")
    print(f"Retrieved: {sidecar['retrieved_at']}")
    print(f"Provider report date: {sidecar['provider_report_date']}")
    print(f"Raw filename: {path.name}")
    print(f"SHA-256: {sha256_file(path)}")
    print(f"Total rows: {result.total_rows}")
    print(f"Valid observations: {len(result.observations)}")
    print(f"Rejected rows: {len(result.rejected_rows)}")
    print(f"Bharati-region observations: {len(regional)}")
    for observation in regional:
        print(
            f"{observation.iceberg_id}: lat={observation.latitude}, "
            f"lon={observation.longitude}, length={observation.length_nm} NM, "
            f"width={observation.width_nm} NM, area={observation.area_sq_nm} sqNM, "
            f"last_update={observation.provider_last_update}"
        )


if __name__ == "__main__":
    main()

