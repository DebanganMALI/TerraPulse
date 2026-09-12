# TerraPulse — Start Here

**Build With Bharat 2.0 · 13–14 Sep 2026 · Team of 3**

---

## First, a correction that changes the plan

On the official timeline, **"Hacking Resumes" means coding *restarts*** — resume as in resumption. It is not a résumé you need to update at each marker. There is no document due at those points.

What the timeline actually tells you is harsher: you have **~13 hours of build time** with **two elimination cuts inside it** — 50% of teams out at 15:00 on Day 1, down to the top 25 at 19:00. So the plan below is built around *having something that runs by 14:30*, not around building the best possible system.

---

## The documents

Read in this order.

| # | File | Who reads it |
|---|---|---|
| 1 | `docs/ARCHITECTURE.md` | **All three.** Working architecture, file architecture, tech choices, security model, answers to judge questions. |
| 2 | `docs/API_CONTRACT.md` | **All three.** The frozen contract. This is what lets you work in parallel. |
| 3 | `docs/GIT_WORKFLOW.md` | **All three.** Branches, exact commands, `.gitignore`, commit hygiene. |
| 4 | `docs/TIMELINE.md` | **All three.** Hour-by-hour, mapped to the official schedule. The cut list. |
| 5 | `plans/PART_A_CORE_SECURITY.md` | **Saheb** |
| 6 | `plans/PART_B_GEO_AI.md` | Teammate B |
| 7 | `plans/PART_C_FRONTEND_MAP.md` | Teammate C |

---

## The split

| Part | Owner | Owns | Deliverable |
|---|---|---|---|
| **A — Core, Security & Infra** | **Saheb** | `backend/` except `app/pipeline/` | Repo, contract, JWT auth + RBAC, job runner, alert engine, security hardening, CI, Docker, integration |
| **B — Geospatial + AI/ML** | teammate | `backend/app/pipeline/`, `data/` | Imagery providers, change detection, event classifier, risk model, overlay PNGs |
| **C — Frontend, Map & Demo** | teammate | `frontend/`, deck | Leaflet dashboard, before/after swipe, risk layer, alerts panel, the pitch |

**Ownership is by folder, so merge conflicts are structurally impossible.** The only shared files are `backend/app/schemas/*` — Saheb writes them, the others only read them.

---

## The one decision that makes this work

Part B's entire pipeline is reached through **one function**:

```python
def run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult
```

Saheb writes the `AnalysisRequest` / `AnalysisResult` schemas **tonight**, plus a **mock implementation** that returns realistic fake data. Flip `PIPELINE_MODE=mock|real` in `.env` to switch.

Consequence: **C builds the whole frontend before B's model exists.** Nobody is ever blocked waiting. Protect this.

---

## Do these five things right now, tonight (12 Sep)

### 1. Saheb — create the GitHub repo and push (30 min)

```bash
cd "D:/BWB Project file"
git init && git branch -M main
# add .gitignore from docs/GIT_WORKFLOW.md first
git add . && git commit -m "initial project skeleton and docs"
git remote add origin https://github.com/DebanganMALI/TerraPulse.git
git push -u origin main
git checkout -b dev && git push -u origin dev
git checkout -b feat/core-security && git push -u origin feat/core-security
```

Then **GitHub → Settings → Collaborators → add both teammates with write access.** Do this before you sleep or they lose tomorrow morning.

### 2. Send your teammates their plan files

B gets `PART_B_GEO_AI.md`, C gets `PART_C_FRONTEND_MAP.md`, everyone gets the four `docs/` files. Tell them: **§0 of your plan is tonight's work, it is not optional.**

### 3. Saheb — write `schemas/` and `pipeline/mock.py` (~2 h)

Part A plan §0.3 and §0.4. This is the highest-leverage code in the project. Push it to `dev` and message the group: *"schemas are on dev, build against them."*

### 4. B — download the satellite imagery (~2 h) ⚠️

**This is the single most important prep task in the whole project.** Venue wifi cannot handle 400 MB downloads at 11 AM. Three Sentinel-2 L2A scene pairs from the Copernicus Browser, cropped small, under 10% cloud. Part B plan §0.1.

Also: verify `import rasterio` works on their machine **tonight**. It's the one package that fails on Windows, and Python 3.11 (not 3.12/3.13) is required.

### 5. C — scaffold Vite + get a map rendering (~2 h)

Part C plan §0. Don't forget `import "leaflet/dist/leaflet.css"` and an explicit height on the map container.

---

## Milestones — these are the real deadlines

| | When | Must be true |
|---|---|---|
| **M1** | 13 Sep **14:30** | Login → pick AOI → Run → polygon on map. Mock data is fine. → survives the 50% cut |
| **M2** | 13 Sep **18:30** | Real Sentinel-2 imagery, real detection, classified events, one alert. → survives the top-25 cut |
| **M3** | 14 Sep **01:30** | Risk layer, 3 AOIs, alerts panel, security hardened, clean clone runs |
| **M4** | 14 Sep **10:30** | Feature freeze. Deck done, click path rehearsed twice, fallback video recorded |

**Hard integration stop at 17:30 on Day 1.** Saheb enforces it: everyone merges, the real pipeline runs end to end, whatever breaks gets fixed or reverted. Teams die by integrating at midnight and finding the coordinates were transposed.

---

## On keeping the work yours

The plans specify this in detail (`docs/GIT_WORKFLOW.md`, end section), but the short version:

- **Comments only for non-obvious decisions** — a magic threshold, a CRS gotcha, a security rationale. No narration comments (`# loop over events`), no docstrings on self-explanatory functions. Type hints instead of prose about types.
- **Many small commits** with short, lowercase, specific messages: `fix ndwi threshold`, `handle empty polygon list`. Not one 40-file commit at 01:00 called `implement complete backend` — that's the biggest tell there is.
- **No attribution trailers.** No `Co-Authored-By:`, no generated-with lines. Check `git log -1 --format=%B` after your first commit.
- **Antigravity IDE:** `.antigravity/` and similar agent config are already in the `.gitignore` — confirm nothing from the IDE is being appended to commit messages.
- Let all three of you write in your own styles. Don't standardise.

Also worth saying plainly: the plans deliberately tell you to be honest with mentors about what's mock, where your labels came from, and what the risk model is and isn't. Mentors probe hard and they punish overclaiming much more than they punish modest scope. "Detection is real, risk prediction lands tonight" scores better than a bluff that collapses under one question.

---

## Where to start reading

Saheb: `docs/ARCHITECTURE.md` → `docs/API_CONTRACT.md` → `plans/PART_A_CORE_SECURITY.md` §0, and start on the repo.
