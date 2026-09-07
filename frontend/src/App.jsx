import { useEffect, useMemo, useState } from "react";
import { fetchLatestIcebergs } from "./services/icebergApi.js";
import { fetchLatestSeaIce } from "./services/seaIceApi.js";
import DataSources from "./views/DataSources.jsx";
import IceIntelligence from "./views/IceIntelligence.jsx";
import MissionControl from "./views/MissionControl.jsx";
import ModelLab from "./views/ModelLab.jsx";
import SeaIceForecast from "./views/SeaIceForecast.jsx";
import UnavailableModule from "./views/UnavailableModule.jsx";

const NAVIGATION = [
  { id: "mission", label: "Mission Control", code: "01" },
  { id: "ice", label: "Ice Intelligence", code: "02" },
  { id: "forecast", label: "Sea-Ice Forecast", code: "03" },
  { id: "navigation", label: "Navigation", code: "04" },
  { id: "models", label: "Model Lab", code: "05" },
  { id: "data", label: "Data Sources", code: "06" },
];

export default function App() {
  const [activeView, setActiveView] = useState("mission");
  const [observation, setObservation] = useState(null);
  const [error, setError] = useState("");
  const [icebergRegistry, setIcebergRegistry] = useState(null);
  const [icebergError, setIcebergError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchLatestSeaIce(controller.signal).then(setObservation).catch((requestError) => {
      if (requestError.name !== "AbortError") setError(requestError.message);
    });
    fetchLatestIcebergs(controller.signal).then(setIcebergRegistry).catch((requestError) => {
      if (requestError.name !== "AbortError") setIcebergError(requestError.message);
    });
    return () => controller.abort();
  }, []);

  const systemState = useMemo(() => {
    if (error || icebergError) return "DEGRADED";
    if (observation && icebergRegistry) return "NOMINAL";
    return "CONNECTING";
  }, [error, icebergError, observation, icebergRegistry]);

  const renderView = () => {
    if (activeView === "mission") return <MissionControl observation={observation} error={error} icebergRegistry={icebergRegistry} icebergError={icebergError} />;
    if (activeView === "ice") return <IceIntelligence registry={icebergRegistry} registryError={icebergError} />;
    if (activeView === "models") return <ModelLab />;
    if (activeView === "data") return <DataSources observation={observation} registry={icebergRegistry} />;
    if (activeView === "forecast") return <SeaIceForecast />;
    return <UnavailableModule title="Navigation Engine" description="Vessel, origin, destination, mission priority, route risk, fuel, and ETA calculations have not been implemented." />;
  };

  return <main className="polaris-app"><header className="command-header"><div className="brand-lockup"><div className="brand-mark">P</div><div><div className="system-kicker">SIH26059 / ANTARCTIC OPERATIONS</div><h1>POLARIS-AI</h1></div></div><div className="command-header-center"><span className="header-section-label">ACTIVE MODULE</span><strong>{NAVIGATION.find((item) => item.id === activeView)?.label.toUpperCase()}</strong></div><div className="system-state"><div><span className="system-state-label">SYSTEM STATE</span><strong>{systemState}</strong></div><span className={`status-dot ${systemState === "DEGRADED" ? "status-dot-warning" : ""}`} /></div></header><section className="operations-layout"><aside className="side-navigation"><div className="nav-section-label">OPERATIONS</div><nav>{NAVIGATION.map((item) => <button className={`nav-item ${activeView === item.id ? "active" : ""}`} key={item.id} type="button" onClick={() => setActiveView(item.id)}><span className="nav-code">{item.code}</span><span className="nav-label">{item.label}</span>{["navigation"].includes(item.id) && <span className="nav-state">PENDING</span>}</button>)}</nav><div className="nav-footer"><div className="nav-footer-row"><span>DISPLAY</span><strong>EPSG:3031</strong></div><div className="nav-footer-row"><span>MODE</span><strong>SCIENTIFIC</strong></div><div className="nav-footer-row"><span>DATA</span><strong>{systemState === "NOMINAL" ? "VERIFIED" : systemState}</strong></div></div></aside>{renderView()}</section></main>;
}
