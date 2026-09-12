# Part C — Frontend, Interactive Map & Demo

**Branch: `feat/frontend-map`**
**Owns:** the entire `frontend/` folder, `docs/img/`, the pitch deck, and the live demo at judging.

---

## Your role in one paragraph

You own what the judges actually see. They will spend four minutes looking at your screen and roughly zero minutes reading anyone's code. A technically weaker project with a beautiful, confident demo routinely beats a stronger one with a clunky UI — that is simply how hackathon judging works, and it means your part carries disproportionate weight in the score.

You also have the biggest structural advantage: because Part A ships a **mock pipeline** in hour one, you are **never blocked**. You can build 100% of the UI against realistic data before B's model exists. Use that. Do not sit around waiting for the backend.

You talk to the backend only over HTTP, using the shapes in `docs/API_CONTRACT.md`. You never read Python.

---

## Prerequisites

```
Node 20+
```

---

# §0 — TONIGHT (12 Sep) · ~2 hours

## 0.1 Scaffold

```bash
cd "D:/BWB Project file"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install leaflet react-leaflet
npm install -D @types/leaflet
npm run dev          # confirm http://localhost:5173 loads
```

Optional, only if you already know them: `zustand` for state, `recharts` for a trend chart. **Do not add a component library** (MUI, Chakra, Ant). You will spend more time fighting its defaults than writing CSS, and everything will look like every other hackathon project. Hand-written CSS with a small token set looks more deliberate and is faster at this scale.

## 0.2 Get a map on screen tonight

```tsx
// src/components/MapView.tsx
import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export function MapView({ children }: { children?: React.ReactNode }) {
  return (
    <MapContainer center={[10.05, 76.35]} zoom={10} className="map">
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution="&copy; OpenStreetMap, &copy; CARTO"
      />
      {children}
    </MapContainer>
  );
}
```

Two things that catch everyone:
- **`import "leaflet/dist/leaflet.css"` is mandatory.** Without it the map renders as broken grey tiles and you will waste 20 minutes.
- **The map container needs an explicit height.** `height: 100%` on a parent with no height gives you a 0px map. Set `.map { height: 100vh; width: 100%; }` and work down from there.

Leaflet centre is `[lat, lng]`. GeoJSON coordinates are `[lng, lat]`. **react-leaflet's `<GeoJSON>` component handles the conversion for you** — pass GeoJSON straight through, don't flip anything. But when you place a marker manually from an event's `centroid`, that field is already `(lat, lon)` per the contract, so it goes in as-is. Know which is which.

## 0.3 `src/api/types.ts`

Hand-transcribe every response shape from `docs/API_CONTRACT.md` into TypeScript interfaces. Yes, by hand — it takes 30 minutes and it means the compiler catches contract drift the moment A changes something.

```ts
export type EventType = "flood" | "deforestation" | "wildfire_burn"
                      | "urban_expansion" | "water_recession" | "no_change";
export type RiskLevel = "low" | "moderate" | "high" | "severe";
export type Severity  = "info" | "low" | "moderate" | "high" | "severe";
export type JobStatus = "queued" | "running" | "done" | "failed";

export interface EventProps {
  event_id: string; aoi_id: string;
  event_type: EventType; confidence: number; severity: Severity;
  area_km2: number; centroid: [number, number];
  deltas: Record<string, number | null>;
  detected_at: string; job_id: string;
}
export type EventCollection = GeoJSON.FeatureCollection<GeoJSON.Polygon, EventProps>;
// ...and the rest
```

## 0.4 API client

```ts
// src/api/client.ts
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

let token: string | null = null;
export const setToken = (t: string | null) => { token = t; };

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? res.statusText, body.code, res.status);
  }
  return res.json();
}
```

Keep the token in a module variable + React state. **Do not put it in `localStorage`** — an in-memory token is the more defensible choice (no XSS exfiltration surface), it's less code, and "we keep the access token in memory rather than localStorage" is a nice thing to have an answer for if a judge asks about the frontend's security.

## 0.5 Design tokens — 15 minutes, large payoff

Pick the palette now so you're never choosing colours at midnight. Dark basemap, so a dark UI:

```css
:root {
  --bg: #0b0f14;  --panel: #131a22;  --border: #1f2a35;
  --text: #e6edf3; --muted: #8b98a5;
  --accent: #2f81f7;

  --sev-info:     #58a6ff;
  --sev-low:      #3fb950;
  --sev-moderate: #d29922;
  --sev-high:     #f85149;
  --sev-severe:   #a32b2b;

  --ev-flood:            #2f81f7;
  --ev-deforestation:    #db6d28;
  --ev-wildfire_burn:    #f85149;
  --ev-urban_expansion:  #a371f7;
  --ev-water_recession:  #39c5cf;
  --ev-no_change:        #6e7681;
}
```

**Use these consistently**: a flood polygon, its legend swatch, its stat-tile bar, and its alert card border are all `--ev-flood`. Consistent colour semantics is the cheapest thing that makes a UI look designed rather than assembled.

Commit. Push `feat/frontend-map`.

---

# §1 — Block 1 · 11:00–12:00 · Shell

Target: app shell + `/health` round-trip + map centred on the hero AOI.

Layout — settle it now and don't revisit:

```
┌──────────────────────────────────────────────────────────┐
│  TerraPulse   [AOI ▾]  [Run Analysis]      officer ▾    │  56px topbar
├───────────────────────────────────────┬──────────────────┤
│                                       │  STAT TILES      │
│                                       ├──────────────────┤
│              MAP                      │  ALERTS          │
│                                       │  (scrollable)    │
│   [layer panel]          [legend]     │                  │
└───────────────────────────────────────┴──────────────────┘
                                          360px sidebar
```

One screen, no routing, no navigation. Everything visible at once. At judging you will not have time to navigate between pages, and a judge who has to be shown where things are has already stopped being impressed.

---

# §2 — Block 2 · 12:00–15:00 · The vertical slice (your critical block)

By 14:30 the team must be able to demo: login → pick AOI → Run → polygon appears. A has mock data ready, so **all of this is buildable right now.**

## 2.1 `LoginDialog.tsx`

Modal over a blurred map. Username + password, error text on 401. Pre-fill `officer` / the seeded password — at judging you do not want to type credentials while talking.

## 2.2 `AoiSelector.tsx`

Dropdown from `GET /aoi`. On change: fly the map to the AOI (`map.flyToBounds(bbox)`) and clear all layers.

`bbox` from the API is `[min_lon, min_lat, max_lon, max_lat]`. Leaflet's `flyToBounds` wants `[[south, west], [north, east]]` = `[[min_lat, min_lon], [max_lat, max_lon]]`. **Convert it.** This is the one place you must flip by hand.

## 2.3 `RunAnalysisBar.tsx` + `useAnalysisJob.ts`

```ts
export function useAnalysisJob() {
  const [job, setJob] = useState<Job | null>(null);

  const run = async (aoiId: string) => {
    const j = await api<Job>("/analysis/run", {
      method: "POST",
      body: JSON.stringify({ aoi_id: aoiId, provider: "local" }),
    });
    setJob(j);
    const timer = setInterval(async () => {
      const s = await api<Job>(`/analysis/${j.job_id}`);
      setJob(s);
      if (s.status === "done" || s.status === "failed") clearInterval(timer);
    }, 1500);
  };
  return { job, run };
}
```

Show the `stage` text next to the progress bar — "computing indices", "classifying regions". That live-updating stage text is a small thing that makes the system feel like it's genuinely working rather than faking a spinner. It's free: A is already sending it.

Clean up the interval on unmount, and disable the Run button while a job is in flight (the API returns `409` otherwise).

## 2.4 `EventLayer.tsx`

```tsx
<GeoJSON
  key={jobId}                              // ← forces remount when data changes
  data={events}
  style={(f) => ({
    color: EVENT_COLORS[f!.properties.event_type],
    weight: 2, fillOpacity: 0.35,
  })}
  onEachFeature={(f, layer) => layer.bindPopup(renderEventPopup(f.properties))}
/>
```

**The `key` prop is essential.** react-leaflet's `<GeoJSON>` does not re-render when `data` changes — it only reads it on mount. Without a changing `key`, your second analysis run shows the first run's polygons and you will lose half an hour to it.

**M1 gate — 14:30.** Login → AOI → Run → progress → polygons → click one → popup. Merge to `dev`. Tell A.

---

# §3 — Block 3 · 15:00–19:00 · The money shot

## 3.1 `BeforeAfterSwipe.tsx` — build this before anything else in this block

This is the single most persuasive element in the whole demo. A draggable vertical divider over the map, with the before-image on the left and the after-image on the right. Judges *see* the flood appear. No explanation needed.

Two `L.imageOverlay` layers from `GET /static/overlays/<aoi>/before.png` and `after.png`, placed using the `bbox` from the sibling `bounds.json`. Clip the top layer with a CSS `clip-path: inset(0 X% 0 0)` driven by the divider position.

```tsx
const [split, setSplit] = useState(50);
// after-layer wrapper: style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
```

Add date labels — "20 Jul 2018" on the left, "22 Aug 2018" on the right — from the AOI metadata. Small detail, makes the comparison legible instantly.

If B's PNGs aren't ready yet, build it against any two placeholder images. The mechanism is the work; swapping the URLs later takes a minute.

## 3.2 `EventPopup.tsx`

```
┌─────────────────────────────────┐
│ ▮ FLOOD              91% conf.  │
│ Area        12.43 km²           │
│ ΔNDWI       +0.38  ▲            │
│ ΔNDVI       −0.21  ▼            │
│ Severity    HIGH                │
└─────────────────────────────────┘
```

Show the deltas with arrows and colour. This is what tells a judge the classification is grounded in physical measurement rather than guessed — and it invites the good follow-up question rather than the sceptical one.

## 3.3 `StatTiles.tsx`

Four tiles from `GET /stats`: total events, changed area km², open alerts, highest risk score. Big numbers, small labels. Add a small stacked bar for `by_event_type` using the event colours.

## 3.4 `LayerPanel.tsx`

Checkboxes: Before/After · Change mask · Events · Risk. Bottom-left over the map, semi-transparent panel.

Toggling layers on and off during the demo is how you control the judges' attention. Make the toggles instant and obvious.

**M2 gate — 18:30.** Real imagery in the swipe, real polygons, working popups.

---

# §4 — Block 4 · 20:00–22:00 · Risk layer + alerts

## 4.1 `RiskLayer.tsx`

Up to 1600 grid cells from `GET /risk`. Fill by `risk_level` with graduated opacity, no stroke (strokes on a grid look like a net and hide the pattern).

```tsx
const RISK_FILL = {
  low:      { color: "#3fb950", fillOpacity: 0.12 },
  moderate: { color: "#d29922", fillOpacity: 0.30 },
  high:     { color: "#f85149", fillOpacity: 0.45 },
  severe:   { color: "#a32b2b", fillOpacity: 0.62 },
};
```

**Performance:** at 1600 polygons, plain `<GeoJSON>` is acceptable but not smooth. If it lags, pass `renderer={L.canvas()}` to the GeoJSON layer — SVG rendering is the bottleneck and canvas fixes it in one prop. Also consider hiding `low` cells by default (`?min_level=moderate`); it both performs better and reads better, since a map that's uniformly tinted green communicates nothing.

Cell click → popup showing `risk_score`, `risk_level`, `primary_risk`, and the **three drivers as labelled bars**. Those driver bars are what make the risk layer feel like a model rather than a colour ramp. Spend fifteen minutes making them look good — it is the highest-value fifteen minutes in this block.

## 4.2 `RiskLegend.tsx`

Bottom-right, four swatches with the score ranges. A heat layer without a legend is decoration; with one it is data.

## 4.3 `AlertsPanel.tsx`

Cards in the right sidebar, sorted severity-descending, from `GET /alerts`.

```
┌────────────────────────────────────────┐
│ ▌SEVERE   flood          14:05 UTC     │
│ Severe flood risk — Aluva block         │
│                                         │
│ Water extent increased by 12.4 km²      │
│ since 20 Jul. 3 cells in severe band,   │
│ driven by 7-day rainfall and low slope. │
│                                         │
│ ▸ Recommended actions (3)               │
│ ┌───────────┐  ┌──────────────────────┐ │
│ │ Zoom to   │  │ Acknowledge          │ │
│ └───────────┘  └──────────────────────┘ │
└────────────────────────────────────────┘
```

- Left border in the severity colour
- Recommendations collapsed by default, expand on click
- **Zoom to** flies the map to the alert geometry — use this at judging to move between alerts without touching the map
- **Acknowledge** calls `POST /alerts/{id}/ack`. Only visible for the `authority` role — read `role` from the session and hide the button otherwise. Then, when a judge asks about permissions, you log in as `viewer` and show the button is gone. That is a far better demonstration of RBAC than describing it.

---

# §5 — Block 5 · 22:00–01:30 · Polish

This block is what separates a demo that looks finished from one that looks like a hackathon project. Do not skip it for features.

| Time | Task |
|---|---|
| 22:00–23:00 | **States.** Every panel needs four: loading (skeleton, not a spinner), empty ("No analysis yet — select an area and run"), error (readable message + retry), populated. An empty panel with no explanation reads as broken. |
| 23:00–23:45 | **Transitions.** 150 ms fade on layer toggle, smooth `flyTo`, animated progress bar. Nothing fancy — but abrupt state changes read as unfinished. |
| 23:45–00:30 | **Consistency pass.** Same border radius, same spacing scale (4/8/12/16/24), same font sizes throughout. Pick 3 type sizes and stop. Inconsistency is the most common tell of rushed work. |
| 00:30–01:00 | **Screenshots** of every view into `docs/img/` for A's README and your deck. Do this while everything still works. |
| 01:00–01:15 | **Record the fallback video.** 90 seconds, full click path, narrated. Save to the desktop. This is your insurance. |

Also, once, before you sleep: resize the browser to ~1366×768. That is what the projector will be. If your sidebar overflows or the map collapses, fix it now. Do not bother with phone widths — nobody will look.

---

# §6 — Day 2, 09:00–11:00 · You own the pitch

**No new features.** You are the one most tempted and it is the most expensive mistake available to you.

## 6.1 Deck — 7 slides, no more

1. **Title** — TerraPulse, one line: *"AI satellite monitoring that predicts environmental risk, not just reports it."*
2. **Problem** — floods/fires/deforestation cost lives and crores; satellite data exists but manual analysis is slow and existing tools are retrospective. One number if you have a real sourced one; no number rather than an invented one.
3. **Solution** — the pipeline diagram from `ARCHITECTURE.md` §2, simplified to 5 boxes.
4. **Live demo** — a single slide that says DEMO. You switch to the browser here. This is 60% of your time.
5. **Risk prediction** — the actual differentiator. Show the driver breakdown screenshot. Say plainly it is a risk-propensity model, not a physical forecast.
6. **Engineering** — architecture + security controls table + real accuracy numbers. This is A's and B's slide content; you lay it out.
7. **Scale path** — Postgres/PostGIS swap, Celery workers, live Copernicus ingest, SMS/WhatsApp alert delivery, more event classes. Frame as *"designed for, not built"* — never imply it's done.

## 6.2 Rehearse the click path — twice, out loud, timed

The exact sequence is in `docs/TIMELINE.md` (Day 2, Judging Round). Nine steps, under four minutes. You drive the laptop.

Rehearsal rules:
- **Pre-log-in before the judges arrive.** Have the hero AOI selected and one analysis already complete in a second browser tab.
- Know which step is slowest and have a sentence to fill it — the analysis run takes ~20 seconds, so that is when you explain the pipeline.
- Practise the *recovery*: if a click does nothing, you say "one moment" and switch to the pre-loaded tab. Practise that switch so it looks intentional.
- Full screen, browser zoom at 100%, no dev tools open, no other tabs visible, notifications off.

## 6.3 Speaking split — agree this and hold it

- **You** drive the laptop and narrate the demo
- **B** takes every model / accuracy / data question
- **A** takes every architecture / security / scale question

When a question comes in, whoever owns it answers and the other two stay quiet. Three people talking over each other is the most common way a good project loses points, and it is entirely avoidable.

---

# §7 — Your checklist

**Tonight**
- [ ] Vite + React + TS running
- [ ] react-leaflet map renders with basemap (CSS imported, height set)
- [ ] `api/types.ts` transcribed from the contract
- [ ] `api/client.ts` with token attach + typed errors
- [ ] CSS tokens defined
- [ ] Pushed to `feat/frontend-map`

**Day 1**
- [ ] 12:00 — shell + `/health` + map on the hero AOI
- [ ] 14:30 — **M1**: login → AOI → Run → progress → polygons → popup
- [ ] 16:30 — before/after swipe working
- [ ] 18:30 — **M2**: real imagery + real polygons + stat tiles
- [ ] 21:00 — risk layer + legend + driver bars
- [ ] 22:00 — alerts panel with Zoom-to and Acknowledge
- [ ] 23:45 — all loading / empty / error states done
- [ ] 00:30 — screenshots in `docs/img/`
- [ ] 01:15 — fallback video recorded

**Day 2**
- [ ] 10:15 — 7 slides done
- [ ] 10:45 — click path rehearsed twice, timed under 4 minutes
- [ ] Second tab pre-loaded and pre-analysed

---

# §8 — Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Grey broken tiles | missing `leaflet/dist/leaflet.css` | Import it in `MapView.tsx` |
| Map is 0px tall | no explicit height on the container | `.map { height: 100vh }`, or an explicit px height on the parent |
| Second analysis shows the first run's polygons | `<GeoJSON>` doesn't react to `data` changes | Add `key={jobId}` |
| Polygons in the wrong hemisphere | you flipped coordinates that react-leaflet already handles | Pass GeoJSON straight through; only flip for `flyToBounds` and manual markers |
| CORS error in the console | backend origin list doesn't include `:5173` | Tell A to set `CORS_ORIGINS`. Don't try to fix it from the frontend. |
| Every call 401s | token not attached, or expired (30 min) | Check the request headers in the Network tab; re-login |
| Map stutters with the risk layer | 1600 SVG polygons | `renderer={L.canvas()}`, and/or `?min_level=moderate` |
| `409` on Run Analysis | a job is already running for that user | Disable the button while `job.status` is queued/running |
| Popup content renders as literal HTML text | `bindPopup` with a React element | `bindPopup` needs an HTML string, or use react-leaflet's `<Popup>` inside `<GeoJSON>` children |

---

# §9 — Your two non-negotiables

1. **Build everything against A's mock data starting at 12:00.** Do not wait for B. If you are idle at 15:00 because "the backend isn't ready", the project loses its most valuable hours — the mock exists precisely so that never happens.

2. **Rehearse the click path twice, out loud, with a timer.** Not mentally. Not once. The difference between a team that has rehearsed and one that hasn't is visible within ten seconds, and it is worth more points than any feature you could add in that time instead.
