import proj4 from "proj4";
import { register } from "ol/proj/proj4.js";

export const ANTARCTIC_CRS = "EPSG:3031";

// EPSG:3031 — WGS 84 / Antarctic Polar Stereographic. Display transforms only;
// this does not alter or reproject the stored Copernicus source NetCDF.
proj4.defs(ANTARCTIC_CRS, "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs");
register(proj4);

export const LAND_SOURCE_URL = "/data/ne_110m_land.geojson";

export function concentrationColor(value) {
  const bounded = Math.max(0, Math.min(100, value)) / 100;
  const start = [22, 66, 86];
  const end = [224, 249, 255];
  const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * bounded));
  return `rgba(${channels.join(",")},0.86)`;
}
