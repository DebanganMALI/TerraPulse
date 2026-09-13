import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

// esri's canvas tiles need no key; carto started demanding one mid-build.
// swap BASE for World_Imagery/MapServer to demo over true-colour satellite.
const BASE =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}";
const LABELS =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}";
const ATTRIB = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";

function Expose({ onReady }: { onReady: (m: LeafletMap) => void }) {
  const map = useMap();
  useEffect(() => {
    onReady(map);
  }, [map, onReady]);
  return null;
}

export function MapView({
  onReady,
  children,
}: {
  onReady: (m: LeafletMap) => void;
  children?: React.ReactNode;
}) {
  return (
    <MapContainer
      center={[10.05, 76.35]}
      zoom={10}
      className="map"
      zoomControl={true}
      preferCanvas={false}
    >
      <TileLayer url={BASE} attribution={ATTRIB} maxZoom={16} />
      <TileLayer url={LABELS} maxZoom={16} pane="shadowPane" />
      <Expose onReady={onReady} />
      {children}
    </MapContainer>
  );
}
