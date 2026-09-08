# Release checklist

| Gate | Result |
|---|---|
| Source ancestry and clean build input | PASS |
| Frozen scientific model and packaged inference | PASS |
| Fresh PyInstaller / native window / Navigation | PASS |
| Packaged APIs and isolated DEMO routing/replanning | PASS |
| Single instance and eventual process cleanup | PASS; installed exit exceeded first 15-second probe |
| Inno installer / per-user path with spaces | PASS |
| Installed startup independent of development environment | PASS |
| Installed native UI and browser smokes | PASS |
| Controlled application offline and reconnect | PASS; no physical disconnect claimed |
| AppData / no install-directory writes | PASS; operational state remains session-only |
| Uninstall and AppData preservation | PASS |
| Source / staging / installer-input security review | PASS |
| 167 tests / Ruff / production build | PASS |
| Must-fix debt dispositions | Documented; research RC scope explicit |
| Checksums and release metadata | Written |
| Release tag | Created only after final commit and clean-tree verification |

See FINAL_TEST_REPORT.md for actual measurements, limitations and warning classifications.
