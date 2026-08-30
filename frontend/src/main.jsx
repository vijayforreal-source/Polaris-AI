import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">SIH26059</p>
      <h1>POLARIS-AI</h1>
      <p>Antarctic Predictive Navigation Decision Support</p>
      <p className="status">Foundation Environment Operational</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

