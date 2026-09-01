import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import torch
import xarray as xr

from backend.forecasting.sea_ice.ml.config import SeaIceV02TrainingConfig
from backend.forecasting.sea_ice.ml.dataset import SeaIceWindowDataset
from backend.forecasting.sea_ice.ml.network import (
    BoundedPersistenceResidualCNN,
    parameter_count,
)
from backend.forecasting.sea_ice.ml.training import save_weights, train_model
from backend.forecasting.sea_ice.models import TRAIN_SPLIT, VALIDATION_SPLIT

SOURCE_CHECKSUM = "5c14a6a05fc8c351edfb0eb3509b519be3339dc283a9e1b0dd82902ded6b0400"
MODEL_NAME = "POLARIS Sea-Ice Bounded Residual CNN v0.2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    config = SeaIceV02TrainingConfig()
    if sha256(config.source_cube) != SOURCE_CHECKSUM:
        raise ValueError("Processed source checksum does not match the verified cube")
    forcing_available = config.forcing_path.is_file()
    if forcing_available:
        raise ValueError(
            "A forcing file exists but has not yet passed the dedicated alignment workflow"
        )
    with xr.open_dataset(config.source_cube) as source:
        cube = source.load()
    train = SeaIceWindowDataset.from_xarray(cube, TRAIN_SPLIT, config.context_days)
    validation = SeaIceWindowDataset.from_xarray(
        cube, VALIDATION_SPLIT, config.context_days
    )
    smoke_model = BoundedPersistenceResidualCNN(
        config.context_days, config.hidden_channels
    )
    smoke = train_model(
        smoke_model, train, validation, config, maximum_epochs=2, smoke_samples=128
    )
    print("SMOKE RUN", json.dumps(smoke.history, indent=2))
    if smoke.history[-1]["train_mae_percent"] > smoke.history[0]["train_mae_percent"]:
        raise ValueError("Smoke-run training loss did not decrease")
    if args.smoke_only:
        return
    model = BoundedPersistenceResidualCNN(config.context_days, config.hidden_channels)
    outcome = train_model(model, train, validation, config)
    save_weights(model, outcome.best_state_dict, config.model_path, overwrite=args.overwrite)
    metadata = {
        "model_name": MODEL_NAME,
        "classification": "MODEL_PREDICTION",
        "architecture": "bounded persistence-residual depthwise-separable CNN",
        "parameter_count": parameter_count(model),
        "forcing_status": "UNAVAILABLE_FOR_TRAINING",
        "forcing_required_source": "ERA5 reanalysis-era5-single-levels",
        "forcing_variables": ["u10", "v10", "t2m"],
        "forcing_normalization": "TRAIN_SPLIT_ONLY when verified forcing is present",
        "context_days": config.context_days,
        "training_config": config.model_dump(mode="json"),
        "best_epoch": outcome.best_epoch,
        "best_validation_mae_percent": outcome.best_validation_mae_percent,
        "training_history": outcome.history,
        "source_dataset_sha256": SOURCE_CHECKSUM,
        "model_file_sha256": sha256(config.model_path),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cpu_count": os.cpu_count(),
        "trained_at": datetime.now(UTC).isoformat(),
    }
    config.model_path.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
