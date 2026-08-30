export default function IcebergRegistryInfo({ metadata, error }) {
  return <section className="registry-info"><p className="panel-kicker">USNIC REGISTRY</p>{metadata ? <><strong>{metadata.study_region_count} tracked named icebergs</strong><span>in active study region</span><dl><div><dt>Current Antarctic registry</dt><dd>{metadata.total_registry_count}</dd></div><div><dt>Provider report date</dt><dd>{metadata.provider_report_date}</dd></div></dl><p>{metadata.limitation}</p></> : <p className="panel-error">{error || "Loading current USNIC registry…"}</p>}</section>;
}
