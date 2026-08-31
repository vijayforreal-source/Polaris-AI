"""Verified aggregate results from the reproducible 1-hour A76C evaluation."""

A76C_PHYSICS_EVALUATION = {
    "iceberg_id": "A76C",
    "label": "PHYSICS-GUIDED TRAJECTORY HINDCAST",
    "evaluation_mode": "HINDCAST",
    "prediction_classification": "MODEL_PREDICTION",
    "integration_timestep_hours": 1.0,
    "forcing": {
        "ocean": "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i",
        "ocean_classification": "ANALYSIS",
        "wind": "reanalysis-era5-single-levels",
        "wind_classification": "REANALYSIS",
    },
    "models": {
        "P0_PERSISTENCE": {
            "n": 34, "mean_km": 53.642824, "median_km": 44.434367,
            "rmse_km": 71.394677, "p90_km": 138.283984, "maximum_km": 184.885017,
        },
        "P1_CONSTANT_VELOCITY": {
            "n": 33, "mean_km": 65.582919, "median_km": 49.757257,
            "rmse_km": 81.924393, "p90_km": 144.422906, "maximum_km": 201.767104,
        },
        "P2_SURFACE_CURRENT": {
            "n": 34, "mean_km": 41.341801, "median_km": 32.767249,
            "rmse_km": 48.755161, "p90_km": 76.205050, "maximum_km": 105.948346,
        },
        "P3_WDE17_SURFACE": {
            "n": 33, "mean_km": 41.598829, "median_km": 33.861022,
            "rmse_km": 49.446764, "p90_km": 83.364052, "maximum_km": 108.186706,
        },
        "P2W_EMPIRICAL_2_PERCENT_WIND": {
            "n": 33, "mean_km": 101.699053, "median_km": 97.063670,
            "rmse_km": 110.488619, "p90_km": 157.832117, "maximum_km": 190.089324,
        },
        "P2_CURRENT_29M": {
            "n": 34, "mean_km": 39.375306, "median_km": 30.001788,
            "rmse_km": 48.689514, "p90_km": 71.372732, "maximum_km": 117.302625,
        },
        "P2_CURRENT_92M": {
            "n": 34, "mean_km": 43.506810, "median_km": 36.944775,
            "rmse_km": 54.624833, "p90_km": 76.977301, "maximum_km": 164.498240,
        },
        "P3_WDE17_STYLE_29M": {
            "n": 33, "mean_km": 39.882801, "median_km": 30.837070,
            "rmse_km": 49.444144, "p90_km": 64.556034, "maximum_km": 122.544328,
        },
        "P3_WDE17_STYLE_92M": {
            "n": 33, "mean_km": 42.506868, "median_km": 33.942945,
            "rmse_km": 53.750377, "p90_km": 79.141107, "maximum_km": 149.000620,
        },
    },
    "skill_vs_persistence_mean_error": {
        "P1_CONSTANT_VELOCITY": -0.218113,
        "P2_SURFACE_CURRENT": 0.229313,
        "P3_WDE17_SURFACE": 0.206142,
        "P2W_EMPIRICAL_2_PERCENT_WIND": -0.940790,
        "P2_CURRENT_29M": 0.265973,
        "P2_CURRENT_92M": 0.188954,
        "P3_WDE17_STYLE_29M": 0.238890,
        "P3_WDE17_STYLE_92M": 0.188814,
    },
    "wind_contribution_ratio": {
        "mean": 0.101820,
        "median": 0.069197,
        "minimum": 0.000009,
        "maximum": 5.032259,
    },
    "best_canonical_physics_model": "P2_SURFACE_CURRENT",
    "best_depth_sensitivity_run": "P2_CURRENT_29M",
    "coverage_note": (
        "Wind-dependent models use 33 intervals; 2026-08-20 to 2026-08-27 is excluded "
        "because ERA5 ends at 2026-08-26T12:00Z."
    ),
}
