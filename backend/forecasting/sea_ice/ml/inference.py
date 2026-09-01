from pathlib import Path

import torch

from .network import PersistenceResidualCNN


def load_model(
    weights_path: Path,
    *,
    context_days: int = 7,
    hidden_channels: int = 16,
) -> PersistenceResidualCNN:
    model = PersistenceResidualCNN(context_days, hidden_channels)
    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


@torch.no_grad()
def deterministic_inference(
    model: PersistenceResidualCNN, features: torch.Tensor
) -> torch.Tensor:
    model.eval()
    return model(features.to("cpu")).cpu()
