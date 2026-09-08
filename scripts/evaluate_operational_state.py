"""Print the current operational health, freshness, capabilities, and snapshot."""

import json

from backend.operations.service import health

if __name__ == "__main__":
    report = health()
    print(
        json.dumps(
            {
                "overall_health": report["overall_status"],
                "sources": report["data_source_statuses"],
                "capabilities": report["capabilities"],
                "environment_snapshot": report["latest_environment_version"],
                "mission": report["active_mission_status"],
                "critical_blockers": report["critical_blockers"],
                "warnings": report["warnings"],
            },
            indent=2,
        )
    )
