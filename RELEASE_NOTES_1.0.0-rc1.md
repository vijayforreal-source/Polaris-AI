# POLARIS-AI 1.0.0-rc1

This release candidate packages the Antarctic Voyage Intelligence & Decision Support regional prototype for Windows desktop evaluation.

## Included

- Sea-ice observation and +24/+48/+72-hour forecast views
- USNIC iceberg registry and historical transit intelligence
- Vessel-aware dynamic risk with explicit blocked-cell semantics
- SAFE / FAST / ECO / BALANCED time-dependent route planning
- Captain-controlled active routes and dynamic replanning
- Operational health, provenance, freshness, cache, sync, and connectivity states
- PyWebView desktop shell with a local FastAPI backend and production React assets

## Scientific record

Champion model: POLARIS Sea-Ice Multimodal Bounded Residual CNN v0.3. Locked historical MAE is 2.877915 pp at +24H, 4.066660 pp at +48H, and 4.788987 pp at +72H; mean 3.911187 pp. No retraining was performed for packaging.

## Limitations

The scope is Bharati / Prydz Bay. The system is not certified navigation, autonomous vessel control, live AIS/GPS, or a guaranteed-safe service. ERA5 is historical reanalysis rather than an operational weather forecast. No bathymetry or operational future-weather provider is claimed. Historical verified-voyage data may be empty. The installer is unsigned. The current data snapshot is stale/degraded where reported by Operational Status.

## Validation

The source release passed 165 pytest tests, Ruff, the production frontend build, main browser smoke, and historical transit browser smoke in the release audit. Packaged Windows validation requires a Windows machine with PyInstaller, PyWebView, and Inno Setup; this repository contains the reproducible build and smoke commands.
