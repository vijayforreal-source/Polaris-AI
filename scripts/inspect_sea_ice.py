import json
from pathlib import Path

from backend.ingestion.copernicus_sea_ice import inspect_netcdf, sha256_file


def main() -> None:
    candidates = sorted(Path("data/raw/copernicus/osi_saf_sic_south").glob("*/*.nc"))
    if not candidates:
        raise SystemExit("No downloaded Copernicus sea-ice NetCDF found")

    path = candidates[-1]
    sidecar_path = path.with_suffix(path.suffix + ".metadata.json")
    metadata = json.loads(sidecar_path.read_text(encoding="utf-8"))
    inspection = inspect_netcdf(path)

    summary = {
        "Source": metadata["source"],
        "Product ID": metadata["product_id"],
        "Dataset ID": metadata["dataset_id"],
        "Classification": metadata["classification"],
        "Observation time": metadata["observed_at"],
        "Variable": inspection["variable"],
        "Units": inspection["units"],
        "Dimensions": inspection["dimensions"],
        "Shape": inspection["shape"],
        "Valid min": inspection["valid_min"],
        "Valid max": inspection["valid_max"],
        "Missing count": inspection["missing_count"],
        "Native CRS": metadata["native_crs"],
        "Grid mapping variable": inspection["grid_mapping_variable"],
        "Grid mapping attributes": inspection["grid_mapping_attributes"],
        "SHA-256": sha256_file(path),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
