import torch
from torch import nn


class SeparableConvBlock(nn.Module):
    def __init__(self, input_channels: int, output_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(
                input_channels,
                input_channels,
                kernel_size=3,
                padding=1,
                groups=input_channels,
            ),
            nn.Conv2d(input_channels, output_channels, kernel_size=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.block(inputs)


class PersistenceResidualCNN(nn.Module):
    def __init__(
        self, context_days: int = 7, hidden_channels: int = 16
    ) -> None:
        super().__init__()
        self.context_days = context_days
        input_channels = context_days * 2 + 3
        expanded = hidden_channels * 2
        self.encoder = nn.Sequential(
            nn.Conv2d(input_channels, hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            SeparableConvBlock(hidden_channels, expanded),
            SeparableConvBlock(expanded, expanded),
            SeparableConvBlock(expanded, hidden_channels),
        )
        self.residual_head = nn.Conv2d(hidden_channels, 3, kernel_size=1)

    def raw_prediction(self, features: torch.Tensor) -> torch.Tensor:
        residual = self.residual_head(self.encoder(features))
        latest_observation = features[:, self.context_days - 1 : self.context_days]
        return latest_observation + residual

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return torch.clamp(self.raw_prediction(features), 0.0, 1.0)


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
