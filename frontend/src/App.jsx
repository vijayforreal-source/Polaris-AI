import { useEffect, useMemo, useState } from "react";
import AntarcticMap from "./components/map/AntarcticMap.jsx";
import MapLegend from "./components/map/MapLegend.jsx";
import ObservationInfo from "./components/map/ObservationInfo.jsx";
import IcebergRegistryInfo from "./components/map/IcebergRegistryInfo.jsx";
import { fetchLatestIcebergs } from "./services/icebergApi.js";
import { fetchLatestSeaIce } from "./services/seaIceApi.js";

const NAVIGATION = [
  { id: "mission", label: "Mission Control", code: "01", active: true },
  { id: "ice", label: "Ice Intelligence", code: "02" },
  { id: "forecast", label: "Sea-Ice Forecast", code: "03" },
  { id: "navigation", label: "Navigation", code: "04" },
  { id: "models", label: "Model Lab", code: "05" },
  { id: "data", label: "Data Sources", code: "06" },
];

const TIMELINE = [
  { label: "OBSERVED", active: true },
  { label: "+6H" },
  { label: "+12H" },
  { label: "+24H" },
  { label: "+48H" },
  { label: "+72H" },
];

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
        if (requestError.name !== "AbortError") {
          setError(requestError.message);
        }
      });

    fetchLatestIcebergs(controller.signal)
      .then(setIcebergRegistry)
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setIcebergError(requestError.message);
        }
      });

    return () => controller.abort();
  }, []);

  const icebergCount = icebergRegistry?.icebergs?.length ?? 0;

  const systemState = useMemo(() => {
    if (error || icebergError) return "DEGRADED";
    if (observation && icebergRegistry) return "NOMINAL";
    return "CONNECTING";
  }, [error, icebergError, observation, icebergRegistry]);

  return (
    <main className="polaris-app">
      <header className="command-header">
        <div className="brand-lockup">
          <div className="brand-mark">P</div>

          <div>
            <div className="system-kicker">
              SIH26059 / ANTARCTIC OPERATIONS
            </div>
            <h1>POLARIS-AI</h1>
          </div>
        </div>

        <div className="command-header-center">
          <span className="header-section-label">MISSION</span>
          <strong>BHARATI / PRYDZ BAY</strong>
        </div>

        <div className="system-state">
          <div>
            <span className="system-state-label">SYSTEM STATE</span>
            <strong>{systemState}</strong>
          </div>

          <span
            className={`status-dot ${
              systemState === "DEGRADED" ? "status-dot-warning" : ""
            }`}
          />
        </div>
      </header>

      <section className="operations-layout">
        <aside className="side-navigation">
          <div className="nav-section-label">OPERATIONS</div>

          <nav>
            {NAVIGATION.map((item) => (
              <button
                className={`nav-item ${item.active ? "active" : ""}`}
                key={item.id}
                type="button"
              >
                <span className="nav-code">{item.code}</span>

                <span className="nav-label">{item.label}</span>

                {!item.active && (
                  <span className="nav-state">LOCKED</span>
                )}
              </button>
            ))}
          </nav>

          <div className="nav-footer">
            <div className="nav-footer-row">
              <span>DISPLAY</span>
              <strong>EPSG:3031</strong>
            </div>

            <div className="nav-footer-row">
              <span>MODE</span>
              <strong>SCIENTIFIC</strong>
            </div>

            <div className="nav-footer-row">
              <span>DATA</span>
              <strong>{observation ? "VERIFIED" : "WAITING"}</strong>
            </div>
          </div>
        </aside>

        <section className="mission-workspace">
          <div className="workspace-header">
            <div>
              <span className="workspace-kicker">
                MISSION CONTROL / LIVE SCIENTIFIC VIEW
              </span>
              <h2>Antarctic Operating Picture</h2>
            </div>

            <div className="workspace-statuses">
              <span className="data-chip active">OBSERVATION</span>
              <span className="data-chip">FORECAST UNAVAILABLE</span>
              <span className="data-chip">MODEL OUTPUT UNAVAILABLE</span>
            </div>
          </div>

          <div className="map-frame">
            {observation ? (
              <AntarcticMap
                metadata={observation.metadata}
                grid={observation.grid}
                icebergs={icebergRegistry?.icebergs ?? []}
              />
            ) : (
              <div className="map-state" role="status">
                {error ? (
                  <>
                    <strong>SCIENTIFIC DATA UNAVAILABLE</strong>
                    <span>{error}</span>
                    <span>
                      No substitute or demonstration data is displayed.
                    </span>
                  </>
                ) : (
                  <>
                    <span className="loading-pulse" />
                    <span>Loading verified observation...</span>
                  </>
                )}
              </div>
            )}

            {observation && <MapLegend />}

            <div className="mission-coordinate-card">
              <span>ACTIVE REGION</span>
              <strong>BHARATI / PRYDZ BAY</strong>
              <small>ANTARCTICA</small>
            </div>

            <div className="map-attribution">
              Sea ice: Copernicus Marine / OSI-SAF
              <br />
              Icebergs: U.S. National Ice Center
              <br />
              Land: Natural Earth 1:110m
            </div>
          </div>

          <div className="timeline-panel">
            <div className="timeline-description">
              <span className="timeline-title">TEMPORAL STATE</span>
              <strong>Observed environmental state</strong>
            </div>

            <div className="timeline-track">
              {TIMELINE.map((item) => (
                <button
                  type="button"
                  key={item.label}
                  className={`timeline-item ${
                    item.active ? "active" : ""
                  }`}
                  disabled={!item.active}
                >
                  <span className="timeline-node" />
                  <strong>{item.label}</strong>
                  <small>
                    {item.active ? "AVAILABLE" : "UNAVAILABLE"}
                  </small>
                </button>
              ))}
            </div>
          </div>
        </section>

        <aside className="intelligence-rail">
          <section className="rail-section mission-overview">
            <div className="rail-heading">
              <div>
                <span className="panel-kicker">MISSION CONTEXT</span>
                <h3>Bharati Approach</h3>
              </div>

              <span className="mission-id">ANT-01</span>
            </div>

            <div className="mission-stats">
              <div>
                <span>SEA ICE</span>
                <strong>{observation ? "ONLINE" : "WAITING"}</strong>
              </div>

              <div>
                <span>ICEBERGS</span>
                <strong>{icebergCount}</strong>
              </div>

              <div>
                <span>FORECAST</span>
                <strong className="unavailable-text">N/A</strong>
              </div>
            </div>
          </section>

          <section className="rail-section scientific-observation">
            <ObservationInfo
              metadata={observation?.metadata}
              error={error}
            />
          </section>

          <section className="rail-section">
            <IcebergRegistryInfo
              metadata={icebergRegistry?.metadata}
              error={icebergError}
            />
          </section>

          <section className="rail-section capability-state">
            <span className="panel-kicker">PREDICTIVE SYSTEMS</span>

            <div className="capability-row">
              <span>Iceberg trajectory</span>
              <strong>IN DEVELOPMENT</strong>
            </div>

            <div className="capability-row">
              <span>Sea-ice forecast</span>
              <strong>UNAVAILABLE</strong>
            </div>

            <div className="capability-row">
              <span>Vessel routing</span>
              <strong>UNAVAILABLE</strong>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}