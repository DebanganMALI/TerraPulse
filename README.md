# TerraPulse

AI-powered satellite monitoring that compares before/after imagery with environmental data to detect environmental change, classify the event, predict forward risk, and issue early warnings to authorities.

Built for Build With Bharat 2.0.

---

## Quickstart

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

copy ..\.env.example .env       # Windows  (cp on macOS/Linux)
# edit .env and set JWT_SECRET to a long random string

uvicorn app.main:app --reload
```

- API — http://localhost:8000/api/v1/health
- Interactive docs — http://localhost:8000/docs

If port 8000 is unavailable on Windows, add `--port 8080` and use that port instead.

### Demo accounts

Seeded on first boot from `.env`. Passwords are never hardcoded in source.

| user | role | can |
|---|---|---|
| `viewer` | viewer | read events, risk, alerts |
| `analyst` | analyst | the above, plus trigger analysis |
| `officer` | authority | the above, plus acknowledge alerts |

```bash
pytest -q                    # tests
ruff check app tests         # lint
python -m app.tools.check    # validate scene metadata + pipeline output
```

### Pre-integration check

Before merging pipeline work, run:

```bash
python -m app.tools.check --real
```

It validates every `data/scenes/*/meta.json` and runs the pipeline, then reports
transposed coordinates, polygons outside the AOI, a risk grid over the 2500-cell
map budget, inconsistent risk levels, missing overlays and schema drift.
`python -m app.tools.check --template` prints a valid `meta.json` to copy.

## Layout

```
backend/app/schemas/    frozen API + pipeline contract  (Part A)
backend/app/security/   auth, RBAC, headers, limits     (Part A)
backend/app/api/        routes                          (Part A)
backend/app/pipeline/   geospatial + ML                 (Part B)
frontend/               React + Leaflet dashboard       (Part C)
data/                   scenes, env data, models        (Part B)
docs/                   architecture, contract, plans
```

## Pipeline modes

`PIPELINE_MODE` in `.env` selects the implementation behind a single function:

| value | behaviour |
|---|---|
| `mock` | `app/pipeline/mock.py` — deterministic synthetic result, no imagery needed |
| `real` | `app/pipeline/__init__.py` — the real geospatial + ML pipeline |

Both satisfy the same `AnalysisResult` contract, enforced by `tests/test_contract.py`.

## Docs

Read `docs/ARCHITECTURE.md` first, then `docs/API_CONTRACT.md`.
