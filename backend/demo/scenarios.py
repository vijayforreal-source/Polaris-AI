from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    name: str
    classification: str
    expected: str
    steps: tuple[str, ...]


SCENARIOS = (
    DemoScenario(
        "A",
        "NORMAL_REGIONAL_PLANNING",
        "DEMO / SIMULATED",
        "AVAILABLE",
        ("create mission", "generate SAFE/FAST/ECO/BALANCED routes", "activate one route"),
    ),
    DemoScenario(
        "B",
        "HAZARD_DRIVEN_REROUTE",
        "DEMO / SIMULATED",
        "REROUTE_RECOMMENDED or REROUTE_REQUIRED",
        (
            "active route",
            "future hazard changes",
            "candidate generated",
            "captain accepts manually",
        ),
    ),
    DemoScenario(
        "C",
        "OFFLINE_VOYAGE_OPERATION",
        "DEMO / SIMULATED",
        "local capabilities remain available",
        ("ONLINE", "cache data", "OFFLINE", "defer sync"),
    ),
    DemoScenario(
        "D",
        "RECONNECT_RESYNC",
        "DEMO / SIMULATED",
        "material environment change detected",
        ("OFFLINE", "ONLINE", "critical sync resumes", "re-evaluate route"),
    ),
    DemoScenario(
        "E",
        "DEGRADED_STALE_DATA",
        "DEMO / SIMULATED",
        "DEGRADED or BLOCKED; no fabricated route",
        ("stale critical source", "surface warning", "retain safe failure"),
    ),
)


def scenario_report():
    return [
        {
            "scenario_id": item.scenario_id,
            "name": item.name,
            "classification": item.classification,
            "expected": item.expected,
            "steps": list(item.steps),
        }
        for item in SCENARIOS
    ]
