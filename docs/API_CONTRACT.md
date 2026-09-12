# API Contract — v1 (FROZEN)

**Owner: Part A.** Frozen at 13 Sep 12:00. After that, changes only by A, announced in the group chat, and only additive (new optional fields). B and C build against this document.

Base URL: `http://localhost:8000/api/v1`
Auth: `Authorization: Bearer <access_token>` on everything except `/health` and `/auth/login`.

---

## Conventions

- All timestamps: ISO 8601 UTC, e.g. `2026-09-13T14:05:00Z`.
- All geometry: RFC 7946 GeoJSON, **longitude first**, WGS84 (EPSG:4326).
- `bbox` order: `[min_lon, min_lat, max_lon, max_lat]`.
- Errors are always this shape:

```json
{ "detail": "human readable message", "code": "MACHINE_CODE", "request_id": "a1b2c3d4" }
```

Codes used: `INVALID_CREDENTIALS`, `TOKEN_EXPIRED`, `FORBIDDEN_ROLE`, `AOI_NOT_FOUND`, `JOB_NOT_FOUND`, `JOB_ALREADY_RUNNING`, `RATE_LIMITED`, `PIPELINE_FAILED`, `VALIDATION_ERROR`.

---

## Enums

```
Role          = viewer | analyst | authority
EventType     = flood | deforestation | wildfire_burn | urban_expansion | water_recession | no_change
Severity      = info | low | moderate | high | severe
RiskLevel     = low | moderate | high | severe
JobStatus     = queued | running | done | failed
Provider      = local | sentinel
```

---

## 1. Health

`GET /health` → `200`

```json
{ "status": "ok", "version": "1.0.0", "pipeline_mode": "mock", "models_loaded": false }
```

---

## 2. Auth

### `POST /auth/login`
Rate limit 5/min/IP.

```json
{ "username": "officer", "password": "..." }
```

→ `200`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": { "username": "officer", "role": "authority", "display_name": "DDMA Officer" }
}
```
→ `401 INVALID_CREDENTIALS`

### `GET /auth/me` → `200`
```json
{ "username": "officer", "role": "authority", "display_name": "DDMA Officer" }
```

**Seeded demo users** (created on first boot from env, never hardcoded in source):
`viewer/viewer`, `analyst/analyst`, `officer/officer` — passwords come from `.env`, and `.env.example` documents them.

---

## 3. AOIs

### `GET /aoi` → `200`

```json
[
  {
    "aoi_id": "kerala_flood_2018",
    "name": "Kerala Floods — Aug 2018",
    "region": "Ernakulam, Kerala",
    "bbox": [76.10, 9.80, 76.60, 10.30],
    "center": [10.05, 76.35],
    "before_date": "2018-07-20",
    "after_date": "2018-08-22",
    "provider": "local",
    "expected_event": "flood",
    "preview_before_url": "/static/overlays/kerala_flood_2018/before.png",
    "preview_after_url": "/static/overlays/kerala_flood_2018/after.png"
  }
]
```

`aoi_id` must match `^[a-z0-9_]{3,48}$`. Read from `data/scenes/<aoi_id>/meta.json`.

### `GET /aoi/{aoi_id}` → same single object, or `404 AOI_NOT_FOUND`.

---

## 4. Analysis

### `POST /analysis/run`
Requires role `analyst` or `authority`. Rate limit 10/min/user. One running job per user.

```json
{ "aoi_id": "kerala_flood_2018", "provider": "local" }
```

→ `202`
```json
{ "job_id": "job_7f3a91", "status": "queued", "aoi_id": "kerala_flood_2018", "created_at": "2026-09-13T14:05:00Z" }
```
→ `409 JOB_ALREADY_RUNNING`, `403 FORBIDDEN_ROLE`, `404 AOI_NOT_FOUND`

### `GET /analysis/{job_id}` → `200`

```json
{
  "job_id": "job_7f3a91",
  "aoi_id": "kerala_flood_2018",
  "status": "running",
  "progress": 55,
  "stage": "classifying regions",
  "started_at": "2026-09-13T14:05:01Z",
  "finished_at": null,
  "error": null,
  "counts": { "events": 0, "risk_cells": 0, "alerts": 0 }
}
```

Frontend polls this every 1500 ms until `done` or `failed`, then refetches events / risk / alerts.

---

## 5. Events — `GET /events?aoi_id=...&min_confidence=0.5`

Returns a GeoJSON `FeatureCollection`. Geometry is always `Polygon` or `MultiPolygon`.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[76.21,10.02],[76.24,10.02],[76.24,10.05],[76.21,10.05],[76.21,10.02]]] },
      "properties": {
        "event_id": "ev_kerala_flood_2018_001",
        "aoi_id": "kerala_flood_2018",
        "event_type": "flood",
        "confidence": 0.91,
        "severity": "high",
        "area_km2": 12.43,
        "centroid": [10.035, 76.225],
        "deltas": { "ndwi": 0.38, "ndvi": -0.21, "nbr": -0.04, "ndbi": 0.02 },
        "detected_at": "2026-09-13T14:05:12Z",
        "job_id": "job_7f3a91"
      }
    }
  ]
}
```

`deltas` = mean `after − before` index value inside the polygon. Keys always present; value `null` if that band was unavailable.

---

## 6. Risk — `GET /risk?aoi_id=...&min_level=moderate`

GeoJSON `FeatureCollection` of square grid cells covering the AOI.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[76.20,10.00],[76.22,10.00],[76.22,10.02],[76.20,10.02],[76.20,10.00]]] },
      "properties": {
        "cell_id": "c_0031_0012",
        "aoi_id": "kerala_flood_2018",
        "risk_score": 0.82,
        "risk_level": "severe",
        "primary_risk": "flood",
        "drivers": [
          { "name": "cumulative_rainfall_7d", "contribution": 0.41 },
          { "name": "distance_to_water_change", "contribution": 0.27 },
          { "name": "slope", "contribution": 0.14 }
        ]
      }
    }
  ]
}
```

Grid resolution is B's call, but keep the total under **~2500 cells per AOI** or Leaflet will stutter. Aim for a 40×40 grid.

---

## 7. Alerts

### `GET /alerts?aoi_id=...&min_severity=moderate` → `200`

```json
[
  {
    "alert_id": "al_0007",
    "aoi_id": "kerala_flood_2018",
    "event_type": "flood",
    "severity": "severe",
    "title": "Severe flood risk — Aluva block",
    "message": "Water extent increased by 12.4 km² since 20 Jul 2018. 3 grid cells are in the severe risk band, driven by 7-day cumulative rainfall and low terrain slope.",
    "recommendations": [
      "Pre-position rescue boats at Aluva and Perumbavoor",
      "Issue evacuation advisory for settlements within 1 km of the Periyar floodplain",
      "Verify Bhoothathankettu reservoir discharge schedule"
    ],
    "affected_area_km2": 12.43,
    "risk_cells": 3,
    "geometry": { "type": "Polygon", "coordinates": [[[76.21,10.02],[76.24,10.02],[76.24,10.05],[76.21,10.05],[76.21,10.02]]] },
    "issued_at": "2026-09-13T14:05:14Z",
    "acknowledged": false,
    "acknowledged_by": null
  }
]
```

### `POST /alerts/{alert_id}/ack`
Requires role `authority`. → `200` with the updated alert. Writes an `AuditLog` row.

---

## 8. Stats — `GET /stats?aoi_id=...`

Feeds the dashboard tiles.

```json
{
  "aoi_id": "kerala_flood_2018",
  "total_events": 14,
  "total_changed_area_km2": 41.8,
  "by_event_type": { "flood": 9, "water_recession": 2, "urban_expansion": 3 },
  "risk_distribution": { "low": 1180, "moderate": 302, "high": 96, "severe": 22 },
  "highest_risk_score": 0.91,
  "open_alerts": 4,
  "last_analysis_at": "2026-09-13T14:05:14Z"
}
```

---

## 9. Static overlays

`GET /static/overlays/<aoi_id>/<name>.png` — unauthenticated, read-only, served by FastAPI `StaticFiles` from `backend/app/static/overlays/`.

B writes these files during the pipeline run. Names B must produce, so C can hardcode them:

| File | Content |
|---|---|
| `before.png` | true-colour or false-colour render of the before scene |
| `after.png` | same for after |
| `change_mask.png` | transparent PNG, changed pixels coloured by event type |

Each PNG needs a sibling `bounds.json`: `{ "bbox": [min_lon, min_lat, max_lon, max_lat] }` so Leaflet can place it as an `ImageOverlay`.

---

## 10. The internal pipeline contract

The only Python seam between A and B.

```python
# app/schemas/analysis.py   (A writes this file)

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aoi_id: str = Field(pattern=r"^[a-z0-9_]{3,48}$")
    provider: Provider = Provider.local
    job_id: str

class DetectedEvent(BaseModel):
    event_type: EventType
    confidence: float = Field(ge=0, le=1)
    area_km2: float = Field(ge=0)
    centroid: tuple[float, float]          # (lat, lon)
    geometry: dict                          # GeoJSON Polygon/MultiPolygon
    deltas: dict[str, float | None]

class RiskCell(BaseModel):
    cell_id: str
    risk_score: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    primary_risk: EventType
    geometry: dict
    drivers: list[RiskDriver]

class AnalysisResult(BaseModel):
    aoi_id: str
    job_id: str
    events: list[DetectedEvent]
    risk_cells: list[RiskCell]
    overlays: dict[str, str]                # name -> relative static path
    model_info: dict[str, str]              # e.g. {"classifier": "rf_v2", "accuracy": "0.87"}
    warnings: list[str] = []                # e.g. "cloud cover 18% in after scene"
```

```python
# app/pipeline/__init__.py   (B writes this file)

def run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult: ...
```

**B's rules:**
- `run_analysis` must never raise for a recoverable problem. Degrade: fewer events, a `warnings` entry, still a valid `AnalysisResult`.
- Call `on_progress(percent, stage_text)` at each stage so the UI has something to show.
- Do not import anything from `app.api`, `app.db`, or `app.services`. Importing `app.schemas` and `app.config` is fine.
- `event_type` values come from the enum above. Do not add classes without telling A.

A supplies `app/pipeline/mock.py` implementing the same signature with realistic Kerala-flood-shaped output. Selection is by `PIPELINE_MODE=mock|real` in `.env`.
