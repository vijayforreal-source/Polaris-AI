import json
from pathlib import Path

import numpy as np
import torch
import xarray as xr
from torch.utils.data import DataLoader

from backend.forecasting.sea_ice.forecast_service import _sha256
from backend.forecasting.sea_ice.ml.atmospheric import load_daily_forcing
from backend.forecasting.sea_ice.ml.config import (
    SeaIceV02TrainingConfig,
    SeaIceV03TrainingConfig,
)
from backend.forecasting.sea_ice.ml.dataset import (
    FORCING_VARIABLES,
    SeaIceWindowDataset,
    training_forcing_statistics,
)
from backend.forecasting.sea_ice.ml.evaluation import (
    common_evaluation_mask,
    daily_mae,
    evaluate_model,
    write_model_results,
)
from backend.forecasting.sea_ice.ml.network import BoundedPersistenceResidualCNN
from backend.forecasting.sea_ice.models import TEST_SPLIT, TRAIN_SPLIT

RESULTS_PATH = Path(
    "backend/forecasting/sea_ice/ml/model_results_v03.json"
)

V02_RESULTS_PATH = Path(
    "backend/forecasting/sea_ice/ml/model_results_v02.json"
)

V03_METADATA_PATH = Path(
    "models/sea_ice/"
    "polaris_sea_ice_multimodal_bounded_residual_cnn_v0_3.metadata.json"
)

MODEL_NAME = "POLARIS Sea-Ice Multimodal Bounded Residual CNN v0.3"

BOOTSTRAP_SEED = 26059
BOOTSTRAP_RESAMPLES = 10_000


def predictions(
    model: torch.nn.Module,
    dataset: SeaIceWindowDataset,
    batch_size: int,
) -> np.ndarray:
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    output = []

    model.eval()

    with torch.no_grad():
        for batch in loader:
            output.append(
                model(batch["features"]).numpy() * 100.0
            )

    return np.concatenate(output)


def reference_data(
    dataset: SeaIceWindowDataset,
    batch_size: int,
):
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    targets = []
    masks = []
    current_valid = []
    indices = []

    for batch in loader:
        targets.append(batch["targets"].numpy() * 100.0)
        masks.append(batch["target_mask"].numpy())
        current_valid.append(batch["current_valid"].numpy())
        indices.append(batch["initialization_index"].numpy())

    return (
        np.concatenate(targets),
        np.concatenate(masks),
        np.concatenate(current_valid),
        np.concatenate(indices),
    )


def paired_bootstrap(
    candidate: np.ndarray,
    reference: np.ndarray,
):
    difference = candidate - reference

    rng = np.random.default_rng(BOOTSTRAP_SEED)

    means = np.empty(
        BOOTSTRAP_RESAMPLES,
        dtype="float64",
    )

    for start in range(0, BOOTSTRAP_RESAMPLES, 1000):
        count = min(
            1000,
            BOOTSTRAP_RESAMPLES - start,
        )

        selection = rng.integers(
            0,
            len(difference),
            size=(count, len(difference)),
        )

        means[start : start + count] = difference[
            selection
        ].mean(axis=1)

    lower, upper = np.quantile(
        means,
        [0.025, 0.975],
    )

    return {
        "mean_v03_minus_v02_mae_pp": float(
            difference.mean()
        ),
        "ci_95_lower_pp": float(lower),
        "ci_95_upper_pp": float(upper),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
    }


def main():
    if RESULTS_PATH.exists():
        raise SystemExit("Locked results already exist; preserve them. No repeated test selection.")
    config = SeaIceV03TrainingConfig()
    v02_config = SeaIceV02TrainingConfig()

    metadata = json.loads(
        V03_METADATA_PATH.read_text(encoding="utf-8")
    )
    for path, key in ((config.model_path, "model_file_sha256"),
                      (config.source_cube, "source_dataset_sha256"),
                      (config.forcing_path, "forcing_dataset_sha256")):
        if _sha256(path) != metadata[key]:
            raise ValueError(f"Artifact checksum mismatch: {path}")

    with xr.open_dataset(config.source_cube) as source:
        cube = source.load()

    forcing = load_daily_forcing(
        config.forcing_path,
        cube.time.values,
        cube.latitude.values,
        cube.longitude.values,
    )

    forcing_mean = np.asarray(
        [
            metadata["forcing_normalization"][name]["mean"]
            for name in FORCING_VARIABLES
        ],
        dtype="float32",
    )

    forcing_std = np.asarray(
        [
            metadata["forcing_normalization"][name]["std"]
            for name in FORCING_VARIABLES
        ],
        dtype="float32",
    )

    check_mean, check_std = training_forcing_statistics(
        forcing,
        cube.time.values,
        TRAIN_SPLIT,
    )

    if not np.allclose(
        forcing_mean,
        check_mean,
        atol=1e-5,
    ):
        raise ValueError(
            "Frozen forcing mean does not match training split."
        )

    if not np.allclose(
        forcing_std,
        check_std,
        atol=1e-5,
    ):
        raise ValueError(
            "Frozen forcing std does not match training split."
        )

    v03_dataset = SeaIceWindowDataset(
        concentration_percent=cube.ice_conc.values,
        times=cube.time.values,
        ocean_mask=cube.valid_ocean_mask.values,
        split=TEST_SPLIT,
        context_days=config.context_days,
        forcing=forcing,
        forcing_mean=forcing_mean,
        forcing_std=forcing_std,
    )

    v02_dataset = SeaIceWindowDataset.from_xarray(
        cube,
        TEST_SPLIT,
        v02_config.context_days,
    )

    if len(v03_dataset) != 584:
        raise ValueError(
            f"Locked test changed: {len(v03_dataset)} samples"
        )

    if (
        v03_dataset.initialization_indices
        != v02_dataset.initialization_indices
    ):
        raise ValueError(
            "v0.2 and v0.3 test dates are not identical."
        )

    v03_model = BoundedPersistenceResidualCNN(
        context_days=config.context_days,
        hidden_channels=config.hidden_channels,
        forcing_variables=len(FORCING_VARIABLES),
    )

    v03_model.load_state_dict(
        torch.load(
            config.model_path,
            map_location="cpu",
            weights_only=True,
        )
    )

    v02_model = BoundedPersistenceResidualCNN(
        context_days=v02_config.context_days,
        hidden_channels=v02_config.hidden_channels,
        forcing_variables=0,
    )

    v02_model.load_state_dict(
        torch.load(
            v02_config.model_path,
            map_location="cpu",
            weights_only=True,
        )
    )

    print("LOCKED TEST: 584 initialization dates")

    results = evaluate_model(
        v03_model,
        v03_dataset,
        cube,
        batch_size=config.batch_size,
        model_name=MODEL_NAME,
    )

    v03_pred = predictions(
        v03_model,
        v03_dataset,
        config.batch_size,
    )

    v02_pred = predictions(
        v02_model,
        v02_dataset,
        v02_config.batch_size,
    )

    (
        targets,
        target_masks,
        latest_valid,
        init_indices,
    ) = reference_data(
        v03_dataset,
        config.batch_size,
    )

    ocean = np.asarray(
        cube.valid_ocean_mask.values,
        dtype=bool,
    )

    source_fields = np.asarray(
        cube.ice_conc.values,
        dtype="float32",
    )

    persistence = source_fields[init_indices]

    frozen_v02 = json.loads(
        V02_RESULTS_PATH.read_text(encoding="utf-8")
    )

    comparison = {}

    for horizon_index, hours in enumerate((24, 48, 72)):
        key = f"{hours}H"

        target = targets[:, horizon_index]

        mask = common_evaluation_mask(
            ocean,
            latest_valid,
            target_masks[:, horizon_index],
            persistence,
        )

        v03_daily = daily_mae(
            v03_pred[:, horizon_index],
            target,
            mask,
        )

        v02_daily = daily_mae(
            v02_pred[:, horizon_index],
            target,
            mask,
        )

        v03_mae = float(v03_daily.mean())
        v02_mae = float(v02_daily.mean())

        frozen_v02_mae = frozen_v02[
            "horizons"
        ][key]["ai"]["mae_percentage_points"]

        if not np.isclose(
            v02_mae,
            frozen_v02_mae,
            atol=1e-6,
            rtol=0,
        ):
            raise ValueError(
                f"v0.2 benchmark mismatch at {key}"
            )

        bootstrap = paired_bootstrap(
            v03_daily,
            v02_daily,
        )

        comparison[key] = {
            "v03_mae_pp": v03_mae,
            "v02_mae_pp": v02_mae,
            "improvement_pp": float(v02_mae - v03_mae),
            "relative_improvement": float(
                1.0 - v03_mae / v02_mae
            ),
            "fraction_days_v03_beats_v02": float(
                np.mean(v03_daily < v02_daily)
            ),
            "bootstrap_v03_minus_v02": bootstrap,
            "bootstrap_ci_excludes_zero": bool(
                bootstrap["ci_95_upper_pp"] < 0
                or bootstrap["ci_95_lower_pp"] > 0
            ),
        }
        for season, values in results["horizons"][key]["seasonal"].items():
            values["v02_mae_pp"] = frozen_v02["horizons"][key]["seasonal"][season]["ai_mae_pp"]
        results["horizons"][key]["bharati_local"]["v02"] = (
            frozen_v02["horizons"][key]["bharati_local"]["ai"]
        )

    results["comparison_v02"] = comparison

    v03_mean = float(
        np.mean(
            [
                results["horizons"][key]["ai"][
                    "mae_percentage_points"
                ]
                for key in ("24H", "48H", "72H")
            ]
        )
    )

    v02_mean = float(
        np.mean(
            [
                frozen_v02["horizons"][key]["ai"][
                    "mae_percentage_points"
                ]
                for key in ("24H", "48H", "72H")
            ]
        )
    )

    long_horizon_ok = bool(
        comparison["48H"]["v03_mae_pp"]
        <= comparison["48H"]["v02_mae_pp"]
        and comparison["72H"]["v03_mae_pp"]
        <= comparison["72H"]["v02_mae_pp"]
    )

    adopt = bool(
        v03_mean < v02_mean
        and long_horizon_ok
        and results["clipping"]["clipped_valid_values"] == 0
    )

    results["summary"] = {
        "v03_mean_mae_pp": v03_mean,
        "v02_mean_mae_pp": v02_mean,
        "relative_mean_improvement": float(
            1.0 - v03_mean / v02_mean
        ),
        "long_horizon_requirement_passed": long_horizon_ok,
        "decision": (
            "ADOPT_V03"
            if adopt
            else "KEEP_V02"
        ),
    }

    results["provenance"] = {
        key: metadata[key] for key in (
            "source_dataset_sha256", "forcing_dataset_sha256", "model_file_sha256",
            "normalization_period", "forcing_time_semantics")
    }
    write_model_results(
        results,
        RESULTS_PATH,
    )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
