import { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
import L from "leaflet";
import type { RiskCollection, RiskProps } from "../api/types";
import { RISK_FILL } from "../theme";
import { renderRiskPopup } from "./popups";

export function RiskLayer({ data, version }: { data: RiskCollection; version: string }) {
  // ~1600 cells as SVG stutters on pan; canvas is the whole fix
  const renderer = useMemo(() => L.canvas({ padding: 0.3 }), []);

  return (
    <GeoJSON
      key={version}
      data={data}
      style={(f) => {
        const p = f?.properties as RiskProps | undefined;
        const s = (p && RISK_FILL[p.risk_level]) || RISK_FILL.low;
        return {
          renderer,
          color: s.color,
          fillColor: s.color,
          fillOpacity: s.fillOpacity,
          weight: 0,
        };
      }}
      onEachFeature={(f, layer) => {
        layer.bindPopup(renderRiskPopup(f.properties as RiskProps));
      }}
    />
  );
}
