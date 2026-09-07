import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import torch
import xarray as xr

from backend.forecasting.sea_ice.ml.atmospheric import load_daily_forcing
from backend.forecasting.sea_ice.ml.config import SeaIceV03TrainingConfig
from backend.forecasting.sea_ice.ml.dataset import (
    FORCING_VARIABLES,
    SeaIceWindowDataset,
    training_forcing_statistics,
)
from backend.forecasting.sea_ice.ml.network import (
    BoundedPersistenceResidualCNN,
    parameter_count,
)
from backend.forecasting.sea_ice.ml.training import save_weights, train_model
from backend.forecasting.sea_ice.models import TRAIN_SPLIT, VALIDATION_SPLIT

SOURCE_CHECKSUM = (
    "5c14a6a05fc8c351edfb0eb3509b519be3339dc283a9e1b0dd82902ded6b0400"
)

FORCING_CHECKSUM = (
    "ba09622e086ce522534ea640d9e59fe75f2b3874be4cd63063e7fdf9a72a5659"
)

MODEL_NAME = (
    "POLARIS Sea-Ice Multimodal "
    "Bounded Residual CNN v0.3"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def create_dataset(
    cube: xr.Dataset,
    forcing,
    forcing_mean,
    forcing_std,
    split,
    context_days: int,
) -> SeaIceWindowDataset:
    return SeaIceWindowDataset(
        concentration_percent=cube.ice_conc.values,
        times=cube.time.values,
        ocean_mask=cube.valid_ocean_mask.values,
        split=split,
        context_days=context_days,
        forcing=forcing,
        forcing_mean=forcing_mean,
        forcing_std=forcing_std,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    parser.add_argument(
        "--smoke-only",
        action="store_true",
    )

    args = parser.parse_args()

    config = SeaIceV03TrainingConfig()

    if sha256(config.source_cube) != SOURCE_CHECKSUM:
        raise ValueError(
            "Processed sea-ice source checksum "
            "does not match frozen dataset"
        )

    if not config.forcing_path.is_file():
        raise FileNotFoundError(
            f"ERA5 forcing file not found: "
            f"{config.forcing_path}"
        )

    if sha256(config.forcing_path) != FORCING_CHECKSUM:
        raise ValueError(
            "ERA5 forcing checksum does not "
            "match verified forcing cube"
        )

    with xr.open_dataset(config.source_cube) as source:
        cube = source.load()

    forcing = load_daily_forcing(
        config.forcing_path,
        cube.time.values,
        cube.latitude.values,
        cube.longitude.values,
    )

    forcing_mean, forcing_std = (
        training_forcing_statistics(
            forcing,
            cube.time.values,
            TRAIN_SPLIT,
        )
    )

    print(
        "TRAIN-ONLY FORCING NORMALIZATION"
    )

    for index, variable in enumerate(
        FORCING_VARIABLES
    ):
        print(
            variable,
            "mean=",
            float(forcing_mean[index]),
            "std=",
            float(forcing_std[index]),
        )

    train = create_dataset(
        cube,
        forcing,
        forcing_mean,
        forcing_std,
        TRAIN_SPLIT,
        config.context_days,
    )

    validation = create_dataset(
        cube,
        forcing,
        forcing_mean,
        forcing_std,
        VALIDATION_SPLIT,
        config.context_days,
    )

    smoke_model = BoundedPersistenceResidualCNN(
        context_days=config.context_days,
        hidden_channels=config.hidden_channels,
        forcing_variables=len(
            FORCING_VARIABLES
        ),
    )

    print(
        "v0.3 parameter count:",
        parameter_count(smoke_model),
    )

    smoke = train_model(
        smoke_model,
        train,
        validation,
        config,
        maximum_epochs=2,
        smoke_samples=128,
    )

    print(
        "SMOKE RUN",
        json.dumps(
            smoke.history,
            indent=2,
        ),
    )

    if (
        smoke.history[-1]["train_mae_percent"]
        > smoke.history[0]["train_mae_percent"]
    ):
        raise ValueError(
            "Smoke-run training loss "
            "did not decrease"
        )

    if args.smoke_only:
        return

    model = BoundedPersistenceResidualCNN(
        context_days=config.context_days,
        hidden_channels=config.hidden_channels,
        forcing_variables=len(
            FORCING_VARIABLES
        ),
    )

    outcome = train_model(
        model,
        train,
        validation,
        config,
    )

    save_weights(
        model,
        outcome.best_state_dict,
        config.model_path,
        overwrite=args.overwrite,
    )

    metadata = {
        "model_name": MODEL_NAME,
        "classification":
            "MODEL_PREDICTION",
        "architecture":
            "multimodal bounded "
            "persistence-residual "
            "depthwise-separable CNN",
        "parameter_count":
            parameter_count(model),
        "context_days":
            config.context_days,
        "forcing_status":
            "ERA5_INITIALIZATION_STATE",
        "forcing_dataset":
            "reanalysis-era5-single-levels",
        "forcing_variables":
            list(FORCING_VARIABLES),
        "forcing_time_semantics":
            "00:00 UTC initialization-state only",
        "forcing_normalization":
            {
                variable: {
                    "mean":
                        float(
                            forcing_mean[index]
                        ),
                    "std":
                        float(
                            forcing_std[index]
                        ),
                }
                for index, variable in enumerate(
                    FORCING_VARIABLES
                )
            },
        "normalization_period":
            {
                "start":
                    str(TRAIN_SPLIT.start),
                "end":
                    str(TRAIN_SPLIT.end),
            },
        "training_config":
            config.model_dump(
                mode="json"
            ),
        "best_epoch":
            outcome.best_epoch,
        "best_validation_mae_percent":
            outcome.best_validation_mae_percent,
        "training_history":
            outcome.history,
        "source_dataset_sha256":
            SOURCE_CHECKSUM,
        "forcing_dataset_sha256":
            FORCING_CHECKSUM,
        "model_file_sha256":
            sha256(
                config.model_path
            ),
        "torch_version":
            torch.__version__,
        "cuda_available":
            torch.cuda.is_available(),
        "cpu_count":
            os.cpu_count(),
        "trained_at":
            datetime.now(
                UTC
            ).isoformat(),
    }

    config.model_path.with_suffix(
        ".metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            metadata,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()