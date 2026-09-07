const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
async function get(path, signal) {
  const response = await fetch(`${API_BASE_URL}/api/risk/${path}`, { signal });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === "string" ? payload.detail : payload.detail?.reason ?? `Risk API returned HTTP ${response.status}.`);
  }
  return response.json();
}
export const fetchRiskStatus = signal => get("status", signal);
export const fetchRiskVessels = signal => get("vessels", signal);
export const fetchRiskGrid = (horizon, vessel, signal) => get(`grid?horizon_hours=${horizon}&vessel_id=${encodeURIComponent(vessel)}`, signal);
export const fetchPointRisk = (location, horizon, vessel, signal) => get(`point?lat=${location.latitude}&lon=${location.longitude}&horizon_hours=${horizon}&vessel_id=${encodeURIComponent(vessel)}`, signal);
