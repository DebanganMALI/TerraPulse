import { useState } from "react";
import L from "leaflet";
import type { Map as LeafletMap } from "leaflet";
import type { Alert, Role } from "../api/types";
import { EVENT_LABELS, SEVERITY_COLORS, SEVERITY_RANK, fmtTime } from "../theme";

function AlertCard({
  alert,
  role,
  map,
  onAck,
}: {
  alert: Alert;
  role: Role;
  map: LeafletMap | null;
  onAck: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [acking, setAcking] = useState(false);
  const color = SEVERITY_COLORS[alert.severity];

  const zoom = () => {
    if (!map || !alert.geometry) return;
    map.flyToBounds(L.geoJSON(alert.geometry as any).getBounds(), {
      padding: [60, 60],
      duration: 0.8,
    });
  };

  return (
    <article
      className={`alert ${alert.acknowledged ? "acked" : ""}`}
      style={{ borderLeftColor: color }}
    >
      <div className="alert-head">
        <span style={{ color }}>{alert.severity}</span>
        <span style={{ color: "var(--muted)", fontWeight: 400 }}>
          {EVENT_LABELS[alert.event_type] ?? alert.event_type}
        </span>
        <time>{fmtTime(alert.issued_at)}</time>
      </div>

      <h3>{alert.title}</h3>
      <p>{alert.message}</p>

      {alert.recommendations.length > 0 && (
        <>
          <button className="disclose" onClick={() => setOpen((o) => !o)}>
            {open ? "▾" : "▸"} Recommended actions ({alert.recommendations.length})
          </button>
          {open && (
            <ul className="recs">
              {alert.recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </>
      )}

      <div className="alert-actions">
        <button className="btn sm" onClick={zoom}>
          Zoom to
        </button>
        {role === "authority" && !alert.acknowledged && (
          <button
            className="btn sm primary"
            disabled={acking}
            onClick={async () => {
              setAcking(true);
              await onAck(alert.alert_id);
              setAcking(false);
            }}
          >
            {acking ? "Acknowledging…" : "Acknowledge"}
          </button>
        )}
        {alert.acknowledged && (
          <span style={{ color: "var(--muted)", fontSize: 11, alignSelf: "center" }}>
            Acknowledged{alert.acknowledged_by ? ` by ${alert.acknowledged_by}` : ""}
          </span>
        )}
      </div>
    </article>
  );
}

export function AlertsPanel({
  alerts,
  loading,
  error,
  role,
  map,
  onAck,
  onRetry,
}: {
  alerts: Alert[] | null;
  loading: boolean;
  error: string | null;
  role: Role;
  map: LeafletMap | null;
  onAck: (id: string) => void;
  onRetry: () => void;
}) {
  const sorted = (alerts ?? [])
    .slice()
    .sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]);

  return (
    <div className="alerts">
      <div className="panel-title">
        Alerts
        {sorted.length > 0 && <span className="count-pill">{sorted.length}</span>}
      </div>

      {loading && (
        <>
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 96 }} />
        </>
      )}

      {!loading && error && (
        <div className="state">
          <b>Could not load alerts</b>
          {error}
          <div style={{ marginTop: 12 }}>
            <button className="btn sm" onClick={onRetry}>
              Retry
            </button>
          </div>
        </div>
      )}

      {!loading && !error && sorted.length === 0 && (
        <div className="state">
          <b>No alerts yet</b>
          Select an area and run an analysis — alerts are generated from detected events and
          risk cells.
        </div>
      )}

      {!loading &&
        !error &&
        sorted.map((a) => (
          <AlertCard key={a.alert_id} alert={a} role={role} map={map} onAck={onAck} />
        ))}
    </div>
  );
}
