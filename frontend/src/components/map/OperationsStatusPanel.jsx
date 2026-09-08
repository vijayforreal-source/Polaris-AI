import { useEffect, useState } from "react";
import { fetchOperationsStatus } from "../../services/operationsApi.js";

export default function OperationsStatusPanel() {
  const [data, setData] = useState(null); const [error, setError] = useState("");
  useEffect(() => { const controller = new AbortController(); fetchOperationsStatus(controller.signal).then(setData).catch(e => { if (e.name !== "AbortError") setError(e.message); }); return () => controller.abort(); }, []);
  const sources = data?.data_source_statuses ?? [];
  return <section className="rail-section operations-status" aria-label="Operational Status"><span className="panel-kicker">CHECKPOINT 7 / OPERATIONS</span><h3>POLARIS Operational Status</h3>{error && <p role="alert">{error}</p>}{data && <><strong className={`operation-state state-${data.overall_status?.toLowerCase()}`}>{data.overall_status}</strong><div className="operation-sources">{sources.map(source => <div className="forecast-detail" key={source.source_id}><span>{source.name}</span><strong>{source.status} · {source.freshness_state}</strong><small>{source.classification}</small></div>)}</div><div className="operation-capabilities">{Object.entries(data.capabilities ?? {}).slice(2, 8).map(([name, value]) => <div className="forecast-detail" key={name}><span>{name.replaceAll("_", " ")}</span><strong>{value.status}</strong></div>)}</div>{data.warnings?.length > 0 && <p>Warnings: {data.warnings.join(", ")}</p>}</>}</section>;
}
