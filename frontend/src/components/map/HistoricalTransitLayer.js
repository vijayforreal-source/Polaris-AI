import Feature from "ol/Feature.js";
import MultiLineString from "ol/geom/MultiLineString.js";
import VectorLayer from "ol/layer/Vector.js";
import { transform } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Stroke, Style } from "ol/style.js";
import { ANTARCTIC_CRS } from "../../config/map.js";

export function createHistoricalTransitLayer(voyages) {
  const features = voyages.filter(v => v.renderable && v.source_verified).flatMap(voyage => {
    const gaps = new Set(voyage.data_gaps.map(g => g.after_point));
    const lines = [];
    let line = [];
    voyage.points.forEach((point,index) => {
      line.push(transform([point.longitude, point.latitude], "EPSG:4326", ANTARCTIC_CRS));
      if (gaps.has(index) || index === voyage.points.length - 1) {
        if (line.length >= 2) lines.push(line);
        line = [];
      }
    });
    return lines.length ? [new Feature({geometry: new MultiLineString(lines), historicalVoyage: voyage})] : [];
  });
  return new VectorLayer({source: new VectorSource({features, wrapX:false}),
    style: new Style({stroke: new Stroke({color:"#efc06b", width:3, lineDash:[9,5]})}), zIndex: 4});
}
