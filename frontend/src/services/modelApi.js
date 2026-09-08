const API_BASE_URL = window.POLARIS_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Verified model API returned HTTP ${response.status}.`);
  return response.json();
}

export async function fetchModelEvaluations(signal) {
  const [physics, hybrid] = await Promise.all([
    getJson("/api/icebergs/A76C/physics-evaluation", signal),
    getJson("/api/icebergs/A76C/hybrid-evaluation", signal),
  ]);
  return { physics, hybrid };
}

export async function fetchHybridHindcast(signal) {
  return getJson("/api/icebergs/A76C/hybrid-hindcast/2026-08-27", signal);
}

export async function requestTrajectoryHindcast(request, signal) {
  const response = await fetch(`${API_BASE_URL}/api/trajectory/hindcast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) throw new Error(`Trajectory engine returned HTTP ${response.status}.`);
  return response.json();
}
