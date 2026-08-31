from statistics import mean

import numpy as np

from backend.environment.copernicus_currents import DATASET_ID, DEPTHS_METRES, PRODUCT_ID
from backend.environment.sampling import vector_magnitude
from backend.environment.track_forcing import (
    a76c_track,
    build_interval_summaries,
    build_point_samples,
    write_processed_dataset,
)


def main() -> None:
    track = a76c_track()
    samples = build_point_samples()
    intervals = build_interval_summaries()
    output = write_processed_dataset(samples)
    valid = [sample for sample in samples if sample.ocean_u is not None]
    speeds = [vector_magnitude(sample.ocean_u, sample.ocean_v) for sample in valid]
    ocean_u = np.array([item["mean_ocean_u"] for item in intervals], dtype=float)
    ocean_v = np.array([item["mean_ocean_v"] for item in intervals], dtype=float)
    observed_u = np.array([item["observed_east_velocity"] for item in intervals])
    observed_v = np.array([item["observed_north_velocity"] for item in intervals])

    print("POLARIS-AI — A76C ENVIRONMENTAL FORCING")
    print(f"TRACK: {track[0].observation_date} through {track[-1].observation_date}")
    print(f"Positions: {len(track)}; duration: 237 days")
    print(f"OCEAN SOURCE: {PRODUCT_ID} / {DATASET_ID}")
    print("Variables: uo, vo; 6-hourly instantaneous; units: m s-1")
    print(f"Depth levels: {', '.join(f'{depth:.6f} m' for depth in DEPTHS_METRES)}")
    print("WIND SOURCE: ERA5 hourly single levels; AUTHENTICATION REQUIRED")
    print(f"Ocean samples: {len(valid)}/{len(samples)}")
    print(f"Ocean speed mean/min/max: {mean(speeds):.4f}/{min(speeds):.4f}/{max(speeds):.4f} m s-1")
    print(f"Track intervals: {len(intervals)}")
    print(
        "Interval ocean coverage mean/min: "
        f"{mean(item['coverage_percentage'] for item in intervals):.2f}/"
        f"{min(item['coverage_percentage'] for item in intervals):.2f}%"
    )
    print(f"East-component correlation: {np.corrcoef(ocean_u, observed_u)[0, 1]:.4f}")
    print(f"North-component correlation: {np.corrcoef(ocean_v, observed_v)[0, 1]:.4f}")
    print("Wind correlation: unavailable — ERA5 authentication required")
    print("Sea ice: existing regional Prydz Bay file does not cover the A76C track")
    print(f"Processed dataset: {output}")


if __name__ == "__main__":
    main()
