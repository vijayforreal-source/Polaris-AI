import json
from functools import lru_cache
from pathlib import Path

from .models import Voyage

STORE = Path(__file__).resolve().parents[2] / "data/processed/historical_transit"
MAX_FILE_BYTES = 5_000_000


@lru_cache(maxsize=128)
def _read(path: Path, modified: int, size: int) -> Voyage:
    if size > MAX_FILE_BYTES:
        raise ValueError("Track JSON exceeds the 5 MB processed-file limit")
    return Voyage.model_validate_json(path.read_text(encoding="utf-8"))


def load_voyages(root: Path | None = None) -> tuple[list[Voyage], list[dict]]:
    voyages, errors = [], []
    for path in sorted((root or STORE).glob("*.json")):
        try:
            stat = path.stat()
            voyage = _read(path, stat.st_mtime_ns, stat.st_size)
            if path.stem != voyage.voyage_id:
                raise ValueError("Stored filename and voyage_id must match")
            voyages.append(voyage)
        except (OSError, ValueError) as error:
            errors.append(
                {
                    "file": path.name,
                    "reason": type(error).__name__,
                    "note": "Unreadable or invalid track retained on disk; not displayed.",
                }
            )
    rejected = (root or STORE) / "rejected"
    for path in sorted(rejected.glob("*.json")):
        errors.append(
            {
                "file": path.name,
                "reason": "IMPORT_REJECTED",
                "note": "Malformed input quarantined by importer; not displayed.",
            }
        )
    return voyages, errors


def save_voyage(voyage: Voyage, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{voyage.voyage_id}.json"
    # Exclusive creation preserves existing provenance and imported tracks.
    with target.open("x", encoding="utf-8") as handle:
        json.dump(voyage.model_dump(mode="json"), handle, indent=2, allow_nan=False)
        handle.write("\n")
    return target
