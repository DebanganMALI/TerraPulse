export interface Layers {
  swipe: boolean;
  mask: boolean;
  events: boolean;
  risk: boolean;
}

const ROWS: { key: keyof Layers; label: string }[] = [
  { key: "swipe", label: "Before / After" },
  { key: "mask", label: "Change mask" },
  { key: "events", label: "Events" },
  { key: "risk", label: "Risk" },
];

export function LayerPanel({
  layers,
  onChange,
  available,
}: {
  layers: Layers;
  onChange: (l: Layers) => void;
  available: Record<keyof Layers, boolean>;
}) {
  return (
    <div className="overlay-panel layer-panel">
      <h4>Layers</h4>
      {ROWS.map(({ key, label }) => (
        <label key={key} className={`toggle ${available[key] ? "" : "disabled"}`}>
          <input
            type="checkbox"
            checked={layers[key] && available[key]}
            disabled={!available[key]}
            onChange={(e) => onChange({ ...layers, [key]: e.target.checked })}
          />
          <span>{label}</span>
        </label>
      ))}
    </div>
  );
}
