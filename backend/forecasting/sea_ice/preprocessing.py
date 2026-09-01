from datetime import date

import numpy as np

from .models import SeaIceSplit


def chronological_indices(times: np.ndarray, split: SeaIceSplit) -> np.ndarray:
    days = times.astype("datetime64[D]")
    return np.flatnonzero(
        (days >= np.datetime64(split.start)) & (days <= np.datetime64(split.end))
    )


def forecast_pairs(
    times: np.ndarray,
    split: SeaIceSplit,
    horizon_days: int,
    *,
    require_previous: bool = True,
) -> list[tuple[int, int]]:
    if horizon_days not in {1, 2, 3}:
        raise ValueError("daily forecast horizon must be 1, 2, or 3 days")
    days = times.astype("datetime64[D]")
    index_by_day = {day: index for index, day in enumerate(days)}
    split_indices = chronological_indices(days, split)
    pairs: list[tuple[int, int]] = []
    for index in split_indices:
        initialization = days[index]
        target = initialization + np.timedelta64(horizon_days, "D")
        previous = initialization - np.timedelta64(1, "D")
        target_index = index_by_day.get(target)
        if target_index is None:
            continue
        target_date = date.fromisoformat(str(target))
        if not split.start <= target_date <= split.end:
            continue
        if require_previous and previous not in index_by_day:
            continue
        pairs.append((index, target_index))
    return pairs
