import { useEffect } from "react";
import L from "leaflet";
import type { Map as LeafletMap } from "leaflet";
import type { Aoi } from "../api/types";
import { staticUrl } from "../api/client";

export function ChangeMaskLayer({
  map,
  aoi,
  version,
}: {
  map: LeafletMap;
  aoi: Aoi;
  version: string;
}) {
  useEffect(() => {
    if (!map.getPane("mask")) {
      const p = map.createPane("mask");
      p.style.zIndex = "360";
    }
    const [minLon, minLat, maxLon, maxLat] = aoi.bbox;
    const overlay = L.imageOverlay(
      staticUrl(`/static/overlays/${aoi.aoi_id}/change_mask.png?v=${version}`),
      L.latLngBounds([minLat, minLon], [maxLat, maxLon]),
      { pane: "mask", opacity: 0.75 }
    ).addTo(map);
    return () => {
      overlay.remove();
    };
  }, [map, aoi, version]);

  return null;
}
