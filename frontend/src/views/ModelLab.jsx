import { useEffect, useState } from "react";
import { fetchHybridHindcast, fetchModelEvaluations } from "../services/modelApi.js";

const LABELS = {
  P0_PERSISTENCE: "Persistence",
  P1_CONSTANT_VELOCITY: "Constant Velocity",
  P2_SURFACE_CURRENT: "Surface Current",
  P3_WDE17_SURFACE: "WDE17 Surface",
  P2W_EMPIRICAL_2_PERCENT_WIND: "2%-Wind Comparator",
  H0_EFFECTIVE_CURRENT: "Hybrid Effective Current",
  H1_WDE17_EFFECTIVE_CURRENT: "Hybrid WDE17-Style",
};

export default function ModelLab() {
  const [data, setData] = useState(null);
  const [hindcast, setHindcast] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchModelEvaluations(controller.signal),
      fetchHybridHindcast(controller.signal),
    ]).then(([evaluations, example]) => {
      setData(evaluations);
      setHindcast(example);
    }).catch((requestError) => {
      if (requestError.name !== "AbortError") setError(requestError.message);
    });
    return () => controller.abort();
  }, []);

  if (error) return <ModuleState title="Model Lab" message={error} />;
  if (!data) return <ModuleState title="Model Lab" message="Loading verified hindcast evaluations..." loading />;

  const lockedRows = ["P0_PERSISTENCE", "P1_CONSTANT_VELOCITY", "P2_SURFACE_CURRENT", "P3_WDE17_SURFACE", "H0_EFFECTIVE_CURRENT", "H1_WDE17_EFFECTIVE_CURRENT"];
  const physicsRows = ["P0_PERSISTENCE", "P1_CONSTANT_VELOCITY", "P2_SURFACE_CURRENT", "P3_WDE17_SURFACE", "P2W_EMPIRICAL_2_PERCENT_WIND"];
  const testMetrics = data.hybrid.metrics.final_test;
  const radii = data.hybrid.uncertainty.radii_km;

  return <><section className="mission-workspace module-workspace"><div className="workspace-header"><div><span className="workspace-kicker">A76C / HISTORICAL HINDCAST / NOT LIVE FORECAST</span><h2>Model Lab</h2></div><span className="data-chip active">MODEL_PREDICTION</span></div><div className="module-scroll"><section className="module-panel"><div className="section-heading"><div><span className="panel-kicker">LOCKED FINAL TEST</span><h3>Hybrid Evaluation</h3></div><strong>lambda {data.hybrid.selected_lambda.toFixed(2)}</strong></div><ModelTable rows={lockedRows} metrics={testMetrics} selected={data.hybrid.selected_production_candidate} locked /></section><section className="module-panel"><span className="panel-kicker">FULL ROLLING PHYSICS BENCHMARK</span><h3>Canonical and Empirical Comparators</h3><ModelTable rows={physicsRows} metrics={data.physics.models} skills={data.physics.skill_vs_persistence_mean_error} /></section><section className="module-panel"><span className="panel-kicker">EMPIRICAL HINDCAST ERROR ENVELOPE</span><div className="uncertainty-radii">{["50", "80", "95"].map((level) => <div key={level}><span>{level}% RADIUS</span><strong>{radii[level].toFixed(2)} km</strong><small>Observed test coverage {(100 * data.hybrid.uncertainty.final_test_coverage[level]).toFixed(1)}%</small></div>)}</div></section><section className="module-panel"><span className="panel-kicker">SCIENTIFIC INTERPRETATION</span><p>Surface current outperformed persistence. The classic 2%-wind comparator performed poorly. The 29 m sensitivity remains exploratory because A76C draft is unknown.</p><p>Hybrid locked-test mean improvement was {Math.abs(data.hybrid.paired_bootstrap.mean_difference_km).toFixed(2)} km, but the paired 95% interval crosses zero. No conclusive improvement was established.</p></section></div></section><aside className="intelligence-rail"><section className="rail-section"><span className="panel-kicker">BEST CANONICAL MODEL</span><h3>{LABELS[data.physics.best_canonical_physics_model]}</h3><p className="processing-note">Selected from the uncalibrated physics benchmark.</p></section><section className="rail-section"><span className="panel-kicker">PRODUCTION CANDIDATE</span><h3>{LABELS[data.hybrid.selected_production_candidate]}</h3><p className="processing-note">The simpler model remains selected because hybrid improvement was not conclusive.</p></section><section className="rail-section"><span className="panel-kicker">HINDCAST EXAMPLE</span>{hindcast ? <dl className="observation-facts"><div><dt>Interval</dt><dd>{hindcast.start.date} / {hindcast.actual_endpoint.date}</dd></div><div><dt>Endpoint error</dt><dd>{hindcast.endpoint_error_km.toFixed(3)} km</dd></div><div><dt>Classification</dt><dd>{hindcast.prediction_classification}</dd></div></dl> : <p className="processing-note">Unavailable</p>}</section></aside></>;
}

function ModelTable({ rows, metrics, skills, selected, locked = false }) {
  return <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Model</th><th>Mean km</th><th>Median km</th>{locked && <th>RMSE km</th>}<th>Valid n</th>{skills && <th>Skill</th>}</tr></thead><tbody>{rows.map((model) => { const metric = metrics[model]; return <tr key={model} className={model === selected ? "selected" : ""}><td>{LABELS[model]}</td><td>{(metric.mean_error_km ?? metric.mean_km).toFixed(3)}</td><td>{(metric.median_error_km ?? metric.median_km).toFixed(3)}</td>{locked && <td>{metric.rmse_error_km.toFixed(3)}</td>}<td>{metric.valid_intervals ?? metric.n}</td>{skills && <td>{model === "P0_PERSISTENCE" ? "reference" : skills[model]?.toFixed(3) ?? "-"}</td>}</tr>; })}</tbody></table></div>;
}

function ModuleState({ title, message, loading = false }) {
  return <><section className="mission-workspace module-workspace"><div className="workspace-header"><div><span className="workspace-kicker">HISTORICAL RESEARCH</span><h2>{title}</h2></div></div><div className="module-state"><strong>{loading ? "LOADING VERIFIED RESULTS" : "VERIFIED MODEL API UNAVAILABLE"}</strong><span>{message}</span><span>No substitute results are displayed.</span></div></section><aside className="intelligence-rail" /></>;
}
