from pathlib import Path

from pydantic import BaseModel, Field


class SeaIceTrainingConfig(BaseModel):
    context_days: int = Field(default=7, ge=2)
    output_horizons_days: tuple[int, ...] = (1, 2, 3)
    hidden_channels: int = Field(default=16, ge=4)
    batch_size: int = Field(default=32, ge=1)
    learning_rate: float = Field(default=1e-3, gt=0)
    weight_decay: float = Field(default=1e-4, ge=0)
    maximum_epochs: int = Field(default=10, ge=1)
    early_stopping_patience: int = Field(default=3, ge=1)
    random_seed: int = 26059
    data_loader_workers: int = Field(default=0, ge=0)
    source_cube: Path = Path("data/processed/forecasting/sea_ice_bharati_daily.nc")
    model_path: Path = Path("models/sea_ice/polaris_sea_ice_residual_cnn_v0_1.pt")

    @property
    def input_channels(self) -> int:
        return self.context_days * 2 + 3
