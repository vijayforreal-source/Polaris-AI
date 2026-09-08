# Windows deployment

## Build prerequisites

- Windows 10/11 x64
- Python 3.11–3.13 and the locked project environment
- Node.js/npm for the production frontend build
- PyInstaller and PyWebView from `desktop/requirements-windows.txt`
- Inno Setup 6 for the optional installer

## Build

```powershell
python -m pip install -e ".[dev]"
pip install -r desktop\requirements-windows.txt
.\desktop\build_windows.ps1 -Version 1.0.0-rc1
iscc desktop\installer\POLARIS-AI.iss
```

The folder bundle is written under `release\windows\rc1\dist`; the installer is `release\windows\installer\POLARIS-AI-Setup-1.0.0-rc1.exe`. Build outputs are intentionally ignored by Git because the PyTorch and NetCDF resources are large.

The installed app owns backend startup and shutdown. It chooses an available loopback port, polls `/health`, and writes diagnostics to `%LOCALAPPDATA%\POLARIS-AI\logs`. A clean-machine verification should be performed outside the repository, including a path with spaces. The installer is unsigned in this release candidate; Windows SmartScreen may show an unsigned-build warning.

The launcher uses a per-session Windows mutex and passes the chosen API port to the
production frontend. PyWebView uses `%LOCALAPPDATA%\POLARIS-AI\webview`; launcher logs
and readiness metadata also live under this application-data directory. Bundled local
scientific data are read-only resources. Mission, active-route, event, cache-index and sync
state are session-only in this research RC; restarting clears them. Durable operational
state is a requirement for a later operational release, not a capability claimed by RC1.

Inno supports `/CURRENTUSER /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` for an unelevated
per-user install, and `/DIR="<path with spaces>"` selects the target. The default all-user
installation uses Program Files and requires elevation. Uninstall removes application
files and shortcuts; `%LOCALAPPDATA%\POLARIS-AI` logs/readiness data are preserved.
The target Windows system requires a working WebView2 runtime.

`POLARIS_SMOKE_URL` selects a packaged frontend URL for both browser smoke scripts.
`POLARIS-AI.exe --validate-demo` executes isolated synthetic routing/replanning checks
and exits; it never starts a production server with synthetic risk data.
