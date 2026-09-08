# Checkpoint 9 performance

Performance is measured locally with `scripts/benchmark_polaris.py`, using repeated warm calls and reporting minimum, median, p95, and maximum milliseconds. Results depend on the host, data cache, and current environment state; they are engineering measurements rather than SLAs. The script records operating system, Python version, and CPU string and reports operations status, risk-grid generation, and each route objective separately.

Run the benchmark from the repository virtual environment before a demonstration. A blocked or stale local field may cause route timings to represent failure-path handling rather than successful route search; report that condition alongside the numbers.

Measured 2026-09-08 on Windows 11, Python 3.13.15, Intel Family 6 Model 140 CPU, three iterations: warm risk grid median 16.59 ms (p95 16.59 ms); operations status median 110.54 ms (p95 110.54 ms, one cold maximum 5325.69 ms); SAFE/FAST/ECO/BALANCED route attempts median 17.89/15.51/17.75/15.70 ms. The current local environmental field was blocked, so all route attempts returned `ORIGIN_BLOCKED`; these are failure-path timings, not successful-route performance claims.
