# POLARIS-AI

POLARIS-AI addresses Smart India Hackathon 2026 problem statement **SIH26059 — AI-Enabled
Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System**.

The long-term purpose is a scientifically defensible system for Antarctic environmental
forecasting and vessel navigation decisions. The project is currently at **Day 1 — Checkpoint
1: Repository Foundation**. It provides engineering infrastructure only; no scientific data
pipeline, model, mapping layer, or routing capability is implemented.

## Future architecture

The backend is divided into API, core infrastructure, ingestion, preprocessing, forecasting,
iceberg, routing, and vessel domains. A lightweight React frontend will later host mapping and
decision-support interfaces. Raw, processed, and demonstration data are isolated, while models,
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
support for it. Scientific dependencies are not installed during this foundation checkpoint.

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
