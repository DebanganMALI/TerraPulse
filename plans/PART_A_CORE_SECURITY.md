# Part A — Core, Security & Infrastructure

**Owner: Saheb**
**Branch: `feat/core-security`**
**Owns:** everything in `backend/` except `app/pipeline/` (minus `pipeline/mock.py`, which is yours), plus root config, CI, Docker, docs.

---

## Your role in one paragraph

You are the spine. You define the contract that lets B and C work without waiting for each other, you run the integration checkpoints, and you own the security story that will be a large part of the judging score. Your code is mostly plumbing — the hard part of your job is **sequencing**: shipping the mock pipeline in hour one so nobody is blocked, and being ruthless at the 17:30 integration gate.

You are also the person who says no. Keep the cut list in `TIMELINE.md` open.

---

## Prerequisites

```
Python 3.11+
git
Docker Desktop (optional, only for §11 — skip if it's slow on your machine)
```

---

# §0 — TONIGHT (12 Sep) · ~2.5 hours · do not skip

The goal tonight is that B and C wake up to a repo they can immediately work in.

## 0.1 Repo and skeleton

```bash
cd "D:/BWB Project file"
mkdir -p backend/app/{schemas,security,api/routes,db,services,pipeline/providers,pipeline/train,static/overlays}
mkdir -p backend/tests data/scenes data/env data/models docs plans frontend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install "fastapi[standard]" uvicorn "pydantic>=2" pydantic-settings \
            sqlalchemy "passlib[bcrypt]" "python-jose[cryptography]" \
            python-multipart slowapi pytest httpx ruff
pip freeze > backend/requirements.txt
```

Create `__init__.py` in every folder under `backend/app/`.

Copy in `.gitignore` from `docs/GIT_WORKFLOW.md`, then do the git setup from that file and **add your teammates before you sleep.**

## 0.2 `backend/app/config.py`

```python
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TerraPulse"
    version: str = "1.0.0"
    debug: bool = False

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    database_url: str = "sqlite:///./terrapulse.db"
    cors_origins: str = "http://localhost:5173"

    data_dir: Path = Path("data")
    pipeline_mode: str = "mock"          # mock | real
    max_body_bytes: int = 10 * 1024 * 1024

    seed_viewer_password: str = "viewer"
    seed_analyst_password: str = "analyst"
    seed_authority_password: str = "officer"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def settings() -> Settings:
    return Settings()
```

`jwt_secret` has **no default** on purpose — the app refuses to boot without one. That is a deliberate security property, and a good thing to point out to judges.

`.env` (git-ignored):
```
JWT_SECRET=change-me-to-a-long-random-string
CORS_ORIGINS=http://localhost:5173
PIPELINE_MODE=mock
DEBUG=true
```

Commit `.env.example` with the same keys and placeholder values.

## 0.3 `backend/app/schemas/` — **the most important thing you write all hackathon**

Transcribe §10 of `docs/API_CONTRACT.md` into real Pydantic models. Split across `common.py`, `auth.py`, `aoi.py`, `analysis.py`, `events.py`, `risk.py`, `alerts.py`.

Rules you must follow here:
- Every request model gets `model_config = ConfigDict(extra="forbid")`. This is input validation, not style.
- Every numeric field gets bounds: `Field(ge=0, le=1)` on confidences and scores.
- `aoi_id` and `job_id` get regex patterns.
- Enums are real `enum.StrEnum`, not bare strings.

`common.py` should hold:

```python
class Role(StrEnum):
    viewer = "viewer"; analyst = "analyst"; authority = "authority"

ROLE_ORDER = {Role.viewer: 0, Role.analyst: 1, Role.authority: 2}

class EventType(StrEnum):
    flood = "flood"; deforestation = "deforestation"
    wildfire_burn = "wildfire_burn"; urban_expansion = "urban_expansion"
    water_recession = "water_recession"; no_change = "no_change"

class Severity(StrEnum):
    info = "info"; low = "low"; moderate = "moderate"; high = "high"; severe = "severe"

class RiskLevel(StrEnum):
    low = "low"; moderate = "moderate"; high = "high"; severe = "severe"

class JobStatus(StrEnum):
    queued = "queued"; running = "running"; done = "done"; failed = "failed"

class Provider(StrEnum):
    local = "local"; sentinel = "sentinel"
```

**Push `schemas/` to `dev` tonight.** Message the group: *"schemas are on dev, build against them."*

## 0.4 `backend/app/pipeline/mock.py` — unblocks C entirely

Write a `run_analysis()` that ignores the imagery and returns a hand-authored `AnalysisResult` with:
- 5–6 polygons around the Kerala AOI with realistic lat/lon (get coords from Google Maps), mixed `event_type`, confidences 0.6–0.95, areas 0.5–20 km²
- a 20×20 grid of risk cells with scores that cluster high near the flood polygons (simple distance falloff — a dozen lines of numpy or even plain Python)
- `overlays` pointing at placeholder PNG paths
- `model_info = {"classifier": "mock", "accuracy": "n/a"}`
- a 4-second `time.sleep` split across `on_progress` calls so the frontend's progress bar has something to animate

```python
def run_analysis(req, on_progress=None):
    stages = [(15, "loading scenes"), (35, "computing indices"),
              (55, "detecting change"), (75, "classifying regions"),
              (90, "scoring risk"), (100, "done")]
    for pct, text in stages:
        if on_progress: on_progress(pct, text)
        time.sleep(0.6)
    return AnalysisResult(...)
```

Make the mock data **look plausible**. C will build the entire UI against it and you will demo this at 14:00.

## 0.5 Minimal running app

`backend/app/main.py` with an app factory, `/api/v1/health`, and CORS. Verify:

```bash
cd backend
uvicorn app.main:app --reload
# open http://localhost:8000/api/v1/health and /docs
```

Commit. Push `feat/core-security`. Merge to `dev`. **Sleep.**

---

# §1 — Block 1 · 11:00–12:00 · Foundation

## 1.1 Database layer

`app/db/session.py`:

```python
engine = create_engine(settings().database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
```

`app/db/models.py` — SQLAlchemy models: `User`, `Job`, `Event`, `RiskCell`, `Alert`, `AuditLog`.

Keep geometry as a JSON `Text` column. You are not using PostGIS; you do not need spatial queries for this demo, and you should say exactly that if asked.

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(64))

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    username: Mapped[str | None]
    action: Mapped[str]                 # login | login_failed | analysis_run | alert_ack
    target: Mapped[str | None]
    request_id: Mapped[str | None]
    ip: Mapped[str | None]
```

## 1.2 Seeding

In a lifespan startup hook: `Base.metadata.create_all(engine)`, then create the three demo users from env passwords **if they don't exist**. Never hardcode a password in source.

## 1.3 AOI discovery

`app/api/routes/aoi.py` reads `data/scenes/*/meta.json` and returns the AOI list. Validate each `aoi_id` against the regex and skip anything malformed. B writes the `meta.json` files; you just read them.

**Gate at 12:00:** `/health` and `/aoi` respond, on `dev`, and C can hit them.

---

# §2 — Block 2 · 12:00–15:00 · Auth + the vertical slice

## 2.1 `security/passwords.py`

```python
_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(raw: str) -> str: return _ctx.hash(raw)
def verify_password(raw: str, hashed: str) -> bool: return _ctx.verify(raw, hashed)
```

## 2.2 `security/tokens.py`

```python
def create_access_token(username: str, role: str) -> tuple[str, int]:
    s = settings()
    ttl = s.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": username, "role": role,
        "iat": now, "exp": now + timedelta(seconds=ttl),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), ttl

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings().jwt_secret, algorithms=[settings().jwt_algorithm])
```

## 2.3 `security/deps.py`

```python
bearer = HTTPBearer(auto_error=False)

def current_user(cred=Depends(bearer), db=Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(401, detail="missing bearer token")
    try:
        payload = decode_token(cred.credentials)
    except ExpiredSignatureError:
        raise HTTPException(401, detail="token expired")
    except JWTError:
        raise HTTPException(401, detail="invalid token")
    user = db.scalar(select(User).where(User.username == payload["sub"]))
    if user is None:
        raise HTTPException(401, detail="unknown subject")
    return user

def require_role(minimum: Role):
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_ORDER[Role(user.role)] < ROLE_ORDER[minimum]:
            raise HTTPException(403, detail=f"requires {minimum} role")
        return user
    return dep
```

Note the role check uses an **ordering**, not equality. `authority` inherits everything `analyst` can do. Equality checks are how people end up with an admin who can't use the app.

## 2.4 `POST /auth/login`

- Look up user; `verify_password`
- **Always run the hash comparison even when the user doesn't exist** (compare against a dummy hash) so response timing doesn't leak which usernames are valid. Mention this to judges — it is a detail that signals you actually know security.
- Write an `AuditLog` row on both success and failure
- Return the contract shape from `API_CONTRACT.md` §2

## 2.5 Job runner — `services/jobs.py`

Simple, in-process, no Celery:

```python
def start_job(db, user, aoi_id, provider) -> Job:
    running = db.scalar(select(Job).where(Job.username == user.username,
                                          Job.status.in_(["queued", "running"])))
    if running:
        raise HTTPException(409, detail="a job is already running")
    job = Job(job_id=f"job_{secrets.token_hex(3)}", aoi_id=aoi_id,
              username=user.username, status="queued", progress=0)
    db.add(job); db.commit()
    threading.Thread(target=_run, args=(job.job_id, aoi_id, provider), daemon=True).start()
    return job
```

`_run` opens its own DB session, resolves the pipeline, calls `run_analysis` with an `on_progress` that writes `progress` + `stage` to the `Job` row, then persists the result via `services/store.py`. Wrap the whole thing in try/except and set `status="failed"` with the error message on exception — **never let a pipeline crash take down the API.**

The "one job per user" limit is both a DoS control and the reason your demo never has two analyses fighting each other.

## 2.6 Pipeline resolution

```python
def get_pipeline():
    if settings().pipeline_mode == "real":
        from app.pipeline import run_analysis
    else:
        from app.pipeline.mock import run_analysis
    return run_analysis
```

Import inside the function, not at module level, so a broken `pipeline/__init__.py` from B never stops your app from booting. That single detail will save you at least once today.

## 2.7 Read endpoints

`/events`, `/risk`, `/alerts`, `/stats` — read from SQLite, serialise to the GeoJSON shapes in the contract. All require `viewer` or above.

**M1 gate — 14:30.** With `PIPELINE_MODE=mock`: login → run → poll → events on C's map. Merge to `dev`, then `dev` → `main`, tag `demo-r1`.

---

# §3 — Block 3 · 15:00–19:00 · Alerts + flip to real

## 3.1 Alert engine — `services/alerts.py`

This is your most visible contribution. Judges read the alert text.

```python
THRESHOLDS = {
    EventType.flood:            {"area_km2": 2.0, "confidence": 0.60},
    EventType.wildfire_burn:    {"area_km2": 0.5, "confidence": 0.60},
    EventType.deforestation:    {"area_km2": 1.0, "confidence": 0.65},
    EventType.urban_expansion:  {"area_km2": 3.0, "confidence": 0.65},
    EventType.water_recession:  {"area_km2": 3.0, "confidence": 0.65},
}
```

Severity from a small matrix of (event area, max overlapping risk score, confidence) → `Severity`. Keep it as a readable table, not nested ifs.

Recommendations come from a dict keyed by `(event_type, severity)`, each holding 2–4 concrete actions. Write these to sound like a district disaster authority actually wrote them:

```python
RECOMMENDATIONS = {
  (EventType.flood, Severity.severe): [
      "Activate the district emergency operations centre",
      "Issue evacuation advisory for settlements within 1 km of the affected extent",
      "Pre-position rescue boats and confirm relief camp capacity",
      "Verify upstream reservoir discharge schedule",
  ],
  (EventType.flood, Severity.high): [
      "Place NDRF units on standby",
      "Issue public advisory against non-essential travel in the affected blocks",
      "Inspect embankments along the affected reach",
  ],
  (EventType.deforestation, Severity.high): [
      "Dispatch a forest range officer for ground verification",
      "Cross-check the area against approved felling permits",
      "Flag for satellite re-verification in the next 15-day cycle",
  ],
  ...
}
```

Fill in all event types. It is 30 minutes of writing and it makes the demo feel like a real product instead of a tech exercise.

`message` should be generated from the numbers — area, date range, risk cell count, top driver — so it reads as data-derived, not templated boilerplate.

## 3.2 `POST /alerts/{id}/ack`

`require_role(Role.authority)`, flips `acknowledged`, records `acknowledged_by`, writes an `AuditLog` row. This is step 7 of your judging click path — make sure the frontend can call it.

## 3.3 Integration checkpoint — **17:30, hard stop**

You run this. Nobody adds features.

```bash
git checkout dev && git pull
git merge feat/geo-ai --no-ff
git merge feat/frontend-map --no-ff
# set PIPELINE_MODE=real in .env
uvicorn app.main:app --reload
```

Then walk the whole click path yourself. Whatever breaks, fix it or revert it. You have until 18:30.

Most likely failures, so you recognise them fast:
- B returns `(lat, lon)` where GeoJSON wants `(lon, lat)` → polygons land in the ocean near Somalia. **Check this first.** It happens to everyone.
- B's polygon count is in the thousands → the map dies. Ask B to filter by minimum area.
- Risk cell count too high → same. Cap it server-side if you must.
- `AnalysisResult` fails validation → the Pydantic error tells you exactly which field; send B the message verbatim.

**M2 gate — 18:30.** Real imagery, real detection, real classification, visible, one alert. Tag `demo-r2`.

---

# §4 — Block 4 · 20:00–22:00 · Risk endpoints

- `/risk` with `min_level` filter; serialise `drivers` through
- `/stats` aggregations
- Alert severity now factors in overlapping risk cells (`risk_cells` count in the alert payload)
- `services/audit.py` finalised — every write path logged

Give C the numbers she needs for the stat tiles and make sure `risk_distribution` sums to the cell count. A tile that says "0 severe" when the map shows red cells is the kind of thing a judge notices.

---

# §5 — Block 5 · 22:00–01:30 · Security hardening

This block is your differentiator. Most hackathon projects have no auth at all. Budget 90 minutes and do it properly.

## 5.1 `security/middleware.py`

```python
class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = secrets.token_hex(4)
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.update({
            "X-Request-ID": rid,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Cache-Control": "no-store",
        })
        return response
```

Also a body-size middleware: reject `Content-Length > max_body_bytes` with `413` before reading the body.

The CSP above is correct for a JSON API, but it will **break `/docs`**. Either exempt the `/docs` and `/openapi.json` paths, or disable docs in production mode. Exempting is better — you want `/docs` in the demo.

## 5.2 `security/limiter.py`

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
# @limiter.limit("5/minute")  on login
# @limiter.limit("10/minute") on analysis/run
```

Register the `RateLimitExceeded` handler so it returns your standard error shape with `code: "RATE_LIMITED"`, not slowapi's default.

## 5.3 `security/paths.py` — path traversal guard

```python
def safe_join(root: Path, *parts: str) -> Path:
    target = (root / Path(*parts)).resolve()
    root = root.resolve()
    if not target.is_relative_to(root):
        raise HTTPException(400, detail="invalid path")
    return target
```

Use it for **every** filesystem read driven by a request parameter — scene files, `meta.json`, model files, overlay PNGs. Tell B to use it too in `providers/local.py`.

The `.resolve()` before the check is the part that matters: without it a symlink inside `data/` escapes the containment test. That is a good thing to say out loud at judging.

## 5.4 CORS — locked down

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,       # exact origins from env, never ["*"]
    allow_credentials=False,                 # we use bearer tokens, not cookies
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

`allow_credentials=False` is correct here and worth saying: because the token is in a header rather than a cookie, there is no CSRF surface.

## 5.5 Error handling

One `RequestValidationError` handler and one generic `Exception` handler, both returning your standard shape with `request_id`. The generic handler logs the traceback server-side and returns a **generic message** to the client — never leak a stack trace. Guard it with `if settings().debug` if you want tracebacks locally.

## 5.6 `tests/test_security.py`

Eight tests, fifteen minutes, and they are worth showing:

```
test_health_is_public
test_protected_route_rejects_missing_token
test_protected_route_rejects_tampered_token
test_expired_token_rejected
test_viewer_cannot_trigger_analysis
test_authority_can_ack_alert
test_login_is_rate_limited
test_path_traversal_rejected            # aoi_id="../../etc"
```

`tests/test_contract.py`: run both mock and real pipelines and assert the output validates as `AnalysisResult`. This catches B's drift automatically.

```bash
cd backend && pytest -q && ruff check app
```

---

# §6 — Docker, CI, README · 23:30–01:15

## 6.1 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The non-root `USER appuser` is one line and it is a real hardening measure. Point at it.

## 6.2 `docker-compose.yml`

Two services — `api` and `web` — with `data/` and `.env` mounted into the api container. A `Makefile` with `up`, `down`, `test`, `lint`, `seed` targets so the demo is `make up`.

If Docker is fighting you at midnight, **abandon it.** A working `uvicorn` + `npm run dev` demo beats a broken container. It is a nice-to-have, not a milestone.

## 6.3 `.github/workflows/ci.yml`

`ruff check` → `pytest` → `pip-audit`. Runs on push to `dev` and `main`. A green CI badge in the README is a cheap, real signal of engineering discipline.

## 6.4 README

Sections, in this order: what it does (3 sentences) → screenshot → architecture diagram → quickstart (clean clone to running, 5 commands) → API summary table → security controls table → tech stack → limitations → team. 

Write the **limitations** section honestly: cloud cover sensitivity, two-date comparison only, risk model trained on limited historical samples, cached scenes for demo. Judges trust a project with a stated limitations section considerably more than one without. It costs you nothing and it reads as maturity.

---

# §7 — Day 2, 09:00–11:00

- 09:00 clean-clone verification: `git clone` into a fresh folder, follow your own README, confirm it runs. If your README is wrong, fix the README.
- Own the **architecture slide** and the **security slide** of the deck.
- You answer all architecture / security / scale questions at judging. Rehearse §8 of `ARCHITECTURE.md` until you don't have to think.
- Keep `demo-r2` checked out in a second terminal as your fallback.

---

# §8 — Your checklist

**Tonight**
- [ ] Repo created, pushed, teammates added with write access
- [ ] `.gitignore` committed (verify `*.tif` is ignored)
- [ ] `config.py` + `.env` + `.env.example`
- [ ] All `schemas/` files pushed to `dev`
- [ ] `pipeline/mock.py` returns plausible Kerala data
- [ ] `uvicorn` boots, `/health` and `/docs` respond
- [ ] Messaged the group: schemas are on dev

**Day 1**
- [ ] 12:00 — `/aoi` live, all three can run each other's code
- [ ] 14:30 — **M1**: mock end-to-end on C's map, tagged `demo-r1`
- [ ] 17:30 — integration checkpoint run, lon/lat order verified
- [ ] 18:30 — **M2**: real pipeline, one alert, tagged `demo-r2`
- [ ] 22:00 — `/risk`, `/alerts`, `/stats` complete
- [ ] 23:30 — security hardening done, 8 tests green
- [ ] 01:15 — **M3**: clean clone runs, tagged `demo-final`

**Day 2**
- [ ] 09:30 — clean clone verified against README
- [ ] 10:45 — architecture + security slides done, rehearsed twice
- [ ] Fallback video recorded, `demo-r2` ready in a second terminal

---

# §9 — Things that will go wrong, and what to do

| Symptom | Cause | Fix |
|---|---|---|
| Polygons render in the ocean off Africa | lat/lon swapped | GeoJSON is `[lon, lat]`. Tell B. Check this at 17:30 before anything else. |
| `401` on every frontend call | C isn't attaching the header, or CORS is blocking the preflight | Check the Network tab: if the preflight `OPTIONS` fails it's CORS; if the `GET` returns 401 it's the token |
| App won't boot: `jwt_secret field required` | `.env` missing or not in `backend/` cwd | Intended behaviour. Create `.env`. |
| Map freezes | too many features | Cap risk cells at 2500 and filter events by area server-side |
| `/docs` blank after adding CSP | CSP blocks the Swagger CDN | Exempt `/docs` and `/openapi.json` from the middleware |
| `pip install rasterio` fails on Windows | no wheel for your Python | Use Python 3.11 (not 3.13). This is B's problem but you will be asked. |
| Pipeline crash kills the API | exception escaping the job thread | Your `_run` try/except was missing. This is why §2.5 wraps everything. |
| Merge conflict in `schemas/` | someone edited your files | Your version wins. Re-establish the rule in the group chat immediately. |

---

# §10 — Your two non-negotiables

1. **Ship `pipeline/mock.py` tonight.** If C is blocked waiting for B's model tomorrow, you lose 4 hours of frontend work and probably the top-25 cut. This one file is the highest-leverage thing you write.

2. **Hold the 17:30 integration stop.** Teams die by integrating at 00:30 and discovering the coordinate order is wrong with two hours left. You are the only person positioned to enforce this. Be unpopular for 20 minutes.
