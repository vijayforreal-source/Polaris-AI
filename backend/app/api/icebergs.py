import json
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from backend.iceberg.usnic_registry import (
    PROVIDER,
    SOURCE_PAGE,
    TRACKING_CRITERIA,
    filter_study_region,
    latest_registry_file,
    parse_registry,
)
from backend.ingestion.config import BHARATI_PRYDZ_BAY

router = APIRouter(prefix="/api/icebergs", tags=["icebergs"])


@lru_cache(maxsize=1)
def load_latest_registry() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    path = latest_registry_file()
    sidecar_path = path.with_suffix(path.suffix + ".metadata.json")
    if not sidecar_path.exists():
        raise FileNotFoundError(f"USNIC provenance sidecar is missing: {sidecar_path}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    result = parse_registry(path)
    regional = filter_study_region(result.observations, BHARATI_PRYDZ_BAY)
    all_records = [record.model_dump(mode="json") for record in result.observations]
    regional_records = [record.model_dump(mode="json") for record in regional]
    metadata = {
        "provider": PROVIDER,
        "source": SOURCE_PAGE,
        "classification": "OBSERVATION",
        "retrieved_at": sidecar["retrieved_at"],
        "provider_report_date": sidecar["provider_report_date"],
        "total_registry_count": result.total_rows,
        "valid_coordinate_count": len(result.observations),
        "rejected_record_count": len(result.rejected_rows),
        "study_region_count": len(regional),
        "outside_study_region_count": len(result.observations) - len(regional),
        "tracking_criteria": TRACKING_CRITERIA,
        "limitation": (
            "The USNIC named iceberg registry covers qualifying tracked icebergs and is not "
            "a complete catalogue of all smaller iceberg hazards."
        ),
    }
    return metadata, regional_records, all_records


def _registry_or_503(index: int) -> Any:
    try:
        return load_latest_registry()[index]
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/latest/metadata")
async def latest_iceberg_metadata() -> dict[str, Any]:
    return _registry_or_503(0)


@router.get("/latest")
async def latest_icebergs(
    scope: Literal["study_region", "all"] = Query(default="study_region")
) -> dict[str, Any]:
    records = _registry_or_503(1 if scope == "study_region" else 2)
    return {"scope": scope, "classification": "OBSERVATION", "icebergs": records}

