export default function DataSources({ observation, registry }) {
  const sources = [
    ["U.S. National Ice Center", "Antarctic Iceberg Registry", "OBSERVATION", registry?.metadata?.provider_report_date],
    ["Copernicus Marine / OSI-SAF", observation?.metadata?.dataset_id ?? "Sea-ice concentration", "OBSERVATION", observation?.metadata?.observation_time],
    ["Copernicus Marine GLO12", "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i", "ANALYSIS", "Historical A76C forcing"],
    ["Copernicus Climate / ECMWF", "ERA5 10 m wind", "REANALYSIS", "Historical A76C forcing"],
    ["POLARIS-AI", "Trajectory hindcast outputs", "MODEL_PREDICTION", "Research evaluation only"],
  ];
  return <><section className="mission-workspace module-workspace"><div className="workspace-header"><div><span className="workspace-kicker">PROVENANCE / SCIENTIFIC CLASSIFICATION</span><h2>Data Sources</h2></div></div><div className="module-scroll source-grid">{sources.map(([provider, product, classification, detail]) => <article className="source-card" key={product}><span className={`classification active class-${classification.toLowerCase()}`}>{classification}</span><h3>{provider}</h3><p>{product}</p><small>{detail || "Verified API metadata currently unavailable"}</small></article>)}</div></section><aside className="intelligence-rail"><section className="rail-section"><span className="panel-kicker">CLASSIFICATION CONTRACT</span><p className="processing-note">Observation, analysis, reanalysis, and model prediction remain distinguishable throughout POLARIS-AI.</p></section><section className="rail-section"><span className="panel-kicker">STATUS LANGUAGE</span><p className="processing-note">This view reports configured provenance and returned metadata. It does not claim live provider availability.</p></section></aside></>;
}
