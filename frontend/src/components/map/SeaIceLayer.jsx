import Feature from "ol/Feature.js";
import Polygon from "ol/geom/Polygon.js";
import VectorLayer from "ol/layer/Vector.js";
import { transform } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Fill, Stroke, Style } from "ol/style.js";
import { ANTARCTIC_CRS, concentrationColor } from "../../config/map.js";

function boundaries(coordinates) {
  return coordinates.map((coordinate, index) => {
    const previous = coordinates[Math.max(0, index - 1)];
    const next = coordinates[Math.min(coordinates.length - 1, index + 1)];
    return [index === 0 ? coordinate - (next - coordinate) / 2 : (previous + coordinate) / 2, index === coordinates.length - 1 ? coordinate + (coordinate - previous) / 2 : (coordinate + next) / 2];
  });
}

export function createSeaIceLayer(grid) {
  const latitudeBounds = boundaries(grid.latitude);
  const longitudeBounds = boundaries(grid.longitude);
  const features = [];
  grid.concentration.forEach((row, latitudeIndex) => {
    row.forEach((value, longitudeIndex) => {
      if (value === null) return;
      const [south, north] = latitudeBounds[latitudeIndex];
      const [west, east] = longitudeBounds[longitudeIndex];
      const ring = [[west, south], [east, south], [east, north], [west, north], [west, south]].map((coordinate) => transform(coordinate, "EPSG:4326", ANTARCTIC_CRS));
      features.push(new Feature({ geometry: new Polygon([ring]), concentration: value }));
    });
  });
  const styleCache = new Map();
  return new VectorLayer({
    source: new VectorSource({ features, wrapX: false }),
    style: (feature) => {
      const value = feature.get("concentration");
      const key = Math.round(value);
      if (!styleCache.has(key)) styleCache.set(key, new Style({ fill: new Fill({ color: concentrationColor(value) }), stroke: new Stroke({ color: "rgba(5,23,33,.15)", width: .25 }) }));
      return styleCache.get(key);
    },
  });
}
