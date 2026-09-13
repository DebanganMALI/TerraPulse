import type { EventType, Stats } from "../api/types";
import { EVENT_COLORS, EVENT_LABELS } from "../theme";

function Tile({ value, label }: { value: string; label: string }) {
  return (
    <div className="tile">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

export function StatTiles({ stats, loading }: { stats: Stats | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="stats">
        <div className="tiles">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 62 }} />
          ))}
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="stats">
        <div className="tiles">
          <Tile value="—" label="Events" />
          <Tile value="—" label="Changed km²" />
          <Tile value="—" label="Open alerts" />
          <Tile value="—" label="Peak risk" />
        </div>
      </div>
    );
  }

  const mix = Object.entries(stats.by_event_type) as [EventType, number][];
  const total = mix.reduce((s, [, n]) => s + n, 0) || 1;

  return (
    <div className="stats">
      <div className="tiles">
        <Tile value={String(stats.total_events)} label="Events" />
        <Tile value={stats.total_changed_area_km2.toFixed(1)} label="Changed km²" />
        <Tile value={String(stats.open_alerts)} label="Open alerts" />
        <Tile value={stats.highest_risk_score.toFixed(2)} label="Peak risk" />
      </div>

      {mix.length > 0 && (
        <>
          <div className="mix">
            {mix.map(([t, n]) => (
              <i
                key={t}
                style={{ flexGrow: n / total, background: EVENT_COLORS[t] ?? "#6e7681" }}
                title={`${EVENT_LABELS[t] ?? t}: ${n}`}
              />
            ))}
          </div>
          <div className="mix-key">
            {mix.map(([t, n]) => (
              <span key={t}>
                <i className="swatch" style={{ background: EVENT_COLORS[t] ?? "#6e7681" }} />
                {EVENT_LABELS[t] ?? t} {n}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
