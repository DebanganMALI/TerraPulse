# TerraPulse

Satellite change detection and forward risk assessment for disaster response.

TerraPulse compares two satellite passes over the same area, identifies what
changed on the ground, classifies the type of event, and scores which
surrounding areas are most exposed next. It produces a ranked list of affected
zones with area figures and recommended actions — the form a district
authority can actually act on.

Built for Build With Bharat 2.0, IEM Kolkata.

---

## The problem

Disaster response begins with a question that takes hours to answer: what
actually changed on the ground? Sentinel-2 imagery is free and arrives within
days, but converting it into "these are the wards to evacuate" is manual work
for a trained analyst. TerraPulse compresses that step to roughly ninety
seconds.

---

## What it does

| Stage | Output |
|---|---|
| **Detect** | Spectral index differencing across before/after scenes, thresholded and cleaned |
| **Classify** | Flood, water recession, deforestation, wildfire burn, urban expansion |
| **Score risk** | 1,600-cell grid over the AOI, risk propensity per cell with named drivers |
| **Alert** | Severity-ranked warnings with recommended actions, acknowledgeable by an authority |

---

## Architecture

```
Sentinel-2 scenes
      │
      ├─ align ─────────► common grid, EPSG:4326
      │
      ├─ indices ───────► NDWI · NDVI · NBR · NDBI  (before and after)
      │
      ├─ detect ────────► thresholded change mask, cloud excluded
      │
      ├─ vectorize ─────► polygons + per-region feature vectors
      │
      ├─ classify ──────► RandomForest → event type + confidence
      │
      ├─ risk ──────────► GradientBoosting → per-cell risk score
      │
      └─ render ────────► true-colour and mask overlays

              FastAPI  ──►  React + Leaflet dashboard
```

The pipeline is reached through a single function:

```python
run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult
```

Nothing in the API layer knows how detection works, and nothing in the
pipeline imports the API. That seam is what let three people build in
parallel.

### Imagery providers

Scene loading sits behind an interface with two implementations:

- `LocalProvider` — pre-downloaded GeoTIFF scenes under `data/scenes/`
- `SentinelProvider` — live Sentinel Hub / Copernicus fetch

Selected per request via the `provider` field. Adding a third source means
implementing one class.

---

## Tech stack

**Backend** — FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite
**Geospatial** — rasterio, shapely, scipy
**ML** — scikit-learn (RandomForest, GradientBoosting), joblib
**Frontend** — React 18, Vite, react-leaflet, Esri basemaps

---

## Security

| Concern | Implementation |
|---|---|
| Authentication | JWT HS256, short-lived tokens, `jti` per token |
| Password storage | bcrypt via passlib, cost factor 12 |
| Username enumeration | Constant-time login — unknown users are compared against a dummy hash |
| Authorization | Role ordering, not equality: `viewer < analyst < authority` |
| Rate limiting | slowapi, per-route limits on auth and analysis |
| Path traversal | `safe_join` resolves before containment check |
| Request size | Body capped at 10 MB by middleware |
| Headers | CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` |
| Audit | Alert acknowledgements write an audit row with actor and timestamp |

The application refuses to start without `JWT_SECRET` set. There is no
fallback signing key.

---

## Running it

**Requirements:** Python 3.11, Node 18+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export JWT_SECRET="change-me-to-something-long"
export PIPELINE_MODE=real          # 'mock' for a data-free run
uvicorn app.main:app --port 8080
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

| | |
|---|---|
| Dashboard | http://localhost:5173 |
| API docs | http://localhost:8080/docs |
| Health | http://localhost:8080/api/v1/health |

### Demo accounts

| Username | Role | Can |
|---|---|---|
| `viewer` | viewer | Read events, risk and alerts |
| `analyst` | analyst | Above, plus trigger analysis |
| `officer` | authority | Above, plus acknowledge alerts |

Passwords match the usernames by default and are overridable via
`SEED_VIEWER_PASSWORD`, `SEED_ANALYST_PASSWORD`, `SEED_AUTHORITY_PASSWORD`.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | *(required)* | Token signing key |
| `ACCESS_TOKEN_MINUTES` | `30` | Token lifetime |
| `PIPELINE_MODE` | `mock` | `mock` or `real` |
| `DATA_DIR` | `../data` | Scenes, models and environmental data |
| `DATABASE_URL` | `sqlite:///./terrapulse.db` | Database |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `RATE_LIMIT_ENABLED` | `true` | Disable for load testing |
| `SENTINEL_CLIENT_ID` | — | Required only for live fetch |
| `SENTINEL_CLIENT_SECRET` | — | Required only for live fetch |

---

## API

All routes are prefixed `/api/v1`.

| Method | Route | Role | Purpose |
|---|---|---|---|
| `GET` | `/health` | public | Liveness and pipeline mode |
| `POST` | `/auth/login` | public | Issue a token |
| `GET` | `/auth/me` | viewer | Current identity and role |
| `GET` | `/aoi` | viewer | Available areas of interest |
| `POST` | `/analysis/run` | analyst | Start a job, returns `202` |
| `GET` | `/analysis/{job_id}` | viewer | Job status and progress |
| `GET` | `/events` | viewer | Detected events as GeoJSON |
| `GET` | `/risk` | viewer | Risk grid, filterable by level |
| `GET` | `/alerts` | viewer | Generated alerts |
| `POST` | `/alerts/{id}/ack` | authority | Acknowledge, writes audit row |

One analysis job per user at a time; a second request returns `409`.

Errors use a consistent envelope:

```json
{ "detail": "...", "code": "JOB_ALREADY_RUNNING", "request_id": "08f4f009" }
```

---

## Results — Kuttanad, Alappuzha (Sept 2018)

Sentinel-2 scenes, 03 Feb 2018 against 11 Sept 2018.

| | |
|---|---|
| Change regions detected | 35 |
| Total changed area | 68.0 km² |
| Alerts raised | 7 |
| Peak risk score | 0.98 |
| Risk model AUC | 0.94 |
| Permanent water correctly excluded | 45.7% of water pixels |

The flood footprint matches the recorded inundation of the Kuttanad
backwaters. Vembanad Lake is water in both scenes and is not flagged.

### On the classifier's accuracy

The event classifier was bootstrapped from rule-derived labels, so its own
accuracy score is circular — it measures whether the forest reproduces the
rules it was trained on. We do not quote it. The figures above that we do
quote are the risk model AUC, which is trained on pre-event land cover against
observed change, and the footprint and permanent-water checks.

---

## Known limitations

**Rainfall contributes nothing to the risk model.** The environmental series
is one station per AOI, so the value is constant across all 1,600 cells and
carries no gradient. The 0.94 AUC comes from pre-event land cover. Fixing this
needs gridded precipitation (IMD or GPM), not a model change — the feature
slot already exists.

**Single AOI validated.** Detection thresholds are tuned for this scene, not
proven universal.

**Risk is propensity, not forecast.** The model ranks relative exposure from
terrain, recent change and land cover. It is not a hydrological simulation and
should not be read as one.

---

## Testing

```bash
cd backend
export JWT_SECRET="test-secret"
pytest -q
ruff check .
```

Tests run against the mock pipeline and complete in under a second. Do not set
`PIPELINE_MODE=real` when running them — the flow tests assert mock timing.

A contract checker validates real pipeline output before integration:

```bash
python -m app.tools.check --real
```

It catches the failure that costs the most time in a parallel build:
transposed latitude and longitude. GeoJSON geometry is `[lon, lat]`; the
`centroid` field is `(lat, lon)`.

---

## Repository layout

```
backend/
  app/
    api/routes/      HTTP layer
    schemas/         Pydantic contracts, frozen early
    security/        auth, RBAC, path safety, headers
    services/        jobs, alerts, AOI, audit
    pipeline/        geospatial + ML
      providers/     local and Sentinel scene loaders
      train/         dataset build and model training
    tools/check.py   pre-integration contract checker
  tests/
frontend/
  src/
    api/             typed client
    components/      map, layers, panels
data/
  scenes/            GeoTIFF imagery + meta.json per AOI
  models/            trained joblib models
  env/               environmental series per AOI
docs/
  API_CONTRACT.md    frozen v1 contract
  ARCHITECTURE.md    data flow and file ownership
  GIT_WORKFLOW.md    branch model
```

---

## Roadmap

- Gridded precipitation, making rainfall a real driver and enabling scenario sliders
- CNN change detector behind the existing provider interface
- Live Copernicus ingestion
- Population overlay so risk is expressed in people, not km²

---

## Team

| | |
|---|---|
| Saheb | Core API, security, infrastructure, integration |
| — | Geospatial pipeline, models |
| — | Frontend, map, visualization |
