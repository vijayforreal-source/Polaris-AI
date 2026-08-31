from pathlib import Path

DATASET_ID = "reanalysis-era5-single-levels"
VARIABLES = ("10m_u_component_of_wind", "10m_v_component_of_wind")


def cds_credentials_available(home: Path | None = None) -> bool:
    base = home if home is not None else Path.home()
    return (base / ".cdsapirc").is_file()


def monthly_request(year: int, month: int) -> dict[str, object]:
    """Return a credential-free, deterministic CDS request description."""
    return {
        "product_type": ["reanalysis"],
        "variable": list(VARIABLES),
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": [f"{day:02d}" for day in range(1, 32)],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [-51.08, -39.5, -61.53, -28.5],
    }
