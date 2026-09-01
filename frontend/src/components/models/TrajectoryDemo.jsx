import { useEffect, useMemo, useState } from "react";
import { fetchIcebergHistory } from "../../services/icebergApi.js";
import { requestTrajectoryHindcast } from "../../services/modelApi.js";
import TrajectoryMap from "./TrajectoryMap.jsx";

const HORIZONS = [6, 12, 24, 48, 72];
const MODELS = [
  ["P2_SURFACE_CURRENT", "P2 Surface Current / Production Candidate"],
  ["WDE17_SURFACE", "WDE17 Surface / Reference"],
  ["H0_EFFECTIVE_CURRENT_HYBRID", "H0 Effective Current / Experimental"],
  ["H1_HYBRID_WDE17_STYLE", "H1 WDE17-Style Hybrid / Experimental"],
];

export default function TrajectoryDemo() {
  const [history, setHistory] = useState(null);
  const [startDate, setStartDate] = useState("2026-08-13");
  const [model, setModel] = useState("P2_SURFACE_CURRENT");
  const [horizon, setHorizon] = useState(24);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetchIcebergHistory("A76C", controller.signal).then(setHistory).catch((requestError) => {
      if (requestError.name !== "AbortError") setError(requestError.message);
    });
    return () => controller.abort();
  }, []);

  const startPoint = useMemo(() => history?.track_points?.find((point) => point.observation_date === startDate), [history, startDate]);
  useEffect(() => {
    if (!startPoint) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    requestTrajectoryHindcast({ iceberg_id: "A76C", initial_latitude: startPoint.latitude, initial_longitude: startPoint.longitude, initial_time: `${startDate}T00:00:00Z`, prediction_horizon_hours: horizon, model }, controller.signal).then((response) => {
      if (!controller.signal.aborted) { setResult(response); setLoading(false); }
    }).catch((requestError) => {
      if (requestError.name !== "AbortError" && !controller.signal.aborted) { setError(requestError.message); setResult(null); setLoading(false); }
    });
    return () => controller.abort();
  }, [startPoint, startDate, horizon, model]);

  const dates = history?.track_points?.map((point) => point.observation_date) ?? [];
  return <section className="module-panel trajectory-demo"><div className="section-heading"><div><span className="panel-kicker">A76C TRAJECTORY DEMO / HISTORICAL HINDCAST</span><h3>Reusable Trajectory Engine</h3></div><span className="data-chip active">MODEL_PREDICTION</span></div><div className="trajectory-controls"><label>START DATE<select value={startDate} onChange={(event) => setStartDate(event.target.value)}>{dates.map((date) => <option key={date} value={date}>{date}</option>)}</select></label><label>MODEL<select value={model} onChange={(event) => setModel(event.target.value)}>{MODELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><div className="trajectory-timeline" aria-label="Historical trajectory horizon">{HORIZONS.map((value) => <button type="button" className={horizon === value ? "active" : ""} key={value} onClick={() => setHorizon(value)}>+{value}H</button>)}</div>{loading && <div className="trajectory-status">Computing from verified historical forcing...</div>}{error && <div className="trajectory-status error">VERIFIED TRAJECTORY API UNAVAILABLE / {error}</div>}{!loading && result && <><div className={`trajectory-status ${result.availability_status === "AVAILABLE" ? "available" : "error"}`}>{result.availability_status.replaceAll("_", " ")}</div><div className="trajectory-map-frame"><TrajectoryMap result={result} /><div className="trajectory-map-label">A76C / {result.mode}<br />{result.model_status.replaceAll("_", " ")}</div></div><div className="trajectory-summary"><div><span>START</span><strong>{result.start_position.latitude.toFixed(4)}, {result.start_position.longitude.toFixed(4)}</strong></div><div><span>PREDICTED ENDPOINT</span><strong>{result.endpoint ? `${result.endpoint.latitude.toFixed(4)}, ${result.endpoint.longitude.toFixed(4)}` : "UNAVAILABLE"}</strong></div><div><span>HORIZON</span><strong>{result.actual_horizon_hours.toFixed(0)} / {result.requested_horizon_hours} H</strong></div><div><span>UNCERTAINTY</span><strong>{result.uncertainty.applicable ? `50% ${result.uncertainty.radius_50_km.toFixed(1)} km` : "NOT APPLICABLE"}</strong></div></div>{result.actual_historical_observation ? <p className="trajectory-observation">ACTUAL HISTORICAL OBSERVATION / endpoint error {result.actual_historical_observation.endpoint_error_km.toFixed(3)} km</p> : <p className="processing-note">No USNIC observation exists at this exact selected horizon; no actual endpoint is invented.</p>}</>}</section>;
}
