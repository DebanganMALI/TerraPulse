import type { Aoi, Job, User } from "../api/types";

function Logo() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="#2f81f7" strokeWidth="2" />
      <path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18" stroke="#2f81f7" strokeWidth="1.2" opacity=".65" />
    </svg>
  );
}

export function TopBar({
  user,
  aois,
  aoiId,
  onAoi,
  job,
  onRun,
  canRun,
  healthy,
  onLogout,
}: {
  user: User;
  aois: Aoi[];
  aoiId: string;
  onAoi: (id: string) => void;
  job: Job | null;
  onRun: () => void;
  canRun: boolean;
  healthy: boolean;
  onLogout: () => void;
}) {
  const running = job?.status === "queued" || job?.status === "running";

  return (
    <header className="topbar">
      <div className="brand">
        <Logo />
        EarthShield
      </div>

      <select value={aoiId} onChange={(e) => onAoi(e.target.value)} disabled={running}>
        {aois.length === 0 && <option>Loading areas…</option>}
        {aois.map((a) => (
          <option key={a.aoi_id} value={a.aoi_id}>
            {a.name}
          </option>
        ))}
      </select>

      <button className="btn primary" onClick={onRun} disabled={running || !canRun || !aoiId}>
        {running ? "Running…" : "Run analysis"}
      </button>

      {job && (
        <div className="runbar">
          <div className="progress">
            <i style={{ width: `${job.status === "done" ? 100 : (job.progress ?? 0)}%` }} />
          </div>
          <div className="stage">
            {job.status === "failed"
              ? (job.error ?? "analysis failed")
              : job.status === "done"
                ? "complete"
                : (job.stage ?? job.status)}
          </div>
        </div>
      )}

      <div className="spacer" />

      <span className={`health-dot ${healthy ? "" : "down"}`} title={healthy ? "API online" : "API unreachable"} />
      <div className="who">
        <span>{user.display_name}</span>
        <small>{user.role}</small>
      </div>
      <button className="btn sm" onClick={onLogout}>
        Sign out
      </button>
    </header>
  );
}
