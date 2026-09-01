import json

from backend.forecasting.sea_ice.dataset import (
    discover_raw_files,
    inspect_source_consistency,
    load_daily_cube,
    quality_control,
    write_processed_cube,
)
from backend.forecasting.sea_ice.evaluation import evaluate_baselines, write_results
from backend.ingestion.historical_sea_ice import write_raw_sidecar


def main() -> None:
    paths = discover_raw_files()
    for path in paths:
        write_raw_sidecar(path)
    consistency = inspect_source_consistency(paths)
    cube = load_daily_cube(paths)
    processed = write_processed_cube(cube)
    results = evaluate_baselines(cube)
    write_results(results)
    qc = quality_control(cube)

    print("POLARIS-AI")
    print("ANTARCTIC SEA-ICE FORECAST BASELINES")
    print("\nSOURCE DATA")
    print(f"Product: {cube.attrs['product_id']}")
    print(f"CDR: {cube.attrs['cdr_dataset_id']}")
    print(f"ICDR: {cube.attrs['icdr_dataset_id']}")
    print(f"Files: {consistency['file_count']}")
    print("\nREGION")
    print("67.2E to 87.0E; 73.4S to 63.2S (3 degree context buffer requested)")
    print("\nDATA COVERAGE / GRID / QUALITY CONTROL")
    print(json.dumps(qc, indent=2))
    print("\nTRAIN / VALIDATION / TEST")
    print(json.dumps(results["splits"], indent=2))
    for horizon in ("24H", "48H", "72H"):
        print(f"\n+{horizon} RESULTS")
        for baseline, payload in results["horizons"][horizon].items():
            if baseline != "best_baseline":
                metrics = payload["regional"]
                print(
                    f"{baseline}: MAE={metrics['mae_percentage_points']:.3f} pp "
                    f"RMSE={metrics['rmse_percentage_points']:.3f} pp "
                    f"bias={metrics['mean_bias_percentage_points']:.3f} pp"
                )
        print(f"BEST: {results['horizons'][horizon]['best_baseline']}")
    print("\nSEASONAL RESULTS / BHARATI-REGION RESULTS")
    print("Recorded per horizon and baseline in baseline_results.json")
    print("\nBEST BASELINE")
    print(results["best_overall_baseline"])
    print("\nPROCESSED DATA")
    print(processed["local_file"], processed["sha256"])
    print("\nLIMITATIONS")
    print("Daily satellite observation targets; deterministic baselines only; no AI model.")


if __name__ == "__main__":
    main()
