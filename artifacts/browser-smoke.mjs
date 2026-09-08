import { writeFile } from "node:fs/promises";

const pages = await (await fetch("http://127.0.0.1:9223/json/list")).json();
const page = pages.find((item) => item.type === "page");
if (!page) throw new Error("No Chrome page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve) => ws.addEventListener("open", resolve, { once: true }));
let id = 0;
const pending = new Map();
const errors = [];
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const requestId = ++id;
  const timer = setTimeout(() => reject(new Error(`CDP timeout ${method}`)), 15000);
  pending.set(requestId, {
    resolve: (value) => { clearTimeout(timer); resolve(value); },
    reject: (error) => { clearTimeout(timer); reject(error); },
  });
  ws.send(JSON.stringify({ id: requestId, method, params }));
});
ws.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const request = pending.get(message.id);
    pending.delete(message.id);
    message.error ? request.reject(message.error) : request.resolve(message.result);
  }
  if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails);
});
const evaluate = async (expression) => {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
};
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const waitFor = async (expression) => {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (await evaluate(expression)) return;
    await delay(500);
  }
  throw new Error(`Timeout: ${expression}`);
};
const clickButton = async (label) => {
  const clicked = await evaluate(`(() => {
    const target = [...document.querySelectorAll('button')].find((button) =>
      button.offsetParent !== null && button.textContent.trim().includes(${JSON.stringify(label)})
    );
    if (!target) return false;
    target.click();
    return true;
  })()`);
  if (!clicked) throw new Error(`Visible button not found: ${label}`);
};

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: process.env.POLARIS_SMOKE_URL || "http://127.0.0.1:5173" });
await waitFor("document.body.innerText.includes('Antarctic Operating Picture') && !!document.querySelector('.antarctic-map')");
await waitFor("document.body.innerText.includes('Operational Status') && document.body.innerText.includes('Connection')");
console.log("PASS Mission Control map, Operational Status, and Connectivity");

await clickButton("Ice Intelligence");
await waitFor("document.body.innerText.includes('Ice Intelligence') && !document.body.innerText.includes('Antarctic Operating Picture')");
console.log("PASS Ice Intelligence");

await clickButton("Navigation");
await waitFor("document.body.innerText.includes('Time-Dependent Antarctic Route Planning') && document.body.innerText.includes('ROUTING ENGINE AVAILABLE')");
const navigationControls = await evaluate("(() => { const planner = document.querySelector('[aria-label=\"Route Planner\"]'); return !!planner && !!planner.querySelector('select') && planner.querySelectorAll('fieldset').length >= 2 && [...planner.querySelectorAll('button')].some(button => button.textContent.includes('PLAN ROUTES')) && document.body.innerText.includes('SAFE · FAST · ECO · BALANCED') && document.body.innerText.includes('CHECK FOR SAFER ROUTE'); })()");
if (!navigationControls) throw new Error("Navigation workspace controls not rendered");
if (await evaluate("document.body.innerText.includes('IMPLEMENTATION PENDING') || document.body.innerText.includes('NOT YET AVAILABLE') || document.body.innerText.includes('PENDING')")) throw new Error("Obsolete Navigation placeholder text remains");
console.log("PASS Navigation workspace, route planner, alternatives, active-route, and replanning controls");

await clickButton("Sea-Ice Forecast");
await waitFor("document.body.innerText.includes('Sea-Ice Forecast') && !!document.querySelector('.antarctic-map')");
for (const horizon of [24, 48, 72]) {
  const label = `+${horizon}H`;
  await clickButton(label);
  await waitFor(`(() => [...document.querySelectorAll('button')].some((button) => button.textContent.trim() === ${JSON.stringify(label)} && button.getAttribute('aria-pressed') === 'true'))()`);
}
console.log("PASS Sea-Ice Forecast +24H/+48H/+72H controls");

await clickButton("Mission Control");
await waitFor("document.body.innerText.includes('Regional Route Planning') && document.body.innerText.includes('Dynamic Risk Engine')");
const riskControls = await evaluate("!!document.querySelector('select[aria-label=\"Risk vessel profile\"]') && !!document.querySelector('[aria-label=\"Risk forecast horizon\"]')");
if (!riskControls) throw new Error("Dynamic Risk controls not rendered");
console.log("PASS Dynamic Risk and route-planning controls");

if (errors.length) throw new Error(`Fatal JavaScript exceptions: ${JSON.stringify(errors)}`);
await writeFile("artifacts/browser-smoke-results.json", JSON.stringify({ errors, checks: ["mission-control", "operations-status", "connectivity", "ice-intelligence", "navigation-workspace", "route-planner", "route-alternatives", "active-route", "replanning", "sea-ice-forecast", "+24H", "+48H", "+72H", "dynamic-risk"] }, null, 2));
ws.close();
