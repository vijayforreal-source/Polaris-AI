const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Verified sea-ice API returned HTTP ${response.status}.`);
  return response.json();
}

export async function fetchLatestSeaIce(signal) {
  const [metadata, grid] = await Promise.all([
    getJson("/api/sea-ice/latest/metadata", signal),
    getJson("/api/sea-ice/latest/grid", signal),
  ]);
  return { metadata, grid };
}
