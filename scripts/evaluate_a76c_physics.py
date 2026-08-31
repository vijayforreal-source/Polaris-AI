import argparse
import json
from pathlib import Path

from backend.iceberg.physics.evaluation import (
    run_a76c_evaluation,
    run_timestep_sensitivity,
)
from backend.iceberg.physics.parameters import WDE17_DOI, paper_parameters
from backend.iceberg.physics.wde17 import gamma, harmonic_length


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate A76C physics-guided hindcasts")
    parser.add_argument("--timestep-hours", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_a76c_evaluation(args.timestep_hours)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("POLARIS-AI — A76C PHYSICS-GUIDED TRAJECTORY HINDCAST")
    print(f"Paper: Wagner, Dell & Eisenman (2017), DOI {WDE17_DOI}")
    dimensions = result["dimensions"]
    print(
        f"Iceberg: A76C, {dimensions['length_nm']:.0f} NM x "
        f"{dimensions['width_nm']:.0f} NM"
    )
    print(
        "Harmonic length: "
        f"{harmonic_length(dimensions['length_m'], dimensions['width_m']):.3f} m"
    )
    print(f"Published gamma: {gamma(paper_parameters()):.8f}")
    print(f"Integration timestep: {result['timestep_hours']:.1f} h")
    print("\nMODEL RESULTS")
    for model, metrics in result["models"].items():
        skill = result["skill_vs_persistence_mean_error"].get(model)
        skill_text = "n/a" if skill is None else f"{skill:.4f}"
        print(
            f"{model}: n={metrics['valid_intervals']}, "
            f"mean={metrics['mean_error_km']:.3f} km, "
            f"median={metrics['median_error_km']:.3f} km, skill={skill_text}"
        )
    print("\nWIND CONTRIBUTION / OCEAN SPEED")
    for name, value in result["wind_contribution_ratio"].items():
        print(f"{name}: {value:.6f}")
    print(f"\nBEST MODEL: {result['best_by_median_then_mean']}")
    print(f"FAILURES: {len(result['failures'])}")
    print("\nTIMESTEP SENSITIVITY")
    print(json.dumps(run_timestep_sensitivity(), indent=2))


if __name__ == "__main__":
    main()
