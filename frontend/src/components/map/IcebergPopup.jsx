function Fact({ label, value, suffix = "" }) {
  if (value === null || value === undefined) return null;
  return <div><dt>{label}</dt><dd>{value}{suffix}</dd></div>;
}

export default function IcebergPopup({ iceberg, onClose }) {
  if (!iceberg) return null;
  return <section className="iceberg-popup"><button type="button" onClick={onClose} aria-label="Close iceberg details">×</button><p>USNIC ICEBERG</p><h3>{iceberg.iceberg_id}</h3><dl><Fact label="Last Update" value={iceberg.provider_last_update} /><Fact label="Position" value={`${iceberg.latitude.toFixed(2)}, ${iceberg.longitude.toFixed(2)}`} /><Fact label="Length" value={iceberg.length_nm} suffix=" NM" /><Fact label="Width" value={iceberg.width_nm} suffix=" NM" /><Fact label="Area" value={iceberg.area_sq_nm} suffix=" sq NM" /><Fact label="Source" value="U.S. National Ice Center" /><Fact label="Classification" value={iceberg.classification} /></dl></section>;
}
