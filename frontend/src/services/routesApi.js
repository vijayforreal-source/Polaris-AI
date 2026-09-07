const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export async function fetchRouteStatus(signal) {
  const response = await fetch(`${API_BASE_URL}/api/routes/status`, { signal });
  if (!response.ok) throw new Error(`Routing API returned HTTP ${response.status}.`);
  return response.json();
}
export async function planRoutes(request, signal) {
  const response = await fetch(`${API_BASE_URL}/api/routes/plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request), signal });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : payload.detail?.reason ?? `Routing API returned HTTP ${response.status}.`);
  return payload;
}
