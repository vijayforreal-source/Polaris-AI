from datetime import date

import numpy as np
import torch
import xarray as xr
from torch.utils.data import Dataset

from backend.forecasting.sea_ice.models import SeaIceSplit

FORCING_VARIABLES = ("u10", "v10", "t2m")


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
        forcing: np.ndarray | None = None,
        forcing_mean: np.ndarray | None = None,
        forcing_std: np.ndarray | None = None,
    ) -> None:
        self.concentration = np.asarray(concentration_percent, dtype="float32")
        self.times = times.astype("datetime64[D]")
        self.ocean_mask = np.asarray(ocean_mask, dtype=bool)
        self.context_days = context_days
        self.forcing = None if forcing is None else np.asarray(forcing, dtype="float32")
        self.forcing_mean = forcing_mean
        self.forcing_std = forcing_std
        if self.forcing is not None:
            if self.forcing.shape != (len(times), len(FORCING_VARIABLES), *ocean_mask.shape):
                raise ValueError("Atmospheric forcing shape does not match sea-ice grid/time")
            if forcing_mean is None or forcing_std is None:
                raise ValueError("Training-derived forcing normalization is required")
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
        normalized_targets = np.where(target_valid, targets / 100.0, 0.0)
        features = self.features_at(initialization_index)
        return {
            "features": torch.from_numpy(features),
            "targets": torch.from_numpy(normalized_targets.astype("float32")),
            "target_mask": torch.from_numpy(target_valid),
            "current_valid": torch.from_numpy(context_valid[-1]),
            "initialization_index": torch.tensor(initialization_index, dtype=torch.int64),
        }

    def features_at(self, initialization_index: int) -> np.ndarray:
        """Identical training/inference features; never reads observed targets."""
        start = initialization_index - self.context_days + 1
        if start < 0 or not np.all(
            np.diff(self.times[start:initialization_index + 1]) == np.timedelta64(1, "D")
        ):
            raise ValueError("A contiguous observation context is required")
        context = self.concentration[start:initialization_index + 1]
        context_valid = np.isfinite(context) & self.ocean_mask[None, :, :]
        normalized_context = np.where(context_valid, context / 100.0, 0.0)
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
        if self.forcing is not None:
            forcing = self.forcing[initialization_index]
            forcing_valid = np.isfinite(forcing)
            normalized_forcing = np.where(
                forcing_valid,
                (forcing - self.forcing_mean[:, None, None])
                / self.forcing_std[:, None, None],
                0.0,
            )
            features = np.concatenate(
                [features, normalized_forcing, forcing_valid.astype("float32")]
            ).astype("float32")
        return features


def training_forcing_statistics(
    forcing: np.ndarray, times: np.ndarray, training_split: SeaIceSplit
) -> tuple[np.ndarray, np.ndarray]:
    dates = times.astype("datetime64[D]")
    selected = np.asarray(
        [
            training_split.start <= date.fromisoformat(str(value)) <= training_split.end
            for value in dates
        ]
    )
    training = np.asarray(forcing, dtype="float64")[selected]
    mean = np.nanmean(training, axis=(0, 2, 3))
    std = np.nanstd(training, axis=(0, 2, 3))
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)) or np.any(std <= 0):
        raise ValueError("Invalid training-only forcing normalization statistics")
    return mean.astype("float32"), std.astype("float32")
