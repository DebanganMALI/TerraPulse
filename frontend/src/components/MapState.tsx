export function MapState({
  running,
  stage,
  progress,
  loading,
  error,
  empty,
  onRetry,
}: {
  running: boolean;
  stage?: string;
  progress?: number;
  loading: boolean;
  error: string | null;
  empty: boolean;
  onRetry: () => void;
}) {
  if (!running && !loading && !error && !empty) return null;

  if (running) {
    return (
      <div className="map-state">
        <div className="map-state-card">
          <div className="spinner" />
          <b>Analysing</b>
          <span>{stage ?? "starting the pipeline"}</span>
          <div className="progress" style={{ marginTop: 12 }}>
            <i style={{ width: `${progress ?? 0}%` }} />
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="map-state">
        <div className="map-state-card">
          <div className="spinner" />
          <b>Loading results</b>
          <span>Fetching events, risk cells and alerts.</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="map-state">
        <div className="map-state-card interactive">
          <b style={{ color: "var(--sev-high)" }}>Could not load results</b>
          <span>{error}</span>
          <button className="btn sm" style={{ marginTop: 14 }} onClick={onRetry}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="map-state">
      <div className="map-state-card">
        <b>No analysis yet</b>
        <span>Select an area and run an analysis to detect events and score forward risk.</span>
      </div>
    </div>
  );
}
