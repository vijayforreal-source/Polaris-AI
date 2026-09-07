import { useEffect, useState } from "react";
import { fetchForecastStatus } from "../../services/seaIceApi.js";

export default function ForecastStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchForecastStatus(controller.signal).then(setStatus).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, []);
  const label = status?.mode === "MODEL_PREDICTION" ? "MODEL PREDICTION" : status?.mode === "PERSISTENCE" ? "PERSISTENCE FALLBACK" : "UNAVAILABLE";
  return <section className="rail-section"><h3>Sea-Ice Forecast</h3><p>{status?.champion?.model_version} · {label}</p><p>{status?.initialization_time}</p><div className="forecast-detail"><span>NOW</span><strong>OBSERVATION</strong></div>{[24,48,72].map(h => <div key={h} className="forecast-detail"><span>+{h}H</span><strong>{label}</strong></div>)}<p>{error || status?.fallback_reason}</p><p>Open Sea-Ice Forecast for maps and historical comparisons.</p></section>;
}
