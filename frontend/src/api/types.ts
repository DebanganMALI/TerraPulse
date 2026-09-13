export type Role = "viewer" | "analyst" | "authority";

export type EventType =
  | "flood"
  | "deforestation"
  | "wildfire_burn"
  | "urban_expansion"
  | "water_recession"
  | "no_change";

export type Severity = "info" | "low" | "moderate" | "high" | "severe";
export type RiskLevel = "low" | "moderate" | "high" | "severe";
export type JobStatus = "queued" | "running" | "done" | "failed";
export type Provider = "local" | "sentinel";

export interface Health {
  status: string;
  version: string;
  pipeline_mode: string;
  models_loaded: boolean;
}

export interface User {
  username: string;
  role: Role;
  display_name: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Aoi {
  aoi_id: string;
  name: string;
  region: string;
  bbox: [number, number, number, number];
  center: [number, number];
  before_date: string;
  after_date: string;
  provider: Provider;
  expected_event: EventType;
  preview_before_url: string;
  preview_after_url: string;
}

export interface Job {
  job_id: string;
  aoi_id: string;
  status: JobStatus;
  progress?: number;
  stage?: string;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  counts?: { events: number; risk_cells: number; alerts: number };
}

export interface EventProps {
  event_id: string;
  aoi_id: string;
  event_type: EventType;
  confidence: number;
  severity: Severity;
  area_km2: number;
  centroid: [number, number];
  deltas: Record<string, number | null>;
  detected_at: string;
  job_id: string;
}

export interface RiskDriver {
  name: string;
  contribution: number;
}

export interface RiskProps {
  cell_id: string;
  aoi_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  primary_risk: EventType;
  drivers: RiskDriver[];
}

export type Poly = GeoJSON.Polygon | GeoJSON.MultiPolygon;
export type EventCollection = GeoJSON.FeatureCollection<Poly, EventProps>;
export type RiskCollection = GeoJSON.FeatureCollection<Poly, RiskProps>;

export interface Alert {
  alert_id: string;
  aoi_id: string;
  event_type: EventType;
  severity: Severity;
  title: string;
  message: string;
  recommendations: string[];
  affected_area_km2: number;
  risk_cells: number;
  geometry: Poly;
  issued_at: string;
  acknowledged: boolean;
  acknowledged_by: string | null;
}

export interface Stats {
  aoi_id: string;
  total_events: number;
  total_changed_area_km2: number;
  by_event_type: Partial<Record<EventType, number>>;
  risk_distribution: Record<RiskLevel, number>;
  highest_risk_score: number;
  open_alerts: number;
  last_analysis_at: string | null;
}

export interface Bounds {
  bbox: [number, number, number, number];
}
