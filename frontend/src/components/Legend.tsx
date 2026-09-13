import type { EventType } from "../api/types";
import { EVENT_COLORS, EVENT_LABELS, RISK_FILL, RISK_RANGES } from "../theme";

export function Legend({
  mode,
  present,
}: {
  mode: "events" | "risk";
  present: EventType[];
}) {
  if (mode === "risk") {
    return (
      <div className="overlay-panel legend">
        <h4>Risk score</h4>
        {(["severe", "high", "moderate", "low"] as const).map((lvl) => (
          <div key={lvl} className="legend-row">
            <i
              className="swatch"
              style={{
                background: RISK_FILL[lvl].color,
                opacity: 0.35 + RISK_FILL[lvl].fillOpacity,
              }}
            />
            <span style={{ textTransform: "capitalize" }}>{lvl}</span>
            <span>{RISK_RANGES[lvl]}</span>
          </div>
        ))}
      </div>
    );
  }

  const types = present.length ? present : (["flood"] as EventType[]);
  return (
    <div className="overlay-panel legend">
      <h4>Detected events</h4>
      {types.map((t) => (
        <div key={t} className="legend-row">
          <i className="swatch" style={{ background: EVENT_COLORS[t] }} />
          <span>{EVENT_LABELS[t] ?? t}</span>
        </div>
      ))}
    </div>
  );
}
