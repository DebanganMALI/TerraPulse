import { api } from "./client";
import type {
  Alert,
  Aoi,
  EventCollection,
  Health,
  Job,
  LoginResponse,
  RiskCollection,
  RiskLevel,
  Stats,
  User,
} from "./types";

export const getHealth = () => api<Health>("/health");

export const login = (username: string, password: string) =>
  api<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const getMe = () => api<User>("/auth/me");

export const listAois = () => api<Aoi[]>("/aoi");

export const startAnalysis = (aoi_id: string) =>
  api<Job>("/analysis/run", {
    method: "POST",
    body: JSON.stringify({ aoi_id, provider: "local" }),
  });

export const getJob = (jobId: string) => api<Job>(`/analysis/${jobId}`);

export const getEvents = (aoiId: string, minConfidence = 0.5) =>
  api<EventCollection>(`/events?aoi_id=${aoiId}&min_confidence=${minConfidence}`);

export const getRisk = (aoiId: string, minLevel: RiskLevel = "moderate") =>
  api<RiskCollection>(`/risk?aoi_id=${aoiId}&min_level=${minLevel}`);

export const getAlerts = (aoiId: string) => api<Alert[]>(`/alerts?aoi_id=${aoiId}`);

export const ackAlert = (alertId: string) =>
  api<Alert>(`/alerts/${alertId}/ack`, { method: "POST" });

export const getStats = (aoiId: string) => api<Stats>(`/stats?aoi_id=${aoiId}`);
