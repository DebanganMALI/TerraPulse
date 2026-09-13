import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

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
      <TileLayer
        url="https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution="&copy; Esri"
      />
      <TileLayer
        url="https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
      />
      <Expose onReady={onReady} />
      {children}
    </MapContainer>
  );
}
