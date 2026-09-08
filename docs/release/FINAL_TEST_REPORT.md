# Final Windows release test report

Validation date: 2026-09-08. Starting HEAD: `5e207eb307e9d64c68e6f1ff1fd3e952c225f58d`, clean.
History included packaging (`e221986`), Navigation (`fa4b937`) and browser fixes (`e41fea7`).
Runtime rebuilt from clean commit `4c51bd6e6ff28de9d7a8e27f069ea226504d0261`.
Later changes are validation scripts, documentation and release metadata only.

| Gate | Actual result |
|---|---|
| PyInstaller rebuild | PASS, fresh `release/windows/rc1/dist/POLARIS-AI`, 1,615,180,087 bytes; old staging was not reused |
| Native desktop | PASS, actual PyWebView window, process/window handle, startup logs and native WebView CDP inspected |
| Port handshake | PASS on backend 8017 and dynamically selected frontend port; production HTML receives API address and CORS origin |
| Navigation | PASS, real workspace, four objectives, active-route and replanning controls; no obsolete PENDING placeholder |
| Model | PASS, v0.3 checksum verified, safe output `(1,3,4,4)`; installed historical 2025-06-01 inference used ERA5 REANALYSIS and returned three 52x100 grids without fallback |
| APIs | PASS, health/operations/connectivity/cache/routes/replanning status and sea-ice/iceberg/risk endpoints HTTP 200 |
| Production route attempt | HTTP 200 ORIGIN_BLOCKED, scientifically valid for the local snapshot |
| Replanning API | Expected 404 without an active voyage; HTTP 200 with a DEMO active route in offline validation |
| Isolated packaged DEMO | PASS, mission, synthetic risk, SAFE/FAST/ECO/BALANCED, activation, REROUTE_REQUIRED and captain acceptance; standalone process exits without contaminating production data |
| Single instance | PASS, second executable exited 0, one desktop remained; local Windows-session mutex |
| Shutdown | PASS eventual cleanup. Packaged process and all six WebView children disappeared. Installed parent remained at the 15-second probe, then exited normally; follow-up found no POLARIS process. No force kill was used. Final packaged close took 16.575 seconds with no remaining desktop/WebView processes |
| Inno installer | PASS, compile completed in 288.500 seconds |
| Install | PASS, silent CURRENTUSER install outside repository into LocalAppData/Programs/POLARIS AI RC1, path contains spaces, no elevation or restart |
| Installed native UI | PASS, Mission Control, Ice Intelligence, Sea-Ice Forecast, Navigation, Dynamic Risk, route/replanning, Operations/Connectivity |
| Credential independence | PASS startup/API/historical inference with empty credential home, provider variables removed, Windows-only PATH, no virtual environment or PYTHONPATH; normal-profile relaunch used for WebView CDP |
| Controlled offline | PASS manual OFFLINE override, local UI reload/map, all main panels and local APIs with external browser URLs blocked; not physical network disconnection |
| Reconnect | PASS OFFLINE to ONLINE/HIGH; active DEMO-RECONNECT-ONLY route unchanged. Policy permits deferred work online; queue was empty, so no actual deferred transfer claimed |
| AppData | Logs, readiness JSON and WebView storage under LocalAppData/POLARIS-AI. Mission/route/events/cache-index/sync are in memory, explicitly deferred before operational release |
| Install write audit | PASS, zero file size/mtime changes across all installed files after normal runtime |
| Path independence | PASS, no loaded module from repo, virtual environment or global Python; first-party source/runtime metadata contains no developer absolute paths |
| Uninstall | PASS exit 0, directory removed, no restart; AppData logs/readiness/demo report hashes unchanged |
| Pytest | 167 passed, 14 warnings, 153.30 seconds |
| Ruff | PASS |
| Frontend | PASS, 324 modules, 676.60 KB JS / 202.30 KB gzip; chunk advisory retained |
| Main browser smoke | PASS on packaged and installed native WebView production assets |
| Historical browser smoke | PASS on packaged and installed native WebView; fixture is browser-only; geometry unit checks run against source module in Node |
| Security scan | PASS reviewed source, staging and installer inputs: no .env or private keys, no first-party credential values; public CA bundles and botocore example values classified as dependency data |

## Measured performance

- First packaged launch to observed backend readiness: 29.968 seconds; warm packaged launch: 5.336 seconds. A later packaged validation launch took 52.736 seconds; startup varies substantially on this host.
- First installed launch to observed backend readiness: 16.318 seconds. Native document load: 18.473 seconds from process launch (not a separate measurement of all async panels being ready).
- Installed relaunch to backend readiness: 9.083 seconds; document load: 13.846 seconds.
- Installed operations/status: 41.3 ms; risk grid: 66.0 ms; blocked route attempt: 24.4 ms. Single observations, not percentile benchmarks.
- Installed historical model inference endpoint: 2.248 seconds, including response serialization.
- Approximate installed working set after validation: 1,264,177,152 bytes across desktop plus WebView children; includes shared pages and is not private memory.
- Installer: 1,051,479,914 bytes. Installed application including uninstaller: 1,621,712,026 bytes.

## Warnings and limitations

The former 16 pytest warnings became 14: one Starlette/httpx deprecation, twelve
xarray/netCDF4 NumPy shape deprecations, and one pytest cache permission warning.
FastAPI startup deprecation was removed via lifespan without changing scientific logic.
PyInstaller reported optional tensorboard/CUDA/distributed deprecations, optional parser
and scipy imports, and a Linux libgomp reference. pyproj's alternate data-path warning
is covered by explicit bundled proj_dir and successful packaged routing/inference.
NetCDF blosc optional zlib/snappy dependencies remain advisory for unexercised codecs;
all bundled NetCDF observation, historical forcing and inference paths passed.
Inno's x64 alias deprecation is benign; installer built, installed and uninstalled.
The Vite chunk advisory is retained to avoid a late product refactor.

Native Computer Use helper was unavailable. Native window metadata, application logs and
WebView CDP validated the actual desktop. WebView screenshot capture stalled, so native
UI conclusions use DOM controls and successful API requests, not an invented screenshot.
The first empty-home installed launch had no CDP listener despite successful native load;
normal-profile relaunch exposed CDP. This is not a clean-machine/VM test.
A readiness JSON is a last-start diagnostic, not proof that the app is still running.

All former MUST FIX items have explicit dispositions in
`docs/research/technical-debt-before-release.md`. Scientific models were not retrained;
routing, risk and replanning semantics were not changed.

Evidence is retained locally under `artifacts/` (build/install/uninstall logs, API JSON,
process snapshots, file audit, smoke logs) and LocalAppData/POLARIS-AI/logs.
Checksums and runtime source identity are in `release/release-manifest.json` and
`release/checksums.txt`. Large binaries remain ignored by Git.

## Changed files

- `README.md`
- `RELEASE_NOTES_1.0.0-rc1.md`
- `artifacts/browser-smoke.mjs`
- `backend/app/core/logging.py`
- `backend/app/main.py`
- `desktop/build_windows.ps1`
- `desktop/installer/POLARIS-AI.iss`
- `desktop/launcher.py`
- `desktop/release_validation.py`
- `docs/release/FINAL_TEST_REPORT.md`
- `docs/release/OPERATOR_QUICKSTART.md`
- `docs/release/POLARIS_FINAL_ARCHITECTURE.md`
- `docs/release/RELEASE_CHECKLIST.md`
- `docs/release/WINDOWS_DEPLOYMENT.md`
- `docs/research/technical-debt-before-release.md`
- `frontend/src/services/connectivityApi.js`
- `frontend/src/services/historicalTransitApi.js`
- `frontend/src/services/icebergApi.js`
- `frontend/src/services/modelApi.js`
- `frontend/src/services/operationsApi.js`
- `frontend/src/services/replanningApi.js`
- `frontend/src/services/riskApi.js`
- `frontend/src/services/routesApi.js`
- `frontend/src/services/seaIceApi.js`
- `release/checksums.txt`
- `release/release-manifest.json`
- `tests/browser_historical_transit.mjs`
- `tests/test_desktop_release.py`
