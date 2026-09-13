import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Map as LeafletMap } from "leaflet";
import type { Aoi, Bounds } from "../api/types";
import { staticUrl } from "../api/client";
import { fmtDate } from "../theme";

function bboxToBounds(bbox: [number, number, number, number]) {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  return L.latLngBounds([minLat, minLon], [maxLat, maxLon]);
}

async function loadBounds(aoi: Aoi) {
  try {
    const res = await fetch(staticUrl(`/static/overlays/${aoi.aoi_id}/bounds.json`));
    if (res.ok) {
      const b = (await res.json()) as Bounds;
      if (Array.isArray(b.bbox) && b.bbox.length === 4) return bboxToBounds(b.bbox);
    }
  } catch {
    // bounds.json is B's file and may not exist yet; the AOI bbox is close enough to demo on
  }
  return bboxToBounds(aoi.bbox);
}

export function BeforeAfterSwipe({ map, aoi }: { map: LeafletMap; aoi: Aoi }) {
  const [split, setSplit] = useState(50);
  const beforeRef = useRef<L.ImageOverlay | null>(null);
  const afterRef = useRef<L.ImageOverlay | null>(null);
  const boundsRef = useRef<L.LatLngBounds | null>(null);
  const splitRef = useRef(split);
  splitRef.current = split;

  const clip = useCallback(() => {
    const img = afterRef.current?.getElement() as HTMLElement | undefined;
    const b = boundsRef.current;
    if (!img || !b) return;
    const nw = map.latLngToLayerPoint(b.getNorthWest());
    const se = map.latLngToLayerPoint(b.getSouthEast());
    const width = se.x - nw.x;
    const dividerX = map.containerPointToLayerPoint(
      L.point((splitRef.current / 100) * map.getSize().x, 0)
    ).x;
    const rel = Math.max(0, Math.min(width, dividerX - nw.x));
    img.style.clipPath = `inset(0 ${width - rel}px 0 0)`;
  }, [map]);

  useEffect(() => {
    let dead = false;
    for (const name of ["ba-before", "ba-after"]) {
      if (!map.getPane(name)) {
        const p = map.createPane(name);
        p.style.zIndex = name === "ba-before" ? "350" : "351";
      }
    }

    loadBounds(aoi).then((bounds) => {
      if (dead) return;
      boundsRef.current = bounds;
      beforeRef.current = L.imageOverlay(staticUrl(aoi.preview_before_url), bounds, {
        pane: "ba-before",
      }).addTo(map);
      afterRef.current = L.imageOverlay(staticUrl(aoi.preview_after_url), bounds, {
        pane: "ba-after",
      }).addTo(map);
      afterRef.current.once("load", clip);
      clip();
    });

    map.on("move zoom zoomend viewreset resize", clip);
    return () => {
      dead = true;
      map.off("move zoom zoomend viewreset resize", clip);
      beforeRef.current?.remove();
      afterRef.current?.remove();
      beforeRef.current = null;
      afterRef.current = null;
    };
  }, [map, aoi, clip]);

  useEffect(clip, [split, clip]);

  const startDrag = (e: React.PointerEvent) => {
    e.preventDefault();
    const host = (e.currentTarget as HTMLElement).parentElement!;
    const move = (ev: PointerEvent) => {
      const r = host.getBoundingClientRect();
      const pct = ((ev.clientX - r.left) / r.width) * 100;
      setSplit(Math.max(2, Math.min(98, pct)));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <>
      <div className="swipe-date left">BEFORE · {fmtDate(aoi.before_date)}</div>
      <div className="swipe-date right">AFTER · {fmtDate(aoi.after_date)}</div>
      <div className="swipe-handle" style={{ left: `${split}%` }} onPointerDown={startDrag}>
        <i />
      </div>
    </>
  );
}
