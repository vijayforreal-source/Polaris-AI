import { useEffect, useState } from "react";
import { fetchRiskGrid, fetchRiskStatus, fetchRiskVessels, fetchPointRisk } from "../../services/riskApi.js";

export function useDynamicRisk() {
  const [enabled, setEnabled] = useState(false);
  const [horizon, setHorizon] = useState(0);
  const [vessel, setVessel] = useState("simulated-research");
  const [vessels, setVessels] = useState([]);
  const [status, setStatus] = useState(null);
  const [field, setField] = useState(null);
  const [location, setLocation] = useState(null);
  const [point, setPoint] = useState(null);
  const [error, setError] = useState("");
  const [pointError, setPointError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchRiskStatus(controller.signal), fetchRiskVessels(controller.signal)])
      .then(([s, v]) => { setStatus(s); setVessels(v.vessels); })
      .catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setField(null); setPoint(null); setLocation(null); setError("");
    if (enabled) fetchRiskGrid(horizon, vessel, controller.signal).then(setField)
      .catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [enabled, horizon, vessel]);
  useEffect(() => {
    const controller = new AbortController();
    setPoint(null); setPointError("");
    if (enabled && field && location) fetchPointRisk(location, field.metadata.horizon_hours, field.metadata.vessel.vessel_id, controller.signal)
      .then(setPoint).catch(e => { if (e.name !== "AbortError") setPointError(e.message); });
    return () => controller.abort();
  }, [enabled, field, location]);
  return { enabled, setEnabled, horizon, setHorizon, vessel, setVessel, vessels, status, field,
    location, setLocation, point, error, pointError };
}

export const RISK_COLORS = ["#58c397", "#a6c86a", "#e9ca65", "#e99150", "#db5965"];
export function DynamicRiskLegend() {
  return <section className="map-legend risk-legend" aria-label="Dynamic risk legend"><div className="legend-title">DYNAMIC RISK / ENGINEERING SCORE</div>{["LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL"].map((name,index) => <span className="risk-key" key={name}><i style={{background:RISK_COLORS[index]}} />{name}</span>)}<small>Blocked cells are no-go. Dark cells: land / invalid ocean mask.</small></section>;
}

export default function DynamicRiskPanel({ risk }) {
  const { enabled, setEnabled, horizon, setHorizon, vessel, setVessel, vessels, status, field, point, location, error, pointError } = risk;
  const states = field?.metadata.component_states ?? status?.component_states;
  return <section className="rail-section dynamic-risk-panel">
    <span className="panel-kicker">CHECKPOINT 4 / ENGINEERING ASSESSMENT</span><h3>Dynamic Risk Engine</h3>
    <label className="transit-toggle"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Dynamic Risk</label>
    <label className="risk-vessel-label">Vessel profile<select aria-label="Risk vessel profile" value={vessel} onChange={e => setVessel(e.target.value)}>{vessels.map(v => <option key={v.vessel_id} value={v.vessel_id}>{v.name}</option>)}</select></label>
    <div className="risk-horizons" aria-label="Risk forecast horizon">{[0,24,48,72].map(h => <button type="button" key={h} aria-pressed={horizon === h} onClick={() => setHorizon(h)}>{h ? `+${h}H` : "NOW"}</button>)}</div>
    {[["Sea ice", states?.sea_ice], ["Icebergs", states?.icebergs], ["Historical transit", states?.historical_transit],
      ["Vessel profile", field?.metadata.vessel.classification ?? vessels.find(v => v.vessel_id === vessel)?.classification],
      ["Overall", field?.metadata.state ?? status?.state]].map(([name,value]) => <div className="forecast-detail" key={name}><span>{name}</span><strong>{value ?? "LOADING"}</strong></div>)}
    {error && <p role="alert">{error}</p>}
    {enabled && !field && !error && <p role="status">Loading risk field...</p>}
    {enabled && field && <><p>Initialization: {field.metadata.initialization_time}<br />Valid time: {field.metadata.valid_time}</p><p>Horizon is relative to the displayed initialization, not necessarily today.</p><p>{field.summary.blocked_cell_count} / {field.summary.cell_count} cells blocked.</p><p>Click the risk map for the nearest cell explanation.</p></>}
    {pointError && <p role="alert">{pointError}</p>}
    {enabled && location && !point && !pointError && <p role="status">Loading point explanation...</p>}
    {enabled && point && <section className="risk-point" aria-label="Risk point explanation"><h4>Point Risk Explanation</h4>
      {[["Risk score",point.risk_score.toFixed(3)], ["Category",point.risk_category], ["Navigable",point.navigable ? "YES (screening only)" : "NO"],
        ["Horizon",`${point.metadata.horizon_hours}H`], ["Vessel",point.metadata.vessel.name], ["Dominant factor",point.dominant_factor],
        ["Navigation cost",point.navigation_cost == null ? "BLOCKED" : point.navigation_cost.toFixed(3)],
        ["SIC age",`${point.metadata.sea_ice_age_days.toFixed(1)} days`], ["Iceberg report age",`${point.metadata.iceberg_report_age_days.toFixed(1)} days`]]
        .map(([name,value]) => <div className="forecast-detail" key={name}><span>{name}</span><strong>{value}</strong></div>)}
      {Object.entries(point.components).map(([name,value]) => <div className="forecast-detail" key={name}><span>{name.replaceAll("_"," ")}</span><strong>{value.toFixed(3)}</strong></div>)}
      {point.explanations.map(line => <p key={line}>{line}</p>)}
    </section>}
    <p className="transit-disclaimer">Risk score is decision-support output, not certified navigational safety probability.</p>
    <small>Engineering defaults. Historical experience never lowers safety risk. No bathymetry or route generation.</small>
  </section>;
}
