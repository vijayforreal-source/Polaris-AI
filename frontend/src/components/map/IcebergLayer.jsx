import Feature from "ol/Feature.js";
import Point from "ol/geom/Point.js";
import VectorLayer from "ol/layer/Vector.js";
import { transform } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Fill, RegularShape, Stroke, Style, Text } from "ol/style.js";
import { ANTARCTIC_CRS } from "../../config/map.js";

export function createIcebergLayer(icebergs) {
  const features = icebergs.map((iceberg) => new Feature({
    geometry: new Point(transform([iceberg.longitude, iceberg.latitude], "EPSG:4326", ANTARCTIC_CRS)),
    iceberg,
  }));
  return new VectorLayer({
    source: new VectorSource({ features, wrapX: false }),
    style: (feature) => new Style({
      image: new RegularShape({ points: 4, radius: 6, angle: Math.PI / 4, fill: new Fill({ color: "#d87e53" }), stroke: new Stroke({ color: "#fff0df", width: 1.2 }) }),
      text: new Text({ text: feature.get("iceberg").iceberg_id, font: "600 10px Consolas, monospace", fill: new Fill({ color: "#ffd6b5" }), stroke: new Stroke({ color: "#071117", width: 3 }), offsetY: -14 }),
    }),
  });
}
