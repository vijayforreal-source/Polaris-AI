from pathlib import Path

import torch

from .network import BoundedPersistenceResidualCNN, PersistenceResidualCNN


def load_model(
    weights_path: Path,
    *,
    context_days: int = 7,
    hidden_channels: int = 16,
    forcing_variables: int = 0,
) -> PersistenceResidualCNN | BoundedPersistenceResidualCNN:
    """Load a locked model using the architecture implied by its feature width.

    v0.1 uses the original persistence residual network. The v0.3 champion adds
    normalized forcing channels and uses the bounded residual architecture.
    """
    model = (
        BoundedPersistenceResidualCNN(context_days, hidden_channels, forcing_variables)
        if forcing_variables
        else PersistenceResidualCNN(context_days, hidden_channels)
    )
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
