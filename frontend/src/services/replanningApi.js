const API_BASE_URL = window.POLARIS_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}/api/replanning/${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `Replanning API returned HTTP ${response.status}.`);
  return payload;
}
export const activateRoute = (voyageId, route) => request("activate", { method: "POST", body: JSON.stringify({ voyage_id: voyageId, route }) });
export const fetchActiveVoyage = () => request("active");
export const replanRoute = () => request("replan", { method: "POST" });
export const updatePosition = (latitude, longitude, currentTime) => request("position", { method: "POST", body: JSON.stringify({ latitude, longitude, current_time: currentTime }) });
