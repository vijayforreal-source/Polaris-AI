# POLARIS-AI reproducibility report

The scientific core remains frozen at Sea-Ice Multimodal Bounded Residual CNN v0.3. Locked validation metrics are +24H MAE 2.877915 pp, +48H MAE 4.066660 pp, +72H MAE 4.788987 pp, mean 3.911187 pp. No retraining or metric changes were made in Checkpoint 9.

The reproducible local stack uses Python 3.11–3.13, FastAPI, NumPy, SciPy, PyTorch, xarray, pyproj, React, and Vite. Environment fingerprints include source artifacts and configuration. Routing uses the Checkpoint 5 time-dependent Dijkstra planner; replanning uses Checkpoint 6 engineering thresholds; offline policy uses Checkpoint 8 priority rules.

The current regional domain is Bharati / Prydz Bay with a validated forecast horizon of +72H. Local tests, synthetic demo scenarios, and benchmark scripts are explicitly separated from production scientific stores. The latest checkpoint commit is recorded in Git; run `git rev-parse HEAD`, `python scripts/validate_full_system.py`, and `python scripts/benchmark_polaris.py` to reproduce the current operational report.
