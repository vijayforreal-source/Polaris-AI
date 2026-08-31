import json
from pathlib import Path

from backend.iceberg.hybrid.evaluation import run_a76c_hybrid_evaluation

OUTPUT = Path("backend/iceberg/hybrid/a76c_results.json")


def main() -> None:
    result = run_a76c_hybrid_evaluation()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("POLARIS-AI — A76C CALIBRATED HYBRID HINDCAST")
    print("\nCHRONOLOGICAL SPLIT")
    print(json.dumps(result["split"], indent=2))
    print("\nLAMBDA SEARCH")
    for row in result["lambda_search"]:
        print(
            f"lambda={row['lambda']:.2f} mean={row['mean_error_km']:.3f} km "
            f"median={row['median_error_km']:.3f} km"
        )
    print(f"\nSELECTED LAMBDA: {result['selected_lambda']:.2f}")
    for partition, metrics in result["metrics"].items():
        print(f"\n{partition.upper()} RESULTS")
        for model, values in metrics.items():
            print(
                f"{model}: n={values['valid_intervals']} "
                f"mean={values['mean_error_km']:.3f} km "
                f"median={values['median_error_km']:.3f} km"
            )
    print("\nPAIRED BOOTSTRAP")
    print(json.dumps(result["paired_bootstrap"], indent=2))
    print("\nEMPIRICAL HINDCAST ERROR ENVELOPE")
    print(json.dumps(result["uncertainty"], indent=2))
    print(f"\nBEST MODEL: {result['selected_production_candidate']}")
    print("\nLIMITATIONS")
    print(result["scientific_interpretation"])


if __name__ == "__main__":
    main()
