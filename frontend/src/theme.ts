import type { EventType, RiskLevel, Severity } from "./api/types";

export const EVENT_COLORS: Record<EventType, string> = {
  flood: "#2f81f7",
  deforestation: "#db6d28",
  wildfire_burn: "#f85149",
  urban_expansion: "#a371f7",
  water_recession: "#39c5cf",
  no_change: "#6e7681",
};

export const EVENT_LABELS: Record<EventType, string> = {
  flood: "Flood",
  deforestation: "Deforestation",
  wildfire_burn: "Wildfire burn",
  urban_expansion: "Urban expansion",
  water_recession: "Water recession",
  no_change: "No change",
};

export const SEVERITY_COLORS: Record<Severity, string> = {
  info: "#58a6ff",
  low: "#3fb950",
  moderate: "#d29922",
  high: "#f85149",
  severe: "#a32b2b",
};

export const SEVERITY_RANK: Record<Severity, number> = {
  info: 0,
  low: 1,
  moderate: 2,
  high: 3,
  severe: 4,
};

export const RISK_FILL: Record<RiskLevel, { color: string; fillOpacity: number }> = {
  low: { color: "#3fb950", fillOpacity: 0.12 },
  moderate: { color: "#d29922", fillOpacity: 0.3 },
  high: { color: "#f85149", fillOpacity: 0.45 },
  severe: { color: "#a32b2b", fillOpacity: 0.62 },
};

export const RISK_RANGES: Record<RiskLevel, string> = {
  low: "0.00 – 0.35",
  moderate: "0.35 – 0.55",
  high: "0.55 – 0.75",
  severe: "0.75 – 1.00",
};

export const DRIVER_LABELS: Record<string, string> = {
  cumulative_rainfall_7d: "7-day rainfall",
  distance_to_water_change: "Distance to water change",
  slope: "Terrain slope",
  elevation: "Elevation",
  land_cover: "Land cover",
  ndvi_loss: "NDVI loss",
  built_up_density: "Built-up density",
};

export const driverLabel = (name: string) =>
  DRIVER_LABELS[name] ?? name.replace(/_/g, " ");

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) + " UTC";
