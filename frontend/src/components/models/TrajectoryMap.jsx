import Feature from "ol/Feature.js";
import CircleGeometry from "ol/geom/Circle.js";
import LineString from "ol/geom/LineString.js";
import Point from "ol/geom/Point.js";
import VectorLayer from "ol/layer/Vector.js";
import Map from "ol/Map.js";
import { fromLonLat } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Circle as CircleStyle, Fill, Stroke, Style } from "ol/style.js";
import View from "ol/View.js";
import { useEffect, useRef } from "react";
import { ANTARCTIC_CRS } from "../../config/map.js";

const COLORS = { start: "#6bc6a5", predicted: "#9bd4df", actual: "#d8a06e" };

export default function TrajectoryMap({ result }) {
  const target = useRef(null);
  useEffect(() => {
    if (!result?.trajectory_points?.length) return undefined;
    const coordinates = result.trajectory_points.map((point) => fromLonLat([point.longitude, point.latitude], ANTARCTIC_CRS));
    const source = new VectorSource({ wrapX: false });
    source.addFeature(new Feature({ geometry: new LineString(coordinates), kind: "track" }));
    source.addFeature(new Feature({ geometry: new Point(coordinates[0]), kind: "start" }));
    if (result.endpoint) source.addFeature(new Feature({ geometry: new Point(coordinates.at(-1)), kind: "predicted" }));
    if (result.actual_historical_observation) source.addFeature(new Feature({ geometry: new Point(fromLonLat([result.actual_historical_observation.longitude, result.actual_historical_observation.latitude], ANTARCTIC_CRS)), kind: "actual" }));
    if (result.endpoint && result.uncertainty.applicable) {
      const endpoint = coordinates.at(-1);
      [[result.uncertainty.radius_95_km, "#425c69"], [result.uncertainty.radius_80_km, "#557482"], [result.uncertainty.radius_50_km, "#6d98a6"]].forEach(([radius, color]) => source.addFeature(new Feature({ geometry: new CircleGeometry(endpoint, radius * 1000), kind: "uncertainty", color })));
    }
    const layer = new VectorLayer({ source, style: (feature) => { const kind = feature.get("kind"); if (kind === "track") return new Style({ stroke: new Stroke({ color: COLORS.predicted, width: 2 }) }); if (kind === "uncertainty") return new Style({ stroke: new Stroke({ color: feature.get("color"), width: 1, lineDash: [5, 5] }), fill: new Fill({ color: "rgba(70, 120, 138, 0.035)" }) }); return new Style({ image: new CircleStyle({ radius: kind === "start" ? 6 : 5, fill: new Fill({ color: COLORS[kind] }), stroke: new Stroke({ color: "#071015", width: 2 }) }) }); } });
    const map = new Map({ target: target.current, layers: [layer], view: new View({ projection: ANTARCTIC_CRS }), controls: [] });
    map.getView().fit(source.getExtent(), { padding: [65, 65, 65, 65], maxZoom: 7, duration: 0 });
    return () => map.setTarget(undefined);
  }, [result]);
  return <div ref={target} className="trajectory-map" aria-label="A76C historical trajectory hindcast map" />;
}
