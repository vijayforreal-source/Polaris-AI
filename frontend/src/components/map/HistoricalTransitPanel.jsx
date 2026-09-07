import { useEffect, useState } from "react";
import { fetchTransitStatus, fetchTransitVoyages, fetchTransitVoyage } from "../../services/historicalTransitApi.js";

export function useHistoricalTransit() {
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState(null);
  const [listing, setListing] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setError(""); setListing(null); setTracks([]); setSelected(null);
    Promise.all([fetchTransitStatus(controller.signal), fetchTransitVoyages(offset, controller.signal)])
      .then(([s, l]) => { setStatus(s); setListing(l); })
      .catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [offset]);
  useEffect(() => {
    const controller = new AbortController();
    setTracks([]); setSelected(null); setLoading(false);
    if (enabled && listing) {
      setLoading(true);
      Promise.all(listing.voyages.filter(v => v.renderable).map(v => fetchTransitVoyage(v.voyage_id, controller.signal)))
        .then(values => { if (!controller.signal.aborted) { setTracks(values); setLoading(false); } })
        .catch(e => { if (e.name !== "AbortError") { setError(e.message); setLoading(false); } });
    }
    return () => controller.abort();
  }, [enabled, listing]);
  return { enabled, setEnabled, status, listing, tracks, selected, setSelected, error, loading, offset, setOffset };
}

function Details({ voyage, onClose }) {
  return <section className="transit-details" aria-label="Historical voyage details">
    <button type="button" onClick={onClose}>Close voyage details</button>
    <h4>{voyage.vessel_name}</h4>
    {[["Voyage / expedition", `${voyage.voyage_id} / ${voyage.expedition_id ?? "not supplied"}`],
      ["Origin", voyage.origin], ["Destination", voyage.destination],
      ["Start date", voyage.start_time], ["End date", voyage.end_time],
      ["Distance estimate", voyage.distance_km == null ? "Unavailable" : `${voyage.distance_km.toFixed(1)} km`],
      ["Route source", voyage.source], ["Source reference", voyage.source_reference],
      ["Track quality", voyage.track_quality], ["Source reviewed by", voyage.verified_by ?? "Not verified"]]
      .map(([key,value]) => <div className="forecast-detail" key={key}><span>{key}</span><strong>{value ?? "Not supplied"}</strong></div>)}
    <p>{voyage.renderable ? "Previously travelled corridor" : "Questionable record - excluded from map"}</p>
    <p>{voyage.renderable ? `Last verified transit: ${Math.floor(voyage.age_days)} days ago` : "No verified transit age available"}</p>
    {voyage.renderable && <p>Used by 1 known voyage (this track).</p>}
    {voyage.quality_notes?.map(note => <p key={note}>{note}</p>)}
    <p>Historical evidence only. Current environmental safety must be evaluated separately.</p>
  </section>;
}

export default function HistoricalTransitPanel({ transit }) {
  const { status, listing, enabled, setEnabled, selected, setSelected, loading, error, offset, setOffset } = transit;
  return <section className="rail-section historical-transit-panel">
    <span className="panel-kicker">HISTORICAL EVIDENCE / OBSERVATION</span>
    <h3>Historical Transit Intelligence</h3>
    <label className="transit-toggle"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Historical Vessel Tracks</label>
    <p>Cape Town → Bharati · Bharati → Maitri · Maitri → Cape Town</p>
    <small>Voyage corridor terminology; these labels do not define fixed maritime routes.</small>
    {error ? <p role="alert">{error}</p> : !status ? <p role="status">Loading historical transit status...</p> : <>
      <div className="forecast-detail"><span>Verified voyages</span><strong>{status.verified_voyage_count}</strong></div>
      <div className="forecast-detail"><span>Latest known transit</span><strong>{status.latest_transit ?? "None loaded"}</strong></div>
      <p>Sources: {status.data_sources.join(", ") || "None loaded"}</p>
      {!status.available && <p role="status">No verified historical voyage tracks are currently loaded.</p>}
      {Object.entries(status.track_quality).filter(([,count]) => count > 0).map(([quality,count]) => <div className="forecast-detail" key={quality}><span>{quality}</span><strong>{count}</strong></div>)}
      {status.load_errors.length > 0 && <p>{status.load_errors.length} import/storage issue(s); questionable records remain excluded.</p>}
    </>}
    {loading && <p role="status">Loading verified tracks...</p>}
    {enabled && <div className="transit-voyages">{listing?.voyages.map(v => <button type="button" key={v.voyage_id} onClick={() => setSelected(v)}>{v.vessel_name} · {v.voyage_id} · {v.track_quality}</button>)}</div>}
    {listing?.total > 25 && <div className="transit-pagination"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous voyages</button><span>{offset + 1}–{Math.min(offset + 25, listing.total)} / {listing.total}</span><button disabled={offset + 25 >= listing.total} onClick={() => setOffset(offset + 25)}>Next voyages</button></div>}
    {enabled && selected && <Details voyage={selected} onClose={() => setSelected(null)} />}
    <p className="transit-disclaimer">Historical vessel track — not a current safety guarantee.</p>
    <small>Historical transit confidence is not a safety probability. Tracks are not AI predictions or navigation authority.</small>
  </section>;
}
