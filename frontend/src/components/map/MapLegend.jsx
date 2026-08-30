export default function MapLegend() {
  return <section className="map-legend" aria-label="Sea-ice concentration legend"><div className="legend-title">Sea-Ice Concentration (%)</div><div className="legend-ramp" /><div className="legend-scale"><span>0</span><span>50</span><span>100</span></div><div className="missing-key"><span /> Missing / no-data (transparent)</div></section>;
}
