# POLARIS-AI

POLARIS-AI addresses Smart India Hackathon 2026 problem statement **SIH26059 — AI-Enabled
Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System**.

The project now includes the Checkpoint 4 dynamic risk engine, plus the Checkpoint 3 sea-ice prediction engine, with **v0.3** selected
as the historical champion (mean locked MAE 3.911187 percentage points). The forecast API,
historical demonstration and Sea-Ice Forecast map distinguish model output, observations
and explicit persistence fallback. ERA5 is historical reanalysis, not future weather.
See [Checkpoint 3](docs/research/checkpoint-3-sea-ice-forecasting.md) for operation and limitations.
Routing remains Checkpoint 5 work.

## Future architecture

The backend is divided into API, core infrastructure, ingestion, preprocessing, forecasting,
iceberg, routing, and vessel domains. A React frontend hosts Antarctic mapping and
scientific decision-support interfaces. Raw, processed, and demonstration data are isolated, while models,
experiments, notebooks, tests, scripts, and documentation have explicit homes.

```text
backend/       FastAPI and future scientific service domains
frontend/      React + Vite client foundation
data/          Ignored raw, processed, and demo data areas
models/        Future model artifacts (large weights are ignored)
experiments/   Reproducible experimental work
notebooks/     Exploratory work, not production pipelines
scripts/       Operational developer scripts
tests/         Automated tests
docs/          Research, architecture, and citations
```

## Backend setup

Python 3.13 is the recommended development runtime. The currently supported range is
Python `>=3.11,<3.14`. Python 3.14 is intentionally excluded for now because some planned
scientific dependencies, including the Copernicus Marine Toolbox, have not yet standardized
support for it. Install scientific and development dependencies in the project virtual environment.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn backend.app.main:app --reload
```

Configuration is loaded from `POLARIS_`-prefixed environment variables. Copy `.env.example`
to an untracked `.env` when local overrides are needed.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

## Verification

```powershell
python -m pytest
python -m ruff check .
cd frontend
npm run build
```

## Scientific integrity

**No synthetic scientific output should be presented as observational or predicted Antarctic
data.**

Observed data, forecast data, and model-generated predictions will remain distinguishable
throughout the project. Future source datasets will retain provenance, timestamps, units,
quality information, and native CRS metadata before any canonical conversion.
