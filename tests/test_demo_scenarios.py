from backend.demo.scenarios import SCENARIOS, scenario_report


def test_demo_scenarios_are_isolated_and_labeled():
    assert {item.scenario_id for item in SCENARIOS} == {"A", "B", "C", "D", "E"}
    assert all(item.classification == "DEMO / SIMULATED" for item in SCENARIOS)
    assert len(scenario_report()) == 5
