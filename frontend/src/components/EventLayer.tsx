import { GeoJSON } from "react-leaflet";
import type { EventCollection, EventProps } from "../api/types";
import { EVENT_COLORS } from "../theme";
import { renderEventPopup } from "./popups";

export function EventLayer({ data, version }: { data: EventCollection; version: string }) {
  return (
    <GeoJSON
      // <GeoJSON> reads `data` once on mount, so a changing key is what refreshes it
      key={version}
      data={data}
      style={(f) => ({
        color: EVENT_COLORS[(f?.properties as EventProps)?.event_type] ?? "#6e7681",
        weight: 2,
        fillOpacity: 0.35,
      })}
      onEachFeature={(f, layer) => {
        layer.bindPopup(renderEventPopup(f.properties), { closeButton: true });
        layer.on("mouseover", () => (layer as any).setStyle({ weight: 3, fillOpacity: 0.5 }));
        layer.on("mouseout", () => (layer as any).setStyle({ weight: 2, fillOpacity: 0.35 }));
      }}
    />
  );
}
