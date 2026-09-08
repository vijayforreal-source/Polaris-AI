const API_BASE_URL = window.POLARIS_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Verified sea-ice API returned HTTP ${response.status}.`);
  return response.json();
}

export const fetchForecastStatus = (signal) => getJson("/api/sea-ice/forecast/status", signal);
export const fetchForecastResults = (signal) => getJson("/api/sea-ice/forecast/results", signal);
export const fetchForecast = (date, signal) => getJson(date ? `/api/sea-ice/forecast/historical?date=${encodeURIComponent(date)}` : "/api/sea-ice/forecast/latest", signal);

export async function fetchLatestSeaIce(signal) {
  const [metadata, grid] = await Promise.all([
    getJson("/api/sea-ice/latest/metadata", signal),
    getJson("/api/sea-ice/latest/grid", signal),
  ]);
  return { metadata, grid };
}
