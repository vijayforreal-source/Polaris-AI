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

The folder bundle is written under `release\windows\dist`; the installer is `release\windows\installer\POLARIS-AI-Setup-1.0.0-rc1.exe`. Build outputs are intentionally ignored by Git because the PyTorch and NetCDF resources are large.

The installed app owns backend startup and shutdown. It chooses an available loopback port, polls `/health`, and writes diagnostics to `%LOCALAPPDATA%\POLARIS-AI\logs`. A clean-machine verification should be performed outside the repository, including a path with spaces. The installer is unsigned in this release candidate; Windows SmartScreen may show an unsigned-build warning.

Upgrades install into the same application directory while preserving `%LOCALAPPDATA%\POLARIS-AI` mission state, cache, and logs. Uninstall removes program files and shortcuts; operator data is preserved for review.
