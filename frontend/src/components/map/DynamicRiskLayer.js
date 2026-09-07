import Feature from "ol/Feature.js";
import Polygon from "ol/geom/Polygon.js";
import VectorLayer from "ol/layer/Vector.js";
import VectorSource from "ol/source/Vector.js";
import { transform } from "ol/proj.js";
import { Fill, Stroke, Style } from "ol/style.js";
import { ANTARCTIC_CRS } from "../../config/map.js";

const COLORS = ["rgba(88,195,151,.65)", "rgba(166,200,106,.65)", "rgba(233,202,101,.68)", "rgba(233,145,80,.70)", "rgba(219,89,101,.72)"];
function bounds(axis, i) {
  const previous = axis[Math.max(0,i-1)], next = axis[Math.min(axis.length-1,i+1)];
  return [i ? (previous+axis[i])/2 : axis[i]-(next-axis[i])/2,
    i === axis.length-1 ? axis[i]+(axis[i]-previous)/2 : (axis[i]+next)/2];
}
export function createDynamicRiskLayer(field) {
  const features = [];
  if (field) field.risk_grid.forEach((row,y) => row.forEach((score,x) => {
    const [south,north] = bounds(field.latitude,y), [west,east] = bounds(field.longitude,x);
    const ring = [[west,south],[east,south],[east,north],[west,north],[west,south]].map(c => transform(c,"EPSG:4326",ANTARCTIC_CRS));
    features.push(new Feature({geometry:new Polygon([ring]),category:field.risk_category_grid[y][x],
      landOrInvalid:!!(field.hard_constraint_grid[y][x]&1),blocked:!field.navigable_mask[y][x],riskScore:score}));
  }));
  const cache = new Map();
  return new VectorLayer({source:new VectorSource({features,wrapX:false}),zIndex:2,
    style:feature => {
      const key = `${feature.get("category")}-${feature.get("landOrInvalid")}-${feature.get("blocked")}`;
      if (!cache.has(key)) cache.set(key,new Style({fill:new Fill({color:feature.get("landOrInvalid") ? "rgba(32,43,49,.7)" : COLORS[feature.get("category")]}),stroke:new Stroke({color:feature.get("blocked") ? "rgba(30,15,23,.5)" : "rgba(5,23,33,.12)",width:.4})}));
      return cache.get(key);
    }});
}
