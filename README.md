# POLARIS-AI

POLARIS-AI addresses Smart India Hackathon 2026 problem statement **SIH26059 — AI-Enabled
Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System**.

The project now includes Checkpoint 8 external adapter boundaries, offline connectivity and sync hardening, Checkpoint 7 operational integration, Checkpoint 6 manual dynamic replanning, the Checkpoint 5 time-dependent regional route planner, the Checkpoint 4 dynamic risk engine, plus the Checkpoint 3 sea-ice prediction engine, with **v0.3** selected
as the historical champion (mean locked MAE 3.911187 percentage points). The forecast API,
historical demonstration and Sea-Ice Forecast map distinguish model output, observations
and explicit persistence fallback. ERA5 is historical reanalysis, not future weather.
See [Checkpoint 3](docs/research/checkpoint-3-sea-ice-forecasting.md) for operation and limitations.
Routing, manual/event-triggered replanning, operational health, and offline-first synchronization are available for the Bharati / Prydz Bay regional study grid through +72H. They are research decision-support outputs, not certified navigation; no live AIS/GPS or direct satellite control is claimed.

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

## Release candidate

POLARIS-AI 1.0.0-rc1 is a Windows desktop release candidate for the Bharati / Prydz Bay regional research prototype. The planned desktop bundle uses a PyWebView shell, a folder-based PyInstaller scientific runtime, a local FastAPI backend, and the React production build. The launcher binds only to loopback, waits for `/health`, verifies the v0.3 model, and stores logs under `%LOCALAPPDATA%\POLARIS-AI`.

Build and deployment instructions are in [Windows deployment](docs/release/WINDOWS_DEPLOYMENT.md), while operators should start with the [quickstart](docs/release/OPERATOR_QUICKSTART.md). The [final architecture](docs/release/POLARIS_FINAL_ARCHITECTURE.md), [release notes](RELEASE_NOTES_1.0.0-rc1.md), [test report](docs/release/FINAL_TEST_REPORT.md), and [release checklist](docs/release/RELEASE_CHECKLIST.md) describe the validation boundary.

POLARIS-AI is a research and operational decision-support prototype. Route and risk outputs are advisory and do not replace certified navigation systems, official ice services, vessel operating procedures, or the authority of the ship's master.
