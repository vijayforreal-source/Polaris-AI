import { useEffect, useState } from "react";
import AntarcticMap from "../components/map/AntarcticMap.jsx";
import MapLegend from "../components/map/MapLegend.jsx";
import { fetchForecast, fetchForecastResults, fetchForecastStatus } from "../services/seaIceApi.js";

export default function SeaIceForecast() {
  const [product, setProduct] = useState(null);
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [date, setDate] = useState("");
  const [requestedDate, setRequestedDate] = useState("");
  const [horizon, setHorizon] = useState(24);
  const [layer, setLayer] = useState("prediction");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchForecastStatus(controller.signal).then(setStatus).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    fetchForecastResults(controller.signal).then(setResults).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setProduct(null); setError("");
    fetchForecast(requestedDate, controller.signal).then(setProduct).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [requestedDate]);
  const selected = product?.forecasts?.find(f => f.horizon_hours === horizon);
  const grid = horizon === 0 ? product?.observation : layer === "observation" ? selected?.observed_target : layer === "persistence" ? selected?.persistence : selected?.grid;
  const label = !product ? "LOADING" : product.mode === "UNAVAILABLE" ? "UNAVAILABLE" : horizon === 0 || layer === "observation" ? "OBSERVATION" : layer === "persistence" ? "PERSISTENCE MODEL" : product?.fallback_used ? "PERSISTENCE FALLBACK" : "MODEL PREDICTION";
  return <><section className="mission-workspace forecast-workspace"><div className="workspace-header"><div><span className="workspace-kicker">CHECKPOINT 3 / SCIENTIFIC FORECAST</span><h2>Sea-Ice Forecast</h2></div><span className="data-chip active">{product?.classification ?? "LOADING"}</span></div>
    <form className="forecast-controls" onSubmit={e => { e.preventDefault(); setRequestedDate(date); }}><label>Historical initialization <input type="date" value={date} min={status?.historical_dates?.minimum} max={status?.historical_dates?.maximum} onChange={e => setDate(e.target.value)} required /></label><button type="submit">View historical forecast</button><button type="button" onClick={() => { setRequestedDate(""); setDate(""); setLayer("prediction"); }}>Latest available</button></form>
    <div className="forecast-controls">{[0,24,48,72].map(h => <button aria-pressed={horizon === h} className={horizon === h ? "active" : ""} key={h} onClick={() => setHorizon(h)}>{h ? `+${h}H` : "NOW / OBSERVATION"}</button>)}<select aria-label="Displayed field" value={layer} onChange={e => setLayer(e.target.value)} disabled={horizon === 0}><option value="prediction">Prediction / fallback</option><option value="persistence">Persistence comparison</option>{requestedDate && <option value="observation">Observed target</option>}</select></div>
    <div className="map-frame">{grid && product ? <AntarcticMap metadata={product.map_metadata} grid={grid} /> : <div className="map-state" role="status">{error || product?.fallback_reason || (product ? "Observed target unavailable for this date." : "Loading forecast…")}</div>}{grid && <MapLegend />}<div className="map-attribution">{label} · {horizon === 0 ? product?.initialization_time : selected?.forecast_valid_time}<br />Sea ice: Copernicus Marine / OSI-SAF · Forcing: {product?.forcing_source ?? "not used"}</div></div>
    <p className="forecast-notice">Decision-support research system. Not an autonomous ship-navigation authority. ERA5 reanalysis is not an operational future weather forecast.</p></section>
    <aside className="intelligence-rail"><section className="rail-section"><h3>Model status</h3>{[["Selected champion", product?.champion?.model_name ?? status?.champion?.model_name],["Actual model",product?.model_name],["Prediction mode",product?.mode],["Initialization",product?.initialization_time],["Valid time",horizon === 0 ? product?.initialization_time : selected?.forecast_valid_time],["Data freshness",`${product?.freshness ?? "—"} / age ${product?.age_days ?? "—"} days`],["Forcing",product?.forcing_classification ?? "Not used"],["Fallback",product?.fallback_reason ?? "None"],["Classification",label]].map(([k,v]) => <div className="forecast-detail" key={k}><span>{k}</span><strong>{v ?? "—"}</strong></div>)}</section>
    <section className="rail-section"><h3>Locked benchmark · MAE (pp)</h3><table className="forecast-table"><thead><tr><th>Horizon</th><th>v0.2</th><th>v0.3 ★</th><th>Persistence</th></tr></thead><tbody>{["24H","48H","72H"].map(k => <tr key={k}><td>{k}</td><td>{results?.comparison_v02?.[k]?.v02_mae_pp.toFixed(3) ?? "—"}</td><td><strong>{results?.horizons?.[k]?.ai.mae_percentage_points.toFixed(3) ?? "—"}</strong></td><td>{results?.horizons?.[k]?.persistence.mae_percentage_points.toFixed(3) ?? "—"}</td></tr>)}</tbody></table><p>584 matched initialization dates. ★ Selected historical champion.</p></section>
    <section className="rail-section"><h3>Scientific provenance</h3><p>{product?.provenance?.forcing_time_semantics}</p>{product?.warnings?.map(w => <p key={w}>{w}</p>)}</section></aside></>;
}
