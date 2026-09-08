# POLARIS-AI final architecture

POLARIS-AI 1.0.0-rc1 is a local Windows desktop shell around the existing React production build and FastAPI scientific services. The selected shell is PyWebView with a folder-based PyInstaller backend/runtime bundle. This is more reliable for PyTorch, NetCDF, pyproj, and offline assets than a single-file extraction bundle, while avoiding an Electron/Node runtime in the installed application.

```text
External data adapters
        ↓
Ship network / optional connectivity
        ↓
POLARIS sync and local cache
        ↓
Sea-ice observation and forecast
        ↓
Iceberg + historical transit intelligence
        ↓
Vessel-aware dynamic risk
        ↓
Time-dependent SAFE / FAST / ECO / BALANCED routing
        ↓
Captain-controlled active route and replanning
        ↓
Mission Control
```

Future GNSS/AIS adapters feed a telemetry boundary before entering the same risk and route services. The desktop shell binds the backend to `127.0.0.1`, waits for `/health`, then opens the local production frontend. Logs, readiness and WebView browser storage live under `%LOCALAPPDATA%\POLARIS-AI`; bundled models, configs, data, and frontend assets are read-only resources.

The scientific champion is POLARIS Sea-Ice Multimodal Bounded Residual CNN v0.3. Its validated horizon is 72 hours in the Bharati / Prydz Bay regional prototype. Outputs are advisory decision support and do not replace certified navigation systems or the ship's master.

The frozen backend runs in an owned thread, with bounded shutdown waiting. A Windows
local-session mutex prevents duplicate desktops. The launcher injects the selected API
port into the served HTML and configures its frontend origin for CORS. Model verification
checks the frozen v0.3 SHA-256 before loading and safe inference. Mission, active-route,
event and sync state are in memory for this research RC and do not survive restart.
