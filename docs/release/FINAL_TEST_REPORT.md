# Final test report

| Gate | Result |
|---|---|
| Python suite | 166 passed, 16 warnings |
| Ruff | Passed |
| Frontend production build | Passed; 676 KB JavaScript bundle with existing Vite advisory |
| Main browser smoke | Passed |
| Historical transit browser smoke | Passed |
| Champion model load/inference | Passed in source environment after v0.3 loader fix; output shape `(1, 3, H, W)` |
| Desktop shell build | PyInstaller folder bundle built successfully; packaged `--headless` startup passed model verification, backend health handshake, static frontend startup, and clean shutdown |
| Installer/install/uninstall | Pending Windows execution |
| Packaged offline smoke | Pending Windows execution |

The 16 pytest warnings are dependency/deprecation warnings from Starlette/httpx, FastAPI startup events, NumPy/xarray, and pytest cache permissions. They are documented and do not change scientific output. The remaining release blocker is execution of the Windows-specific packaged application and installer on a Windows validation host.
