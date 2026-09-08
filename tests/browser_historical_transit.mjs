// Optional browser smoke test. Requires Vite :5173, FastAPI :8000 and isolated Chrome CDP :9223.
// All synthetic responses below exist only in this test's browser session.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";

const pages = await (await fetch("http://127.0.0.1:9223/json/list")).json();
const page = pages.find(p => p.type === "page");
assert(page, "Start isolated headless Chrome with --remote-debugging-port=9223");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener("open", resolve, { once: true }));
let id = 0;
const pending = new Map();
const errors = [];
let mock = false;
const interceptedRequests = [];
const fixture = {
  voyage_id: "BROWSER_TEST_ONLY", vessel_name: "Synthetic browser test vessel", expedition_id: "TEST",
  origin: "Test origin", destination: "Test destination", source: "Synthetic fixture - tests only",
  source_reference: "tests/browser_historical_transit.mjs", source_verified: true, verified_by: "Test fixture",
  source_classification: "OBSERVATION", track_quality: "USABLE_WITH_GAPS", renderable: true,
  start_time: "2025-01-01T00:00:00Z", end_time: "2025-01-02T03:00:00Z", last_transit_time: "2025-01-02T03:00:00Z",
  point_count: 4, distance_km: 230, duration_hours: 27, age_days: 613, quality_notes: ["Long gap excluded."],
  data_gaps: [{ after_point: 1, duration_hours: 21 }],
  points: [
    { timestamp_utc: "2025-01-01T00:00:00Z", latitude: -68, longitude: 75 },
    { timestamp_utc: "2025-01-01T03:00:00Z", latitude: -68, longitude: 77 },
    { timestamp_utc: "2025-01-02T00:00:00Z", latitude: -67, longitude: 79 },
    { timestamp_utc: "2025-01-02T03:00:00Z", latitude: -67, longitude: 81 },
  ],
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const n = ++id;
  const timer = setTimeout(() => { pending.delete(n); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
  pending.set(n, { resolve: v => { clearTimeout(timer); resolve(v); }, reject: e => { clearTimeout(timer); reject(e); } });
  ws.send(JSON.stringify({ id: n, method, params }));
});
ws.addEventListener("message", async e => {
  const message = JSON.parse(e.data);
  if (message.id && pending.has(message.id)) {
    const p = pending.get(message.id); pending.delete(message.id);
    message.error ? p.reject(message.error) : p.resolve(message.result);
  }
  if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails);
  if (message.method === "Fetch.requestPaused") {
    const { requestId, request } = message.params;
    if (!mock) { await send("Fetch.continueRequest", { requestId }); return; }
    interceptedRequests.push(request.url);
    const path = new URL(request.url).pathname;
    const payload = path.endsWith("/status") ? {
      available: true, voyage_count: 1, verified_voyage_count: 1, latest_transit: fixture.end_time,
      data_sources: [fixture.source], track_quality: { USABLE_WITH_GAPS: 1 }, load_errors: [],
    } : path.includes("/voyage/") ? fixture : { voyages: [fixture], total: 1, offset: 0, limit: 25 };
    await send("Fetch.fulfillRequest", { requestId, responseCode: 200,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }, { name: "Access-Control-Allow-Origin", value: "http://127.0.0.1:5173" }],
      body: Buffer.from(JSON.stringify(payload)).toString("base64") });
  }
});
const evaluate = async expression => {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
};
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const waitFor = async (expression, label = expression) => {
  for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await delay(300); }
  const diagnostics = await evaluate(`({
    visibleText: document.body.innerText.slice(-1800),
    voyageButtonCount: document.querySelectorAll('.transit-voyages button').length,
    transitEnabled: document.querySelector('.transit-toggle input')?.checked ?? null,
    loading: document.body.innerText.includes('Loading verified tracks...'),
  })`);
  throw new Error(`Browser timeout (${label}): ${JSON.stringify({ diagnostics, interceptedRequests })}`);
};
const click = text => evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.includes(${JSON.stringify(text)}))?.click()`);
const setTransitToggle = async checked => {
  const changed = await evaluate(`(() => { const panel = document.querySelector('.historical-transit-panel'); const fiberKey = Object.keys(panel ?? {}).find(key => key.startsWith('__reactFiber')); let fiber = fiberKey && panel[fiberKey]; while (fiber && fiber.elementType?.name !== 'MissionControl') fiber = fiber.return; const dispatch = fiber?.memoizedState?.queue?.dispatch; if (!dispatch) return false; dispatch(${checked}); return true; })()`);
  assert(changed, "Historical transit toggle is not rendered");
};
try {
  await send("Runtime.enable"); await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: "http://127.0.0.1:5173" });
  await waitFor("document.body.innerText.includes('No verified historical voyage tracks are currently loaded.') && !!document.querySelector('.antarctic-map')");
  await evaluate("document.querySelector('.transit-toggle input').click()");
  assert(await evaluate("document.querySelector('.transit-toggle input').checked"));
  assert.equal(await evaluate("document.querySelectorAll('.transit-voyages button').length"), 0);
  console.log("PASS real empty state and track toggle; no example tracks");
  await click("Sea-Ice Forecast");
  await waitFor("document.body.innerText.includes('STALE_OBSERVATION') && !!document.querySelector('.antarctic-map')");
  await click("+72H");
  assert(await evaluate("document.querySelector('button[aria-pressed=true]').textContent.includes('+72H')"));
  console.log("PASS existing forecast map and horizon selector");
  await click("Ice Intelligence"); await delay(1000);
  assert(await evaluate("document.body.innerText.includes('USNIC')"));
  console.log("PASS iceberg module");
  mock = true;
  await send("Fetch.enable", { patterns: [{ urlPattern: "*://127.0.0.1:8000/api/historical-transit/*" }] });
  await send("Page.navigate", { url: "http://127.0.0.1:5173" });
  await waitFor("document.body.innerText.includes('Synthetic fixture - tests only')");
  await setTransitToggle(true);
  await waitFor("!!document.querySelector('.transit-voyages button') && !document.body.innerText.includes('Loading verified tracks...')");
  const geometry = await evaluate(`(async()=>{const {createHistoricalTransitLayer}=await import('/src/components/map/HistoricalTransitLayer.js');const layer=createHistoricalTransitLayer([${JSON.stringify(fixture)}]);return layer.getSource().getFeatures()[0].getGeometry().getCoordinates().map(l=>l.length);})()`);
  assert.deepEqual(geometry, [2, 2], "Long gap must not be bridged");
  const rejected = await evaluate(`(async()=>{const {createHistoricalTransitLayer}=await import('/src/components/map/HistoricalTransitLayer.js');return createHistoricalTransitLayer([{...${JSON.stringify(fixture)},renderable:false}]).getSource().getFeatures().length;})()`);
  assert.equal(rejected, 0);
  await waitFor("!!document.querySelector('.antarctic-map .ol-viewport')", "historical map viewport");
  assert(await evaluate("document.querySelector('.antarctic-map .ol-viewport') !== null"), "Historical track map is not mounted");
  await evaluate("[...document.querySelectorAll('.transit-voyages button')].find(button => button.textContent.includes('Synthetic browser test vessel'))?.click()");
  await waitFor("document.body.innerText.includes('Used by 1 known voyage (this track).')");
  assert(await evaluate("document.body.innerText.includes('Last verified transit: 613 days ago')"));
  console.log("PASS rendered line click, metadata, gap splitting, rejected-track exclusion");
  await setTransitToggle(false);
  await delay(500);
  assert.equal(await evaluate("document.querySelectorAll('.transit-details').length"), 0);
  await send("Fetch.disable"); mock = false;
  await send("Page.navigate", { url: "http://127.0.0.1:5173" });
  await waitFor("document.body.innerText.includes('No verified historical voyage tracks are currently loaded.')");
  await mkdir("artifacts", { recursive: true });
  const shot = await send("Page.captureScreenshot", { format: "png" });
  await writeFile("artifacts/historical-transit-empty-state.png", Buffer.from(shot.data, "base64"));
  assert.deepEqual(errors, []);
  console.log("PASS zero JavaScript exceptions; production store remains empty");
} finally {
  await send("Fetch.disable").catch(() => {});
  ws.close();
}
