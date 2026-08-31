from statistics import mean, median

from backend.iceberg.baseline import rolling_origin_validation
from backend.iceberg.history import load_history, tracks_by_iceberg
from backend.iceberg.motion import analyze_track, select_baseline_candidate

REGIONAL_IDS = ("D15A", "D15B", "D15C", "D15D", "D23", "D34")


def main() -> None:
    history = load_history()
    tracks = tracks_by_iceberg(history.points)
    metrics = [
        analyze_track(track, sum(len(point.source_files) for point in track))
        for track in tracks.values()
    ]
    ranked = sorted(metrics, key=lambda item: item.cumulative_displacement_km, reverse=True)
    selected = select_baseline_candidate(metrics)
    validation = rolling_origin_validation(tracks[selected.iceberg_id])
    persistence_errors = [result[0].error_km for result in validation]
    velocity_errors = [result[1].error_km for result in validation]
    latest_persistence, latest_velocity = validation[-1]

    print("POLARIS-AI — Historical USNIC Iceberg Analysis")
    print("Archive window: 2026-01-01 through 2026-08-27")
    print(f"Archive files: {len(history.archive_files)}")
    print(f"Iceberg IDs: {len(tracks)}")
    print(f"Raw registry rows: {history.raw_record_count}")
    print(f"Provider-dated track points: {len(history.points)}")
    print("\nBHARATI REGION")
    for iceberg_id in REGIONAL_IDS:
        item = next(metric for metric in metrics if metric.iceberg_id == iceberg_id)
        print(
            f"{item.iceberg_id}: records={item.record_count}, "
            f"unique_positions={item.unique_position_count}, duration={item.duration_days} days, "
            f"displacement={item.cumulative_displacement_km:.3f} km, "
            f"classification={item.classification}"
        )
    print("\nTOP MOVING ICEBERGS")
    for rank, item in enumerate(ranked[:10], start=1):
        print(
            f"{rank}. {item.iceberg_id}: positions={item.unique_position_count}, "
            f"duration={item.duration_days} days, "
            f"displacement={item.cumulative_displacement_km:.3f} km"
        )
    print("\nSELECTED BASELINE CANDIDATE")
    print(
        f"{selected.iceberg_id}: greatest cumulative observed displacement among tracks "
        "meeting continuity, point-count, displacement, and jump-QC criteria"
    )
    print("\nBASELINE RESULTS")
    print(f"Rolling held-out evaluations: {len(validation)}")
    print(
        f"Persistence mean/median error: {mean(persistence_errors):.3f}/"
        f"{median(persistence_errors):.3f} km"
    )
    print(
        f"Constant-velocity mean/median error: {mean(velocity_errors):.3f}/"
        f"{median(velocity_errors):.3f} km"
    )
    print(
        f"Latest horizon: {latest_persistence.forecast_horizon_hours:.0f} h; "
        f"persistence={latest_persistence.error_km:.3f} km "
        f"({latest_persistence.error_nm:.3f} NM); "
        f"constant_velocity={latest_velocity.error_km:.3f} km "
        f"({latest_velocity.error_nm:.3f} NM)"
    )


if __name__ == "__main__":
    main()
