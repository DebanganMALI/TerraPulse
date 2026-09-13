import { useCallback, useEffect, useState } from "react";
import L from "leaflet";
import type { Map as LeafletMap } from "leaflet";

import { setToken } from "./api/client";
import {
  ackAlert,
  getAlerts,
  getEvents,
  getHealth,
  getRisk,
  getStats,
  listAois,
} from "./api/endpoints";
import type {
  Alert,
  Aoi,
  EventCollection,
  EventType,
  LoginResponse,
  RiskCollection,
  Stats,
  User,
} from "./api/types";

import { useAnalysisJob } from "./hooks/useAnalysisJob";
import { MapView } from "./components/MapView";
import { TopBar } from "./components/TopBar";
import { LoginDialog } from "./components/LoginDialog";
import { EventLayer } from "./components/EventLayer";
import { RiskLayer } from "./components/RiskLayer";
import { BeforeAfterSwipe } from "./components/BeforeAfterSwipe";
import { ChangeMaskLayer } from "./components/ChangeMaskLayer";
import { LayerPanel, type Layers } from "./components/LayerPanel";
import { Legend } from "./components/Legend";
import { MapState } from "./components/MapState";
import { StatTiles } from "./components/StatTiles";
import { AlertsPanel } from "./components/AlertsPanel";

const EMPTY_LAYERS: Layers = { swipe: true, mask: false, events: true, risk: false };

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [healthy, setHealthy] = useState(true);

  const [aois, setAois] = useState<Aoi[]>([]);
  const [aoiId, setAoiId] = useState("");
  const aoi = aois.find((a) => a.aoi_id === aoiId) ?? null;

  const [map, setMap] = useState<LeafletMap | null>(null);
  const [layers, setLayers] = useState<Layers>(EMPTY_LAYERS);

  const [events, setEvents] = useState<EventCollection | null>(null);
  const [risk, setRisk] = useState<RiskCollection | null>(null);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [noImagery, setNoImagery] = useState<string | null>(null);
  const [version, setVersion] = useState("0");

  const clearResults = () => {
    setEvents(null);
    setRisk(null);
    setAlerts(null);
    setStats(null);
    setAlertsError(null);
    setResultsError(null);
  };

  const loadResults = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingResults(true);
    setAlertsError(null);
    setResultsError(null);
    const [ev, rk, al, st] = await Promise.allSettled([
      getEvents(id),
      getRisk(id, "moderate"),
      getAlerts(id),
      getStats(id),
    ]);
    setEvents(ev.status === "fulfilled" ? ev.value : null);
    if (ev.status === "rejected") setResultsError((ev.reason as Error).message);
    setRisk(rk.status === "fulfilled" ? rk.value : null);
    setAlerts(al.status === "fulfilled" ? al.value : []);
    if (al.status === "rejected") setAlertsError((al.reason as Error).message);
    setStats(st.status === "fulfilled" ? st.value : null);
    setVersion(String(Date.now()));
    setLoadingResults(false);
  }, []);

  const { job, error: jobError, run, reset } = useAnalysisJob(() => loadResults(aoiId));

  useEffect(() => {
    if (!user) return;
    getHealth()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false));
    listAois()
      .then((list) => {
        setAois(list);
        if (list.length) setAoiId((cur) => cur || list[0].aoi_id);
      })
      .catch(() => setHealthy(false));
  }, [user]);

  useEffect(() => {
    if (!map || !aoi) return;
    const [minLon, minLat, maxLon, maxLat] = aoi.bbox;
    // contract bbox is [min_lon, min_lat, max_lon, max_lat]; leaflet wants [[S,W],[N,E]]
    map.flyToBounds(L.latLngBounds([minLat, minLon], [maxLat, maxLon]), {
      padding: [24, 24],
      duration: 0.9,
    });
  }, [map, aoi]);

  useEffect(() => {
    if (!aoiId) return;
    reset();
    clearResults();
    setLayers(EMPTY_LAYERS);
    loadResults(aoiId);
  }, [aoiId, loadResults, reset]);

  const onLogin = (r: LoginResponse) => {
    setToken(r.access_token);
    setUser(r.user);
  };

  const onLogout = () => {
    setToken(null);
    setUser(null);
    setAois([]);
    setAoiId("");
    clearResults();
    reset();
  };

  const onAck = async (id: string) => {
    try {
      const updated = await ackAlert(id);
      setAlerts((cur) => (cur ?? []).map((a) => (a.alert_id === id ? updated : a)));
      setStats((s) => (s ? { ...s, open_alerts: Math.max(0, s.open_alerts - 1) } : s));
    } catch (e) {
      setAlertsError(e instanceof Error ? e.message : "Acknowledge failed.");
    }
  };

  if (!user) return <LoginDialog onSuccess={onLogin} />;

  const hasEvents = !!events?.features?.length;
  const hasRisk = !!risk?.features?.length;
  const running = job?.status === "queued" || job?.status === "running";
  const available: Record<keyof Layers, boolean> = {
    swipe: !!aoi && noImagery !== aoiId,
    mask: !!aoi && noImagery !== aoiId,
    events: hasEvents,
    risk: hasRisk,
  };
  const presentTypes = [
    ...new Set((events?.features ?? []).map((f) => f.properties.event_type)),
  ] as EventType[];

  return (
    <div className="app">
      <TopBar
        user={user}
        aois={aois}
        aoiId={aoiId}
        onAoi={setAoiId}
        job={job}
        onRun={() => run(aoiId)}
        canRun={user.role !== "viewer"}
        healthy={healthy}
        onLogout={onLogout}
      />

      <div className="body">
        <div className="map-wrap">
          <MapView onReady={setMap}>
            {layers.events && hasEvents && <EventLayer data={events!} version={"e" + version} />}
            {layers.risk && hasRisk && <RiskLayer data={risk!} version={"r" + version} />}
          </MapView>

          {map && aoi && layers.swipe && available.swipe && (
            <BeforeAfterSwipe map={map} aoi={aoi} onUnavailable={setNoImagery} />
          )}
          {map && aoi && layers.mask && available.mask && (
            <ChangeMaskLayer map={map} aoi={aoi} version={version} />
          )}

          <MapState
            running={running}
            stage={job?.stage}
            progress={job?.progress}
            loading={loadingResults}
            error={resultsError}
            empty={!hasEvents && !hasRisk}
            onRetry={() => loadResults(aoiId)}
          />

          <LayerPanel layers={layers} onChange={setLayers} available={available} />
          <Legend mode={layers.risk && hasRisk ? "risk" : "events"} present={presentTypes} />

          <div className="banners">
            {!healthy && (
              <div className="banner">
                <span style={{ color: "var(--sev-high)" }}>
                  API unreachable — start the backend on port 8000, then sign out and back in.
                </span>
              </div>
            )}
            {jobError && (
              <div className="banner">
                <span style={{ color: "var(--sev-high)" }}>{jobError}</span>
              </div>
            )}
          </div>
        </div>

        <aside className="sidebar">
          <StatTiles stats={stats} loading={loadingResults} />
          <AlertsPanel
            alerts={alerts}
            loading={loadingResults}
            error={alertsError}
            role={user.role}
            map={map}
            onAck={onAck}
            onRetry={() => loadResults(aoiId)}
          />
        </aside>
      </div>
    </div>
  );
}
