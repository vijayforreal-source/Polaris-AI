import json

import xarray as xr

from backend.forecasting.sea_ice.ml.config import SeaIceTrainingConfig
from backend.forecasting.sea_ice.ml.dataset import SeaIceWindowDataset
from backend.forecasting.sea_ice.ml.evaluation import evaluate_model, write_model_results
from backend.forecasting.sea_ice.ml.inference import load_model
from backend.forecasting.sea_ice.models import TEST_SPLIT


def main() -> None:
    config = SeaIceTrainingConfig()
    with xr.open_dataset(config.source_cube) as source:
        cube = source.load()
    dataset = SeaIceWindowDataset.from_xarray(cube, TEST_SPLIT, config.context_days)
    model = load_model(
        config.model_path,
        context_days=config.context_days,
        hidden_channels=config.hidden_channels,
    )
    results = evaluate_model(model, dataset, cube, batch_size=config.batch_size)
    write_model_results(results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
