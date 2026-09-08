# Operator quickstart

1. Launch **POLARIS-AI** from the Start Menu or desktop shortcut.
2. Wait for Mission Control to load. A degraded environment still opens when cached/local capabilities are usable.
3. Use Mission Control for the regional operating picture and Operational Status.
4. Use Navigation to choose a vessel, origin, destination, and `PLAN ROUTES`.
5. Compare SAFE, FAST, ECO, and BALANCED alternatives, then explicitly set an active route.
6. Use `CHECK FOR SAFER ROUTE` to evaluate replanning. Recommendations require captain acceptance.
7. Read Connectivity and cache status before relying on offline data.
8. Close the window normally; the local backend is terminated by the desktop shell.

POLARIS-AI is a research and operational decision-support prototype. Route and risk outputs are advisory and do not replace certified navigation systems, official ice services, vessel operating procedures, or the authority of the ship's master.

RC1 mission, active-route, event and sync state last only for the current session. Closing
and reopening starts a fresh session. Logs remain in `%LOCALAPPDATA%\POLARIS-AI\logs`.
A second launch exits while the first desktop instance is running.
