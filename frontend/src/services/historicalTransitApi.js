const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE_URL}/api/historical-transit/${path}`, { signal });
  if (!response.ok) throw new Error(`Historical transit API returned HTTP ${response.status}.`);
  return response.json();
}

export const fetchTransitStatus = signal => getJson("status", signal);
export const fetchTransitVoyages = (offset, signal) => getJson(`voyages?offset=${offset}&limit=25`, signal);
export const fetchTransitVoyage = (id, signal) => getJson(`voyage/${encodeURIComponent(id)}`, signal);
