import { useEffect, useState } from "react";
import AntarcticMap from "./components/map/AntarcticMap.jsx";
import MapLegend from "./components/map/MapLegend.jsx";
import ObservationInfo from "./components/map/ObservationInfo.jsx";
import IcebergRegistryInfo from "./components/map/IcebergRegistryInfo.jsx";
import { fetchLatestIcebergs } from "./services/icebergApi.js";
import { fetchLatestSeaIce } from "./services/seaIceApi.js";

export default function App() {
  const [observation, setObservation] = useState(null);
  const [error, setError] = useState("");
  const [icebergRegistry, setIcebergRegistry] = useState(null);
  const [icebergError, setIcebergError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchLatestSeaIce(controller.signal)
      .then(setObservation)
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });
    fetchLatestIcebergs(controller.signal)
      .then(setIcebergRegistry)
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setIcebergError(requestError.message);
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="mission-shell">
      <header className="mission-header">
        <div>
          <span className="system-kicker">SIH26059 · ANTARCTIC OPERATIONS</span>
          <h1>POLARIS-AI</h1>
        </div>
        <div className="status-lockup"><span className="status-dot" /> VERIFIED SOURCE ONLINE</div>
      </header>
      <section className="mission-stage">
        <div className="map-frame">
          {observation ? (
            <AntarcticMap metadata={observation.metadata} grid={observation.grid} icebergs={icebergRegistry?.icebergs ?? []} />
          ) : (
            <div className="map-state" role="status">
              {error ? <><strong>SCIENTIFIC DATA UNAVAILABLE</strong><span>{error}</span><span>No substitute or demonstration data is displayed.</span></> : <span>Loading verified observation…</span>}
            </div>
          )}
          {observation && <MapLegend />}
          <div className="map-attribution">Sea ice: Copernicus Marine Service · OSI-SAF / EUMETSAT<br />Icebergs: U.S. National Ice Center (USNIC)<br />Land: Natural Earth 1:110m</div>
        </div>
        <aside className="science-panel">
          <ObservationInfo metadata={observation?.metadata} error={error} />
          <IcebergRegistryInfo metadata={icebergRegistry?.metadata} error={icebergError} />
        </aside>
      </section>
    </main>
  );
}
