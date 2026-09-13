import type { EventProps, RiskProps } from "../api/types";
import { EVENT_COLORS, EVENT_LABELS, driverLabel } from "../theme";

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

const DELTA_LABELS: Record<string, string> = {
  ndwi: "ΔNDWI",
  ndvi: "ΔNDVI",
  nbr: "ΔNBR",
  ndbi: "ΔNDBI",
};

function deltaRow(key: string, v: number | null) {
  const label = DELTA_LABELS[key] ?? "Δ" + key.toUpperCase();
  if (v === null || v === undefined)
    return `<div class="pop-row"><span>${esc(label)}</span><b style="color:#6e7681">n/a</b></div>`;
  const cls = v >= 0 ? "up" : "down";
  const arrow = v >= 0 ? "▲" : "▼";
  const sign = v >= 0 ? "+" : "−";
  return `<div class="pop-row"><span>${esc(label)}</span><b class="${cls}">${sign}${Math.abs(v).toFixed(2)} ${arrow}</b></div>`;
}

export function renderEventPopup(p: EventProps): string {
  const color = EVENT_COLORS[p.event_type] ?? "#6e7681";
  const deltas = Object.entries(p.deltas ?? {})
    .map(([k, v]) => deltaRow(k, v))
    .join("");
  return `
    <div class="pop-head">
      <span class="swatch" style="background:${color}"></span>
      <span style="color:${color}">${esc(EVENT_LABELS[p.event_type] ?? p.event_type)}</span>
      <em>${Math.round(p.confidence * 100)}% conf.</em>
    </div>
    <div class="pop-row"><span>Area</span><b>${p.area_km2.toFixed(2)} km²</b></div>
    ${deltas}
    <div class="pop-row"><span>Severity</span><b style="text-transform:uppercase">${esc(p.severity)}</b></div>
  `;
}

export function renderRiskPopup(p: RiskProps): string {
  const color = EVENT_COLORS[p.primary_risk] ?? "#6e7681";
  const max = Math.max(...p.drivers.map((d) => d.contribution), 0.0001);
  const bars = p.drivers
    .map(
      (d) => `
      <div class="bar">
        <em><span>${esc(driverLabel(d.name))}</span><span>${d.contribution.toFixed(2)}</span></em>
        <div><i style="width:${Math.round((d.contribution / max) * 100)}%;background:${color}"></i></div>
      </div>`
    )
    .join("");
  return `
    <div class="pop-head">
      <span class="swatch" style="background:${color}"></span>
      <span>Risk ${esc(p.risk_level)}</span>
      <em>${p.risk_score.toFixed(2)}</em>
    </div>
    <div class="pop-row"><span>Primary risk</span><b style="color:${color}">${esc(p.primary_risk)}</b></div>
    <div style="margin-top:10px;font-size:11px;letter-spacing:.6px;text-transform:uppercase;color:#8b98a5">Drivers</div>
    ${bars}
  `;
}
