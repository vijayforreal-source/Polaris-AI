import Feature from "ol/Feature.js";
import LineString from "ol/geom/LineString.js";
import VectorLayer from "ol/layer/Vector.js";
import VectorSource from "ol/source/Vector.js";
import { Stroke, Style } from "ol/style.js";
import { transform } from "ol/proj.js";
import { ANTARCTIC_CRS } from "../../config/map.js";

const COLORS = { SAFE: "#58c397", FAST: "#67a7e8", ECO: "#d7bd63", BALANCED: "#db5965" };
export function createRouteLayer(routes = [], selected = null) {
  const source = new VectorSource({ wrapX: false });
  routes.forEach(route => {
    if (!route.waypoints?.length || route.status !== "AVAILABLE") return;
    const coords = route.waypoints.map(point => transform([point.longitude, point.latitude], "EPSG:4326", ANTARCTIC_CRS));
    source.addFeature(new Feature({ geometry: new LineString(coords), routeObjective: route.objective }));
  });
  return new VectorLayer({ source, zIndex: 8, style: feature => new Style({ stroke: new Stroke({ color: COLORS[feature.get("routeObjective")] ?? "#fff", width: feature.get("routeObjective") === selected ? 5 : 2, lineDash: feature.get("routeObjective") === selected ? undefined : [8, 5] }) }) });
}
export { COLORS as ROUTE_COLORS };
