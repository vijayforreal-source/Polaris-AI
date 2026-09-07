import { useEffect, useRef, useState } from "react";
import GeoJSON from "ol/format/GeoJSON.js";
import VectorLayer from "ol/layer/Vector.js";
import Map from "ol/Map.js";
import { transformExtent } from "ol/proj.js";
import VectorSource from "ol/source/Vector.js";
import { Fill, Stroke, Style } from "ol/style.js";
import View from "ol/View.js";
import { ANTARCTIC_CRS, LAND_SOURCE_URL } from "../../config/map.js";
import { createBharatiLayer } from "./BharatiMarker.jsx";
import { createSeaIceLayer } from "./SeaIceLayer.jsx";
import { createIcebergLayer } from "./IcebergLayer.jsx";
import IcebergPopup from "./IcebergPopup.jsx";
import { createHistoricalTransitLayer } from "./HistoricalTransitLayer.js";
import { extend as extendExtent } from "ol/extent.js";

const NO_ICEBERGS = [];

export default function AntarcticMap({ metadata, grid, icebergs = NO_ICEBERGS, historicalTracks = NO_ICEBERGS, onSelectVoyage }) {
  const mapTarget = useRef(null);
  const [landWarning, setLandWarning] = useState("");
  const [selectedIceberg, setSelectedIceberg] = useState(null);
  useEffect(() => {
    const landSource = new VectorSource({ wrapX: false });
    const minimumLatitude = (coordinates) => coordinates.flat(Infinity).filter((_, index) => index % 2 === 1).reduce((minimum, latitude) => Math.min(minimum, latitude), 90);
    fetch(LAND_SOURCE_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`Natural Earth returned HTTP ${response.status}`);
        return response.json();
      })
      .then((geojson) => {
        const antarcticFeatures = geojson.features.filter((feature) => minimumLatitude(feature.geometry.coordinates) <= -60);
        const format = new GeoJSON();
        landSource.addFeatures(format.readFeatures({ ...geojson, features: antarcticFeatures }, { dataProjection: "EPSG:4326", featureProjection: ANTARCTIC_CRS }));
      })
      .catch(() => setLandWarning("Natural Earth land context unavailable; no replacement geometry shown."));
    const landLayer = new VectorLayer({ source: landSource, style: new Style({ fill: new Fill({ color: "#17242b" }), stroke: new Stroke({ color: "#526670", width: 1 }) }) });
    const sourceExtent = [metadata.bbox.minimum_longitude, metadata.bbox.minimum_latitude, metadata.bbox.maximum_longitude, metadata.bbox.maximum_latitude];
    const icebergLayer = createIcebergLayer(icebergs);
    const transitLayer = createHistoricalTransitLayer(historicalTracks);
    const map = new Map({ target: mapTarget.current, layers: [landLayer, createSeaIceLayer(grid), icebergLayer, createBharatiLayer(metadata.bharati), transitLayer], view: new View({ projection: ANTARCTIC_CRS }), controls: [] });
    map.on("singleclick", (event) => {
      const feature = map.forEachFeatureAtPixel(
        event.pixel,
        (candidate) => candidate.get("iceberg") || candidate.get("historicalVoyage") ? candidate : null,
        { hitTolerance: 8 },
      );
      setSelectedIceberg(feature?.get("iceberg") ?? null);
      onSelectVoyage?.(feature?.get("historicalVoyage") ?? null);
    });
    const extent = transformExtent(sourceExtent, "EPSG:4326", ANTARCTIC_CRS);
    if (transitLayer.getSource().getFeatures().length) extendExtent(extent, transitLayer.getSource().getExtent());
    map.getView().fit(extent, { padding: [70, 70, 70, 70], maxZoom: 8 });
    return () => map.setTarget(undefined);
  }, [metadata, grid, icebergs, historicalTracks, onSelectVoyage]);
  return <><div ref={mapTarget} className="antarctic-map" aria-label="Verified Antarctic sea-ice and USNIC iceberg map" /><div className="projection-label">DISPLAY / EPSG:3031</div>{landWarning && <div className="land-warning">{landWarning}</div>}<IcebergPopup iceberg={selectedIceberg} onClose={() => setSelectedIceberg(null)} /></>;
}
