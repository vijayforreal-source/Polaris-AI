const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
async function get(path) { const response = await fetch(`${API_BASE_URL}/api/${path}`); if (!response.ok) throw new Error(`Connectivity API returned HTTP ${response.status}.`); return response.json(); }
export const fetchConnectivityStatus = () => get("connectivity/status");
export const fetchSyncStatus = () => get("sync/status");
export const fetchCacheStatus = () => get("cache/status");
