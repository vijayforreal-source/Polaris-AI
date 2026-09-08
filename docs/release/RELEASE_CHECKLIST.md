# Release checklist

| Gate | Status |
|---|---|
| Repository audit | PASS |
| Scientific core frozen | PASS |
| Desktop architecture documented | PASS |
| Frontend production build | PASS |
| Backend launcher and health handshake | PASS in source/headless design; Windows bundle pending |
| Model v0.3 verification | PASS in source environment |
| AppData/log path design | PASS |
| PyInstaller bundle | PENDING Windows build |
| Installer | PENDING Inno Setup build |
| Clean-machine install | PENDING Windows host |
| Packaged offline start | PENDING Windows host |
| Packaged shutdown/orphan check | PENDING Windows host |
| Secret scan | PASS for source release staging; generated bundle not built |
| Absolute developer-path scan | REVIEWED; relative resource resolution used by launcher |
| Pytest / Ruff / frontend | PASS |
| Browser smoke tests | PASS |
| Release docs | PASS |
| Release tag | BLOCKED until packaged Windows validation |
