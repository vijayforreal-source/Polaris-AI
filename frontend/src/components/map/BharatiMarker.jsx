import Feature from "ol/Feature.js";
import Point from "ol/geom/Point.js";
import VectorLayer from "ol/layer/Vector.js";
import { transform } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Circle, Fill, Stroke, Style, Text } from "ol/style.js";
import { ANTARCTIC_CRS } from "../../config/map.js";

export function createBharatiLayer(station) {
  const feature = new Feature({ geometry: new Point(transform([station.longitude, station.latitude], "EPSG:4326", ANTARCTIC_CRS)), station });
  return new VectorLayer({
    source: new VectorSource({ features: [feature] }),
    style: new Style({
      image: new Circle({ radius: 6, fill: new Fill({ color: "#ffb454" }), stroke: new Stroke({ color: "#07151d", width: 2 }) }),
      text: new Text({ text: "BHARATI\nIndian Antarctic Research Station", font: "600 11px Inter, sans-serif", fill: new Fill({ color: "#fff" }), stroke: new Stroke({ color: "rgba(4,17,24,.95)", width: 3 }), offsetY: -23, textAlign: "center" }),
    }),
  });
}
