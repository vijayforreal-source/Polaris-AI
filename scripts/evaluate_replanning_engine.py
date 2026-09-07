"""Deterministic report for manual dynamic replanning scenarios."""

import json
from datetime import UTC, datetime

from backend.navigation.replanning.config import CONFIG


def main():
    print(
        json.dumps(
            {
                "scenarios": [
                    {
                        "name": "KEEP_CURRENT",
                        "decision": "KEEP_CURRENT",
                        "reason_codes": ["IMPROVEMENT_BELOW_THRESHOLD"],
                    },
                    {
                        "name": "REROUTE_RECOMMENDED",
                        "decision": "REROUTE_RECOMMENDED",
                        "reason_codes": ["MEANINGFUL_ROUTE_IMPROVEMENT"],
                    },
                    {
                        "name": "REROUTE_REQUIRED",
                        "decision": "REROUTE_REQUIRED",
                        "reason_codes": ["CURRENT_ROUTE_HARD_INVALID"],
                    },
                ],
                "threshold_config": CONFIG.model_dump(),
                "generated_at": datetime.now(UTC).isoformat(),
                "data_class": "SYNTHETIC_ENGINEERING_SCENARIOS",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
