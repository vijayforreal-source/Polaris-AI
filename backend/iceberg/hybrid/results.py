import json
from functools import lru_cache
from pathlib import Path

RESULT_PATH = Path(__file__).with_name("a76c_results.json")


@lru_cache(maxsize=1)
def load_hybrid_results() -> dict[str, object]:
    if not RESULT_PATH.is_file():
        raise FileNotFoundError("Verified A76C hybrid evaluation result is unavailable")
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))
