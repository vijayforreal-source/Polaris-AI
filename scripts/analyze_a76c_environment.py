from statistics import mean, median

import numpy as np

from backend.environment.copernicus_currents import DATASET_ID, DEPTHS_METRES, PRODUCT_ID
from backend.environment.era5_wind import DATASET_ID as ERA5_DATASET_ID
from backend.environment.era5_wind import validate_complete_coverage
from backend.environment.sampling import vector_magnitude
from backend.environment.track_forcing import (
    a76c_track,
    build_interval_summaries,
    build_point_samples,
    write_processed_dataset,
)


def diagnostics(intervals: list[dict[str, object]], source: str) -> dict[str, float | int]:
    vectors = []
    observed = []
    for interval in intervals:
        forcing = interval["wind"] if source == "wind" else interval["ocean_by_depth"][source]
        if forcing["mean_u"] is None:
            continue
        vectors.append([forcing["mean_u"], forcing["mean_v"]])
        observed.append(
            [interval["observed_east_velocity"], interval["observed_north_velocity"]]
        )
    forcing_array = np.asarray(vectors, dtype=float)
    observed_array = np.asarray(observed, dtype=float)
    alignments = []
    bearing_differences = []
    for forcing, motion in zip(forcing_array, observed_array, strict=True):
        denominator = np.linalg.norm(forcing) * np.linalg.norm(motion)
        if denominator == 0:
            continue
        alignments.append(float(np.dot(forcing, motion) / denominator))
        forcing_bearing = np.degrees(np.arctan2(forcing[0], forcing[1])) % 360
        motion_bearing = np.degrees(np.arctan2(motion[0], motion[1])) % 360
        difference = abs(forcing_bearing - motion_bearing)
        bearing_differences.append(float(min(difference, 360 - difference)))
    return {
        "east_correlation": float(np.corrcoef(forcing_array[:, 0], observed_array[:, 0])[0, 1]),
        "north_correlation": float(np.corrcoef(forcing_array[:, 1], observed_array[:, 1])[0, 1]),
        "mean_alignment": mean(alignments),
        "median_alignment": median(alignments),
        "mean_bearing_difference": mean(bearing_differences),
        "valid_intervals": len(alignments),
    }


def main() -> None:
    track = a76c_track()
    coverage = validate_complete_coverage()
    samples = build_point_samples()
    intervals = build_interval_summaries()
    output = write_processed_dataset(samples)
    ocean_valid = [sample for sample in samples if sample.ocean_u is not None]
    wind_valid = [sample for sample in samples if sample.wind_u10 is not None]
    ocean_speeds = [vector_magnitude(sample.ocean_u, sample.ocean_v) for sample in ocean_valid]
    wind_speeds = [vector_magnitude(sample.wind_u10, sample.wind_v10) for sample in wind_valid]

    print("POLARIS-AI — A76C ENVIRONMENTAL FORCING")
    print(f"TRACK: {track[0].observation_date} through {track[-1].observation_date}")
    print(f"Positions: {len(track)}; duration: 237 days")
    print(
        f"A76C DIMENSIONS: first={track[0].length_nm}x{track[0].width_nm} NM, "
        f"latest={track[-1].length_nm}x{track[-1].width_nm} NM, "
        f"area range={min(point.area_sq_nm for point in track):.2f}-"
        f"{max(point.area_sq_nm for point in track):.2f} sqNM"
    )
    print(f"OCEAN SOURCE: {PRODUCT_ID} / {DATASET_ID}")
    print(f"Depth levels: {', '.join(f'{depth:.6f} m' for depth in DEPTHS_METRES)}")
    print(f"ERA5 WIND SOURCE: {ERA5_DATASET_ID}; u10/v10; hourly; REANALYSIS")
    print(f"ERA5 COVERAGE: {coverage}")
    print(f"Ocean point samples: {len(ocean_valid)}/{len(samples)}")
    print(f"Wind point samples: {len(wind_valid)}/{len(samples)}")
    print(
        f"Ocean speed mean/min/max: {mean(ocean_speeds):.4f}/"
        f"{min(ocean_speeds):.4f}/{max(ocean_speeds):.4f} m s-1"
    )
    print(
        f"Wind speed mean/min/max: {mean(wind_speeds):.4f}/"
        f"{min(wind_speeds):.4f}/{max(wind_speeds):.4f} m s-1"
    )
    print(f"Track intervals: {len(intervals)}")
    wind_intervals = [interval["wind"] for interval in intervals]
    print(
        "INTERVAL WIND: "
        f"mean u/v={mean(item['mean_u'] for item in wind_intervals):.4f}/"
        f"{mean(item['mean_v'] for item in wind_intervals):.4f} m s-1; "
        f"mean std u/v={mean(item['std_u'] for item in wind_intervals):.4f}/"
        f"{mean(item['std_v'] for item in wind_intervals):.4f} m s-1; "
        f"speed min/max={min(item['minimum_speed'] for item in wind_intervals):.4f}/"
        f"{max(item['maximum_speed'] for item in wind_intervals):.4f} m s-1; "
        f"valid/expected={sum(item['valid_samples'] for item in wind_intervals)}/"
        f"{sum(item['expected_samples'] for item in wind_intervals)}"
    )
    print("FORCING COMPARISON")
    for depth in DEPTHS_METRES:
        print(f"Ocean {depth:.6f} m: {diagnostics(intervals, f'{depth:.6f}')}")
    print(f"ERA5 10 m wind: {diagnostics(intervals, 'wind')}")
    wind_coverages = [interval["wind"]["coverage_percentage"] for interval in intervals]
    print(
        f"Interval wind coverage mean/min: {mean(wind_coverages):.4f}/"
        f"{min(wind_coverages):.4f}%"
    )
    print("Wind direction is vector-to bearing clockwise from north, not meteorological wind-from.")
    print("Sea ice: existing regional Prydz Bay file does not cover the A76C track")
    print(f"Processed dataset: {output}")


if __name__ == "__main__":
    main()
