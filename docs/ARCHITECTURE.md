# TerraPulse — Architecture

> Read this first. Everything else assumes you know this page.

---

## 1. What the system actually does

Given an **Area of Interest (AOI)** and two satellite scenes of it (a *before* and an *after*), the system:

1. Aligns the two scenes onto the same grid.
2. Computes spectral indices for each scene (water, vegetation, burn, built-up).
3. Differences the indices and thresholds the difference → **change mask**.
4. Turns the mask into **polygons** (one polygon = one candidate change region).
5. Classifies each polygon into an **event type** using a small trained model.
6. Combines each region with **environmental data** (rainfall, temperature, slope, elevation, prior event count) to predict a **forward-looking risk score**.
7. Runs a **rule engine** over events + risk to produce **alerts with recommendations**.
8. Serves all of it as GeoJSON over a secured REST API, rendered on an interactive map.

Steps 1–7 are the "AI-powered monitoring". Step 6 is the part that answers *"what could happen next"* — this is our differentiator and the thing judges will probe. Do not let it slip.

---

## 2. Working architecture (data flow)

```
                         ┌──────────────────────────────┐
                         │   IMAGERY PROVIDER LAYER     │
                         │  local  │  sentinel (live)   │
                         └──────────────┬───────────────┘
                                        │  before.tif, after.tif, meta
                                        ▼
   env/weather CSV ──────────►  ┌───────────────────┐
   (rain, temp, slope)          │  1. ALIGN + TILE  │
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  2. INDICES       │  NDWI, NDVI, NBR, NDBI
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  3. DETECT        │  Δindex + threshold + denoise
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  4. VECTORIZE     │  mask → polygons + stats
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  5. CLASSIFY      │  RandomForest → event_type
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  6. RISK PREDICT  │  GradientBoosting → 0..1
                                └─────────┬─────────┘
                                          ▼
                              ═══════ AnalysisResult ═══════
                                          │
                                          ▼
                                ┌───────────────────┐
                                │  7. ALERT ENGINE  │  severity + recommendations
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  FastAPI  /api/v1 │  JWT · RBAC · rate limit
                                └─────────┬─────────┘
                                          ▼
                                ┌───────────────────┐
                                │  React + Leaflet  │  map · layers · alerts
                                └───────────────────┘
```

**Steps 1–6 are Part B.** They live entirely inside `backend/app/pipeline/` and are reached through **one function**.
**Step 7, the API, security, and everything around it is Part A.**
**The React app is Part C** and talks *only* to the HTTP API — it never imports Python, never knows a pipeline exists.

---

## 3. The one seam that makes this parallelisable

Part B implements exactly this, and nothing else is allowed to cross the boundary:

```python
# backend/app/pipeline/__init__.py
from app.schemas.analysis import AnalysisRequest, AnalysisResult

def run_analysis(
    req: AnalysisRequest,
    on_progress: Callable[[int, str], None] | None = None,
) -> AnalysisResult:
    ...
```

`AnalysisRequest` and `AnalysisResult` are Pydantic models that **Part A writes and freezes in the first hour**. Part A also ships a **mock implementation** of `run_analysis` that returns hand-written but schema-valid data for one AOI.

Consequence: **Part C can build the entire frontend against real-shaped data before Part B's model exists.** Nobody is ever blocked. When B's real pipeline lands, flip `PIPELINE_MODE=real` in `.env` and the frontend does not change by one line.

This is the single most important decision in the project. Protect it.

---

## 4. File architecture

Ownership is by **folder**, so merge conflicts are structurally impossible. `A`/`B`/`C` marks the owner.

```
terrapulse/
├── README.md                          A
├── .gitignore                         A
├── .env.example                       A
├── docker-compose.yml                 A
├── Makefile                           A
├── .github/workflows/ci.yml           A
│
├── docs/
│   ├── ARCHITECTURE.md                A   ← this file
│   ├── API_CONTRACT.md                A   ← frozen in hour 1
│   ├── GIT_WORKFLOW.md                A
│   └── TIMELINE.md                    A
│
├── data/                              (git-ignored except .gitkeep + meta)
│   ├── scenes/
│   │   └── <aoi_id>/
│   │       ├── before.tif             B
│   │       ├── after.tif              B
│   │       └── meta.json              B
│   ├── env/<aoi_id>.csv               B
│   └── models/
│       ├── event_classifier.joblib    B
│       └── risk_model.joblib          B
│
├── backend/
│   ├── requirements.txt               A
│   ├── Dockerfile                     A
│   ├── app/
│   │   ├── main.py                    A   app factory, middleware wiring
│   │   ├── config.py                  A   pydantic-settings, env only
│   │   │
│   │   ├── schemas/                   A   ★ THE CONTRACT — A owns, B+C read
│   │   │   ├── common.py              A   GeoJSON types, enums, pagination
│   │   │   ├── auth.py                A
│   │   │   ├── aoi.py                 A
│   │   │   ├── analysis.py            A   AnalysisRequest / AnalysisResult
│   │   │   ├── events.py              A
│   │   │   ├── risk.py                A
│   │   │   └── alerts.py              A
│   │   │
│   │   ├── security/                  A
│   │   │   ├── passwords.py           A   bcrypt hash/verify
│   │   │   ├── tokens.py              A   JWT issue/decode
│   │   │   ├── deps.py                A   current_user, require_role
│   │   │   ├── limiter.py             A   rate limiting
│   │   │   ├── middleware.py          A   headers, request-id, body cap
│   │   │   └── paths.py               A   safe path resolution (traversal guard)
│   │   │
│   │   ├── api/
│   │   │   ├── router.py              A
│   │   │   └── routes/
│   │   │       ├── health.py          A
│   │   │       ├── auth.py            A
│   │   │       ├── aoi.py             A
│   │   │       ├── analysis.py        A
│   │   │       ├── events.py          A
│   │   │       ├── risk.py            A
│   │   │       ├── alerts.py          A
│   │   │       └── stats.py           A
│   │   │
│   │   ├── db/
│   │   │   ├── session.py             A   SQLite + SQLAlchemy
│   │   │   └── models.py              A   User, Job, Event, RiskCell, Alert, AuditLog
│   │   │
│   │   ├── services/
│   │   │   ├── jobs.py                A   background job runner + progress
│   │   │   ├── alerts.py              A   rule engine + recommendations
│   │   │   ├── store.py               A   persist AnalysisResult → db
│   │   │   └── audit.py               A
│   │   │
│   │   ├── pipeline/                  B   ★ B OWNS THIS ENTIRE FOLDER
│   │   │   ├── __init__.py            B   run_analysis()  ← the only seam
│   │   │   ├── mock.py                A   schema-valid fake result (A writes once)
│   │   │   ├── providers/
│   │   │   │   ├── base.py            B   ImageryProvider protocol
│   │   │   │   ├── local.py           B   read from data/scenes/
│   │   │   │   └── sentinel.py        B   Copernicus / Sentinel Hub adapter
│   │   │   ├── align.py               B   reproject + co-register + crop to bbox
│   │   │   ├── indices.py             B   ndwi/ndvi/nbr/ndbi
│   │   │   ├── detect.py              B   Δindex → mask
│   │   │   ├── vectorize.py           B   mask → polygons + region stats
│   │   │   ├── features.py            B   polygon + env → feature vector
│   │   │   ├── classify.py            B   load + apply event classifier
│   │   │   ├── risk.py                B   load + apply risk model, grid cells
│   │   │   ├── render.py              B   PNG overlays for the map
│   │   │   └── train/
│   │   │       ├── build_dataset.py   B
│   │   │       ├── train_classifier.py B
│   │   │       └── train_risk.py      B
│   │   │
│   │   └── static/overlays/           B   generated PNGs, served by A
│   │
│   └── tests/
│       ├── test_security.py           A
│       ├── test_contract.py           A   asserts mock + real both satisfy schema
│       └── test_pipeline.py           B
│
└── frontend/                          C   ★ C OWNS THIS ENTIRE FOLDER
    ├── package.json                   C
    ├── vite.config.ts                 C
    ├── .env.example                   C
    ├── index.html                     C
    └── src/
        ├── main.tsx                   C
        ├── App.tsx                    C
        ├── api/
        │   ├── client.ts              C   fetch wrapper, token attach, 401 retry
        │   └── types.ts               C   hand-mirrored from docs/API_CONTRACT.md
        ├── store/session.ts           C   token + user
        ├── hooks/
        │   ├── useAoiList.ts          C
        │   ├── useAnalysisJob.ts      C   POST + poll
        │   ├── useEvents.ts           C
        │   ├── useRisk.ts             C
        │   └── useAlerts.ts           C
        ├── components/
        │   ├── MapView.tsx            C   Leaflet container + layer registry
        │   ├── BeforeAfterSwipe.tsx    C
        │   ├── EventLayer.tsx         C
        │   ├── RiskLayer.tsx          C
        │   ├── LayerPanel.tsx         C
        │   ├── EventPopup.tsx         C
        │   ├── AlertsPanel.tsx        C
        │   ├── StatTiles.tsx          C
        │   ├── AoiSelector.tsx        C
        │   ├── RunAnalysisBar.tsx     C
        │   └── LoginDialog.tsx        C
        ├── pages/Dashboard.tsx        C
        └── styles/theme.css           C
```

**Shared-file rule:** the only files more than one person touches are `backend/app/schemas/*` (A writes, B+C read) and `docs/API_CONTRACT.md` (A writes). If B or C needs a schema change, they **ask A**; A edits and pushes it. Nobody else edits `schemas/`. This one rule removes ~95% of hackathon merge pain.

---

## 5. Technology choices and why

| Layer | Choice | Why this one |
|---|---|---|
| API | FastAPI + Uvicorn | Pydantic gives us the contract and validation for free; auto OpenAPI docs at `/docs` is a free demo asset |
| DB | SQLite via SQLAlchemy | Zero setup, one file, survives restarts. `DATABASE_URL` env means Postgres is a one-line swap — say that to judges |
| Raster | rasterio + numpy | Standard geospatial stack; reads Sentinel-2 GeoTIFF directly |
| Vectorize | rasterio.features + shapely | Mask → polygons in a few lines |
| ML | scikit-learn (RandomForest, GradientBoosting) | Trains in seconds on CPU, fully explainable via feature importances, cannot fail on stage |
| Auth | JWT (HS256) + bcrypt | Stateless, standard, defensible |
| Frontend | React + Vite + TypeScript | Fast HMR, types catch contract drift |
| Map | Leaflet + react-leaflet | Lighter and faster to wire than Mapbox, no API key, no billing surprise |
| Charts | Recharts | Only if time allows |

**Deliberately not using:** PostGIS, Celery/Redis, Kubernetes, a deep learning framework, a cloud account. Each would cost more hours than it earns. Have the one-line answer ready for each (see §8).

---

## 6. Security architecture (Part A)

Defence is layered, and each layer is one small file:

| Concern | Control | Where |
|---|---|---|
| Identity | JWT HS256, 30-min access token, secret from env only | `security/tokens.py` |
| Credentials | bcrypt via passlib, cost 12, never logged | `security/passwords.py` |
| Authorisation | Roles `viewer < analyst < authority`; only `analyst+` may trigger analysis, only `authority` may acknowledge alerts | `security/deps.py` |
| Brute force | Rate limit: 5/min on `/auth/login`, 10/min on `/analysis/run` | `security/limiter.py` |
| Transport | HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, restrictive CSP | `security/middleware.py` |
| CORS | Exact frontend origin from env, no wildcard, credentials off | `main.py` |
| Input | Strict Pydantic models, `extra="forbid"`, bbox range checks, `aoi_id` regex allowlist | `schemas/` |
| Path traversal | Every scene/model read goes through `safe_join()` that resolves and asserts the result is inside `DATA_DIR` | `security/paths.py` |
| DoS | 10 MB body cap, request timeout, one concurrent analysis job per user | `middleware.py`, `services/jobs.py` |
| Deserialisation | Models loaded only from repo-controlled `data/models/`; no pickle from user input | `pipeline/classify.py` |
| Traceability | Request ID on every log line; `AuditLog` row for every login, analysis run, alert ack | `services/audit.py` |
| Secrets | Env only, `.env` git-ignored, `.env.example` committed with placeholders | `config.py` |
| Supply chain | Pinned `requirements.txt`, `pip-audit` in CI | `.github/workflows/ci.yml` |

**Threat model in one sentence, for the judges:** *"This system issues public-safety warnings, so the threats that matter are a false alert injected by an unauthorised caller and a tampered model file — we address the first with authenticated role-gated write paths plus an audit trail, and the second by loading models only from a repo-controlled path."* Memorise that.

---

## 7. Event types and risk model

**Event classes** (fixed — B must not invent new ones without telling A):

| `event_type` | Primary signal |
|---|---|
| `flood` | NDWI ↑ strongly, NDVI ↓ |
| `deforestation` | NDVI ↓ strongly, NDBI ~flat |
| `wildfire_burn` | NBR ↓ strongly, NDVI ↓ |
| `urban_expansion` | NDBI ↑, NDVI ↓ moderately |
| `water_recession` | NDWI ↓ strongly |
| `no_change` | all deltas below noise floor |

**Risk score** is per grid cell (not per event), so the map can show a continuous heat layer:

- Inputs: recent index deltas in/around the cell, distance to detected event polygons, cumulative rainfall (env CSV), mean temperature, slope, elevation, land-cover proxy from NDVI/NDBI, count of prior events in that cell.
- Output: `risk_score ∈ [0,1]` → `risk_level` in `low | moderate | high | severe` at 0.25 / 0.5 / 0.75.
- Also output the top 3 **drivers** with contributions, from the model's feature importances. This single field is what makes the risk layer look intelligent rather than decorative.

**Honest framing to use with mentors:** this is a *risk-propensity* model trained on historic event/no-event cells, not a physical forecast. Say that plainly. Mentors punish overclaiming far harder than they punish modest scope.

---

## 8. Answers to the questions you will be asked

Have these ready. One or two sentences each, no hedging.

- **"Is this real satellite data?"** — Yes, Sentinel-2 L2A scenes from Copernicus. We ship cached scenes for demo reliability; the same provider interface has a live Copernicus adapter, switchable by config.
- **"Why not deep learning?"** — Spectral index differencing is the established method for this class of change and it is explainable, which matters when the output triggers an evacuation advisory. The classifier is a gradient-boosted model on physically meaningful features. A CNN is a drop-in replacement behind the same `classify()` interface.
- **"How does this scale?"** — The pipeline is stateless per AOI, so it scales horizontally. Job runner is an interface; swapping the in-process runner for a Celery worker is one file. SQLite → Postgres/PostGIS is one env var.
- **"How is it secure?"** — See §6, then give the one-sentence threat model.
- **"What's the accuracy?"** — Quote the actual held-out numbers from B's training run, and name the limitation (cloud cover, temporal gap). Never invent a number.
- **"Who uses this?"** — District disaster management authority officer: opens the dashboard, sees high-risk zones ranked, gets the alert with recommended actions, acknowledges it. That's the `authority` role in the API.

---

## 9. Definition of done, per milestone

| Milestone | Deadline | Done means |
|---|---|---|
| **M1** vertical slice | 13 Sep, 14:30 | Login works, map loads, mock analysis runs end-to-end, one polygon renders. Survives the 50% cut. |
| **M2** real detection | 13 Sep, 18:30 | Real pipeline on one real scene pair; events classified; overlay on map; one generated alert. Survives the top-25 cut. |
| **M3** full system | 14 Sep, 01:30 | Risk layer live, 3 AOIs, alerts panel, auth hardened, Docker up, README, tests green. |
| **M4** frozen build | 14 Sep, 10:30 | No new features. Screenshots, rehearsed 4-minute pitch, tagged release. |

Nothing merges to `main` unless it runs. A branch that does not run is not progress.
