import json
from pathlib import Path

import torch
import xarray as xr

from backend.forecasting.sea_ice.ml.config import SeaIceV02TrainingConfig
from backend.forecasting.sea_ice.ml.dataset import SeaIceWindowDataset
from backend.forecasting.sea_ice.ml.evaluation import evaluate_model, write_model_results
from backend.forecasting.sea_ice.ml.network import BoundedPersistenceResidualCNN
from backend.forecasting.sea_ice.models import TEST_SPLIT

RESULTS_PATH = Path("backend/forecasting/sea_ice/ml/model_results_v02.json")
MODEL_NAME = "POLARIS Sea-Ice Bounded Residual CNN v0.2"


def main() -> None:
    config = SeaIceV02TrainingConfig()
    with xr.open_dataset(config.source_cube) as source:
        cube = source.load()
    dataset = SeaIceWindowDataset.from_xarray(cube, TEST_SPLIT, config.context_days)
    model = BoundedPersistenceResidualCNN(config.context_days, config.hidden_channels)
    model.load_state_dict(
        torch.load(config.model_path, map_location="cpu", weights_only=True)
    )
    model.eval()
    results = evaluate_model(
        model,
        dataset,
        cube,
        batch_size=config.batch_size,
        model_name=MODEL_NAME,
    )
    results["comparison_model"] = json.loads(
        Path("backend/forecasting/sea_ice/ml/model_results.json").read_text(
            encoding="utf-8"
        )
    )["horizons"]
    write_model_results(results, RESULTS_PATH)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
