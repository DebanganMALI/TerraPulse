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
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution="&copy; OpenStreetMap, &copy; CARTO"
      />
      <Expose onReady={onReady} />
      {children}
    </MapContainer>
  );
}
