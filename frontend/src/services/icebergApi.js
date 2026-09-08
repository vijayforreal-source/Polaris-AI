const API_BASE_URL = window.POLARIS_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Verified USNIC API returned HTTP ${response.status}.`);
  return response.json();
}

export async function fetchLatestIcebergs(signal) {
  const [metadata, registry] = await Promise.all([
    getJson("/api/icebergs/latest/metadata", signal),
    getJson("/api/icebergs/latest", signal),
  ]);
  return { metadata, icebergs: registry.icebergs };
}

export async function fetchIcebergHistory(icebergId, signal) {
  return getJson(`/api/icebergs/${icebergId}/history`, signal);
}
