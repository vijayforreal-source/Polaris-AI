import copy
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset

from .config import SeaIceTrainingConfig


def configure_determinism(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def masked_mae(
    prediction: torch.Tensor, target: torch.Tensor, valid_mask: torch.Tensor
) -> torch.Tensor:
    if not torch.any(valid_mask):
        raise ValueError("masked MAE received no valid target pixels")
    return torch.abs(prediction - target)[valid_mask].mean()


@dataclass(frozen=True)
class TrainingOutcome:
    best_epoch: int
    best_validation_mae_percent: float
    history: list[dict[str, float]]
    best_state_dict: dict[str, torch.Tensor]


def _epoch(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
) -> float:
    training = optimizer is not None
    model.train(training)
    absolute_error_sum = 0.0
    valid_count = 0
    for batch in loader:
        features = batch["features"].to(device)
        targets = batch["targets"].to(device)
        target_mask = batch["target_mask"].to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        prediction = model(features)
        loss = masked_mae(prediction, targets, target_mask)
        if training:
            loss.backward()
            optimizer.step()
        absolute_error_sum += float(
            torch.abs(prediction.detach() - targets)[target_mask].sum().cpu()
        )
        valid_count += int(target_mask.sum().cpu())
    return 100.0 * absolute_error_sum / valid_count


def train_model(
    model: nn.Module,
    train_dataset: Dataset,
    validation_dataset: Dataset,
    config: SeaIceTrainingConfig,
    *,
    maximum_epochs: int | None = None,
    smoke_samples: int | None = None,
) -> TrainingOutcome:
    configure_determinism(config.random_seed)
    torch.set_num_threads(min(8, torch.get_num_threads()))
    device = torch.device("cpu")
    model.to(device)
    if smoke_samples is not None:
        train_dataset = Subset(
            train_dataset, range(min(smoke_samples, len(train_dataset)))
        )
        validation_dataset = Subset(
            validation_dataset, range(min(smoke_samples, len(validation_dataset)))
        )
    generator = torch.Generator().manual_seed(config.random_seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.data_loader_workers,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.data_loader_workers,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    history: list[dict[str, float]] = []
    best_epoch = 0
    best_validation = float("inf")
    best_state = copy.deepcopy(model.state_dict())
    stale_epochs = 0
    epochs = maximum_epochs or config.maximum_epochs
    for epoch in range(1, epochs + 1):
        train_mae = _epoch(model, train_loader, device, optimizer)
        with torch.no_grad():
            validation_mae = _epoch(model, validation_loader, device, None)
        history.append(
            {
                "epoch": float(epoch),
                "train_mae_percent": train_mae,
                "validation_mae_percent": validation_mae,
            }
        )
        if not np.isfinite(train_mae) or not np.isfinite(validation_mae):
            raise ValueError("Non-finite training metric detected")
        if validation_mae < best_validation:
            best_validation = validation_mae
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= config.early_stopping_patience:
                break
    return TrainingOutcome(best_epoch, best_validation, history, best_state)


def save_weights(
    model: nn.Module,
    state_dict: dict[str, torch.Tensor],
    path: Path,
    *,
    overwrite: bool,
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing verified model: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    model.load_state_dict(state_dict)
    torch.save(state_dict, path)
