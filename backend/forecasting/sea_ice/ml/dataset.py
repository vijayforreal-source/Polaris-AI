from datetime import date

import numpy as np
import torch
import xarray as xr
from torch.utils.data import Dataset

from backend.forecasting.sea_ice.models import SeaIceSplit


def temporal_window_indices(
    times: np.ndarray,
    split: SeaIceSplit,
    context_days: int,
    maximum_horizon_days: int = 3,
) -> list[int]:
    days = times.astype("datetime64[D]")
    available = {day for day in days}
    indices: list[int] = []
    for index, initialization in enumerate(days):
        initialization_date = date.fromisoformat(str(initialization))
        if not split.start <= initialization_date <= split.end:
            continue
        required = [
            initialization + np.timedelta64(offset, "D")
            for offset in range(-(context_days - 1), maximum_horizon_days + 1)
        ]
        if not all(value in available for value in required):
            continue
        if not all(
            split.start <= date.fromisoformat(str(value)) <= split.end
            for value in required
        ):
            continue
        indices.append(index)
    return indices


def seasonal_channels(initialization_time: np.datetime64, shape: tuple[int, int]) -> np.ndarray:
    day = initialization_time.astype("datetime64[D]")
    year_start = day.astype("datetime64[Y]").astype("datetime64[D]")
    day_of_year = int((day - year_start).astype(int)) + 1
    angle = 2.0 * np.pi * day_of_year / 365.2425
    return np.stack(
        [
            np.full(shape, np.sin(angle), dtype="float32"),
            np.full(shape, np.cos(angle), dtype="float32"),
        ]
    )


class SeaIceWindowDataset(Dataset):
    """In-memory views over the immutable processed observation cube."""

    def __init__(
        self,
        concentration_percent: np.ndarray,
        times: np.ndarray,
        ocean_mask: np.ndarray,
        split: SeaIceSplit,
        context_days: int = 7,
    ) -> None:
        self.concentration = np.asarray(concentration_percent, dtype="float32")
        self.times = times.astype("datetime64[D]")
        self.ocean_mask = np.asarray(ocean_mask, dtype=bool)
        self.context_days = context_days
        self.initialization_indices = temporal_window_indices(
            self.times, split, context_days
        )

    @classmethod
    def from_xarray(
        cls, cube: xr.Dataset, split: SeaIceSplit, context_days: int = 7
    ) -> "SeaIceWindowDataset":
        return cls(
            cube.ice_conc.values,
            cube.time.values,
            cube.valid_ocean_mask.values,
            split,
            context_days,
        )

    def __len__(self) -> int:
        return len(self.initialization_indices)

    def __getitem__(self, sample_index: int) -> dict[str, torch.Tensor]:
        initialization_index = self.initialization_indices[sample_index]
        context = self.concentration[
            initialization_index - self.context_days + 1 : initialization_index + 1
        ]
        targets = self.concentration[
            initialization_index + 1 : initialization_index + 4
        ]
        context_valid = np.isfinite(context) & self.ocean_mask[None, :, :]
        target_valid = np.isfinite(targets) & self.ocean_mask[None, :, :]
        normalized_context = np.where(context_valid, context / 100.0, 0.0)
        normalized_targets = np.where(target_valid, targets / 100.0, 0.0)
        season = seasonal_channels(
            self.times[initialization_index], self.ocean_mask.shape
        )
        features = np.concatenate(
            [
                normalized_context,
                context_valid.astype("float32"),
                self.ocean_mask[None, :, :].astype("float32"),
                season,
            ]
        ).astype("float32")
        return {
            "features": torch.from_numpy(features),
            "targets": torch.from_numpy(normalized_targets.astype("float32")),
            "target_mask": torch.from_numpy(target_valid),
            "current_valid": torch.from_numpy(context_valid[-1]),
            "initialization_index": torch.tensor(initialization_index, dtype=torch.int64),
        }
