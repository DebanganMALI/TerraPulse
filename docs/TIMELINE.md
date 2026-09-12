# Execution Timeline — mapped to Build With Bharat 2.0

## Read this first

Two things about the official schedule that change how you should plan:

1. **"Hacking Resumes" means coding *restarts*** — resume as in resumption. It is not a résumé to update. There is no document you need to produce at each of those markers.
2. **You get ~13 hours of wall-clock build time, and two elimination cuts inside it.** Mentor Round 1 ends at 15:00 and takes out 50% of teams. Mentor Round 2 ends at 19:00 and cuts down to the top 25. Both happen *while you are still building*.

The strategy that follows from #2: **have something that runs, very early.** A team with a rough working demo at 14:00 beats a team with beautiful half-finished architecture. Ambition is for after 19:00.

---

## The official schedule, and what we actually do in each block

### Tonight — 12 Sep (before you sleep) ⚠️ non-negotiable

This is the highest-leverage 3 hours of the whole hackathon. Venue wifi will be bad and you cannot download 400 MB scenes at 11 AM tomorrow.

| Who | Task |
|---|---|
| **Saheb (A)** | Create the GitHub repo, push skeleton + these docs, add teammates. Write `schemas/` and `pipeline/mock.py`. See Part A plan §0. |
| **B** | Download **3 scene pairs** from the Copernicus Browser. Put them in `data/scenes/`. Verify each opens in rasterio. See Part B plan §0. |
| **C** | `npm create vite@latest`, install react-leaflet, get a blank map rendering with a basemap. See Part C plan §0. |
| **All** | Install everything. Python 3.11+, Node 20+, git. Verify `pip install rasterio` succeeds *on your own machine* — it is the one package that fails. |

If you do only one thing tonight: **B downloads the imagery.** Everything else can be recovered tomorrow. That cannot.

---

### Day 1 — 13 Sep

#### 08:30–09:30 · Registration
Dead time. Use it: pull the repo, run the app once, confirm all three laptops work on venue wifi.

#### 09:30–11:00 · Inauguration Ceremony
You are sitting in a hall. Not dead time — **plan on paper.** All three of you agree on: the 4-minute pitch narrative, which AOI is the hero demo, and who says what to mentors. Write it in a note. Do not code on your phone.

#### 11:00–12:00 · Hackathon Begins — **Block 1: wire the skeleton (1h)**

| A | B | C |
|---|---|---|
| Repo live, `/health` up, `.env` set, `schemas/` pushed to `dev` | `local` provider reads a GeoTIFF, prints shape + CRS | Vite app talks to `/health`, map centred on hero AOI |

**Gate at 12:00:** all three can run the other two's code. If not, fix that before writing another line.

#### 12:00–15:00 · Mentor Round 1 (lunch 13:00) — **Block 2: vertical slice (~2.5h working)**

Target: **M1 — end-to-end on mock data.**

| A | B | C |
|---|---|---|
| Login + JWT + `/aoi` + `/analysis/run` + `/events` returning **mock** data | `indices.py` + `detect.py` on one real pair, dump a mask PNG to eyeball | Login dialog, AOI selector, "Run analysis" button, events render as polygons |

**By 14:30 you must be able to:** log in → pick Kerala → click Run → see a polygon on the map. Mock data is completely fine. This is what gets you past the 50% cut.

**Mentor pitch at this round** (60 seconds, rehearse it once at 14:20):
> "Satellite change detection that doesn't just report what happened — it predicts what's next. We're differencing Sentinel-2 spectral indices to find floods, deforestation and urban sprawl, classifying each region with a trained model, then scoring forward risk against rainfall and terrain. Here's the pipeline running end to end. The detection layer lands in the next block; risk prediction by tonight."

Show the running app. Name what is mock. **Mentors respect honesty and punish bluffing** — and they will ask.

#### 15:00–19:00 · Hacking Resumes + Mentor Round 2 — **Block 3: make it real (~3.5h)**

Target: **M2 — real detection and classification on real imagery.** This block decides whether you make the top 25.

| A | B | C |
|---|---|---|
| `PIPELINE_MODE=real` switch, job runner + progress, persist results to SQLite, alert rule engine v1 | `vectorize.py` → polygons, train the event classifier, wire `run_analysis()` for real | Before/after swipe, change-mask `ImageOverlay`, event popups, stat tiles |

**Integration checkpoint at 17:30 — hard stop.** Everyone merges to `dev`. A runs the real pipeline end to end. Fix whatever breaks. Do not add features between 17:30 and 18:30.

**By 18:30:** real Sentinel-2 imagery → real detected polygons → classified event types → visible on the map → one generated alert. Tag `demo-r2`.

**Mentor pitch at this round** (90 seconds): lead with the live before/after swipe, then the classified polygons, then say *"risk prediction and the alerting layer land tonight"*. Have your accuracy number ready — the real one from B's training output.

#### 19:00–20:00 · Dinner Break
Eat properly. Do not code at the table. Use it to decide the **cut list**: what you are officially not building. Write it down. Discipline here is worth two hours later.

#### 20:00–22:00 · (gap in the published schedule) — **Block 4: risk layer (~2h)**

Treat this as build time; if the organisers run a session, it becomes buffer.

Target: **risk prediction working.** This is the part that makes the project novel — protect its time.

| A | B | C |
|---|---|---|
| `/risk`, `/alerts`, `/stats`; alert recommendations per event type; audit log | Risk grid + `risk.py` + train the risk model + `drivers` output | Risk heat layer with legend, alerts panel, layer toggles |

#### 22:00–01:30 · Hacking Resumes — **Block 5: harden and polish (3.5h)**

Target: **M3 — the full system.**

| Time | A | B | C |
|---|---|---|---|
| 22:00–23:30 | Security hardening pass: rate limits, headers, safe paths, RBAC tests | Run all 3 AOIs, tune thresholds so each one looks convincing | Polish: loading states, empty states, error toasts, mobile-ish layout |
| 23:30–00:30 | Dockerfile + compose, `make up` works from clean clone | `model_info` + `warnings` populated; write down real accuracy numbers | Dashboard layout final, colour-code by severity |
| 00:30–01:30 | README, architecture diagram, tests green, merge `dev` → `main` | Help C, or a stretch item from the cut list | Screenshots of every screen, saved to `docs/img/` |

**01:15 — hard freeze.** Merge everything. Tag `demo-final`. Verify a **clean clone runs**: `git clone`, `make up`, log in, run analysis. If that fails, fix only that.

Sleep. All three of you. A team that sleeps 5 hours pitches better than a team that sleeps 2 — and the judging is the only thing that counts.

---

### Day 2 — 14 Sep

#### 09:00–11:00 · Hacking Resumes — **Block 6: NO NEW FEATURES (2h)**

This is the block teams lose. Write it on paper: **feature freeze is in effect.**

| Time | Everyone |
|---|---|
| 09:00–09:30 | Clean clone, run, verify. Fix only what is broken. |
| 09:30–10:15 | Build the pitch: 6–8 slides max. Problem → why existing tools fall short → architecture diagram → live demo → risk prediction → security → scale path → team. |
| 10:15–10:45 | **Full rehearsal, twice, out loud, with a timer.** Whoever drives the laptop practises the click path until it is muscle memory. |
| 10:45–11:00 | Contingency: screen-record a 90-second demo video and keep it on the desktop. Open the app in a second browser tab, pre-logged-in, pre-analysed. If live fails, you play the video and keep talking. |

#### 11:00–13:00 · Judging Round

**Click path — memorise this exact sequence:**

1. Login as `officer` (say: *"role-based access, this is the authority role"*)
2. AOI selector → Kerala Floods 2018
3. Before/after swipe — let them see the flood with their own eyes
4. Run Analysis → watch the progress stages tick
5. Event polygons appear → click one → popup shows `flood`, confidence, area, ΔNDWI
6. Toggle the risk layer → *"this is the part that's forward-looking"* → click a severe cell → show the 3 drivers
7. Alerts panel → open the severe alert → read one recommendation aloud → click Acknowledge
8. `/docs` tab → *"fully documented OpenAPI, JWT-secured, audit-logged"*
9. Close: one sentence on the scale path

Nine steps, under four minutes. Practise until you can do it while talking.

**Division of speaking:** C drives the laptop and narrates the demo. B answers all model/accuracy questions. A answers all architecture/security/scale questions. Agree this now — three people talking over each other is the most common way good projects lose.

#### 13:00–14:30 · Result Evaluation + Closing
Done. Push the final `main`, make the repo public if you want it on your CV.

---

## Time budget, honestly

| Block | Hours | Cumulative |
|---|---|---|
| Tonight (prep) | 3 | 3 |
| Block 1 (11:00) | 1 | 4 |
| Block 2 (12:00, mentor-interrupted) | 2.5 | 6.5 |
| Block 3 (15:00, mentor-interrupted) | 3.5 | 10 |
| Block 4 (20:00) | 2 | 12 |
| Block 5 (22:00) | 3.5 | 15.5 |
| Block 6 (Day 2, no features) | 2 | 17.5 |

**~13 hours of feature work.** Per person, that is about 13 hours of focused solo work — not 39, because integration and mentor rounds eat into all three of you at once.

## The cut list — what we are NOT building

Decide this now, not at midnight. If someone proposes one of these, the answer is a flat no.

- ❌ User registration / password reset / email
- ❌ Live Sentinel API as the demo path (adapter exists, demo uses cached scenes)
- ❌ Deep learning / U-Net / training on GPU
- ❌ PostGIS, Redis, Celery, Kubernetes
- ❌ Mobile app
- ❌ SMS/WhatsApp alert delivery (*say* it's a one-file integration — don't build it)
- ❌ Historical time-series beyond two dates
- ❌ Multi-tenant orgs
- ❌ Test coverage beyond the security tests and one contract test

**Stretch items, only if you are genuinely ahead at 00:30:** a third scene pair; a small Recharts trend panel; a downloadable PDF alert brief; a live Copernicus fetch button behind a feature flag.
