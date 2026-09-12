# Part B — Geospatial Pipeline & AI/ML Engine

**Branch: `feat/geo-ai`**
**Owns:** `backend/app/pipeline/` (everything except `mock.py`), `data/scenes/`, `data/env/`, `data/models/`, `backend/tests/test_pipeline.py`, `backend/app/static/overlays/`

---

## Your role in one paragraph

You are the technical heart. Everything the judges find *interesting* comes from your folder: real Sentinel-2 imagery, actual change detection, a trained classifier, and the forward-looking risk model. You are also the highest-risk part of the project, because imagery is heavy and geospatial libraries are finic. Your job is therefore as much about **de-risking early** as it is about modelling.

You talk to the rest of the system through exactly **one function**. Read `docs/API_CONTRACT.md` §10 before you write a line.

```python
# backend/app/pipeline/__init__.py
def run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult: ...
```

Nothing else. Do not import `app.api`, `app.db`, or `app.services`. `app.schemas` and `app.config` are fine.

---

## Prerequisites

```
Python 3.11    ← NOT 3.12 or 3.13. rasterio wheels lag behind.
```

```bash
pip install rasterio shapely numpy scikit-learn joblib pillow matplotlib scipy pandas
```

**Verify `import rasterio` works tonight.** It is the one package that fails on Windows. If the pip wheel fails:
1. Try `pip install rasterio --only-binary :all:`
2. Failing that, download the matching wheel from the Gohlke unofficial-binaries mirror and `pip install <file>.whl`
3. Failing that, use conda: `conda install -c conda-forge rasterio`

Do not discover this at 11:15 tomorrow.

---

# §0 — TONIGHT (12 Sep) · ~3 hours · THE MOST IMPORTANT PREP IN THE PROJECT

**If you do nothing else tonight, download the imagery.** Venue wifi cannot be trusted with 400 MB downloads, and without scenes there is no project.

## 0.1 Get three scene pairs

Use the **Copernicus Browser** (`browser.dataspace.copernicus.eu`) — free, no card, instant sign-up. Sentinel-2 **L2A** (already atmospherically corrected; L1C makes you do more work).

For each AOI you need a *before* and an *after* scene: same area, both with **< 10% cloud cover**, a few weeks to a few months apart.

| Priority | AOI | What to search | Why |
|---|---|---|---|
| **1 — hero demo** | Kerala floods, Aug 2018 | Ernakulam / Periyar river. Before: ~20 Jul 2018. After: ~22 Aug 2018 | Dramatic, unambiguous NDWI signal. Indian context. This is the one you demo. |
| **2** | Deforestation | A Jharkhand / Chhattisgarh forest block, ~18 months apart | Clean NDVI drop, different event class |
| **3** | Urban expansion | Outer Kolkata / New Town, 2019 vs 2024 | NDBI increase, shows range. Local — good story. |

Download the bands you need (not the whole product): **B02 (blue), B03 (green), B04 (red), B08 (NIR), B11 (SWIR)**. Use the browser's download-as-GeoTIFF option and crop to a small bounding box — a 15×15 km window is plenty and keeps files under ~50 MB. Resist downloading a full 110×110 km tile; it will make everything slow all day.

Layout:

```
data/scenes/kerala_flood_2018/
    before.tif          # multiband stack, or before_B03.tif etc.
    after.tif
    meta.json
data/env/kerala_flood_2018.csv
```

`meta.json` — this is the file Part A reads to build the AOI list, so match the contract exactly:

```json
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
  "band_map": { "blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5 }
}
```

`aoi_id` must match `^[a-z0-9_]{3,48}$`. `bbox` is `[min_lon, min_lat, max_lon, max_lat]`.

`band_map` is yours to define but keep it consistent across scenes — it is what stops you hardcoding band indices in five different files.

## 0.2 Environmental data

For each AOI, a small CSV. Hand-typing 20 rows from a public weather source is completely acceptable and takes 10 minutes per AOI.

```csv
date,rainfall_mm,temp_max_c,temp_min_c,humidity_pct
2018-07-20,12.4,31.2,24.8,82
2018-07-21,48.1,29.8,24.1,89
...
```

You also want static terrain features. Two options, in order of preference:
- Download a small SRTM/Copernicus DEM tile for the AOI → compute slope with `scipy.ndimage` gradients
- If that fights you: skip elevation, and note it as a limitation. The risk model works without it, just less well.

## 0.3 Smoke test — prove the data opens

```python
import rasterio, numpy as np
with rasterio.open("data/scenes/kerala_flood_2018/before.tif") as src:
    print(src.count, src.shape, src.crs, src.bounds, src.dtypes)
    a = src.read(1)
    print(a.min(), a.max(), a.dtype)
```

Check: CRS is set (probably a UTM zone, not 4326 — that's fine, you'll reproject), the array is not all zeros, and `before.tif` and `after.tif` have the **same shape and CRS**. If shapes differ, `align.py` handles it — but knowing tonight is better than finding out tomorrow.

Commit `meta.json` and the CSVs. **Do not commit the `.tif` files** — they're git-ignored, and you'll share them by USB stick or a shared Drive folder. Do that tonight too, so A and C have them locally.

---

# §1 — Block 1 · 11:00–12:00 · Provider layer

## `providers/base.py`

```python
class SceneBundle(NamedTuple):
    before: np.ndarray          # (bands, h, w), float32, reflectance 0..1
    after: np.ndarray
    transform: Affine
    crs: CRS
    band_map: dict[str, int]
    meta: dict

class ImageryProvider(Protocol):
    def load(self, aoi_id: str) -> SceneBundle: ...
```

## `providers/local.py`

Reads from `data/scenes/<aoi_id>/`. Two rules:
- Resolve the path through Part A's `safe_join()` from `app.security.paths` — never `Path(data_dir) / aoi_id` directly. `aoi_id` comes from an HTTP request.
- Sentinel-2 L2A DNs are scaled by 10000. Divide by 10000 and clip to `[0, 1]` so your index maths is in physical reflectance units. Getting this wrong silently breaks every threshold you tune later.

## `providers/sentinel.py` — the "live" adapter

Build the **interface and the config plumbing** now, real network calls only if you have spare time after 00:30.

```python
class SentinelProvider:
    def __init__(self, client_id: str, client_secret: str): ...
    def load(self, aoi_id: str) -> SceneBundle:
        # OAuth2 client-credentials -> token
        # POST to the Sentinel Hub Process API with the AOI bbox + two date windows
        # returns GeoTIFF bytes -> rasterio.MemoryFile -> SceneBundle
```

Read credentials from env via `app.config`. Register both providers in a dict so `provider="sentinel"` in the request picks it up. Even unimplemented, having the class, the config keys, and the registry lets you say truthfully: *"the provider layer is pluggable; local is the demo path, the Copernicus adapter uses the same interface."* That is a legitimate architectural claim. Do **not** claim it works if it doesn't.

---

# §2 — Block 2 · 12:00–15:00 · Detection

## 2.1 `align.py`

```python
def align(bundle: SceneBundle) -> SceneBundle:
    # reproject both to EPSG:4326 if not already
    # crop both to the intersection of their extents
    # resample after -> before's grid (bilinear) so shapes match exactly
```

`rasterio.warp.reproject` does the work. Two gotchas:
- Always reproject the **mask** with `nearest`, never `bilinear`. Interpolating a categorical mask produces meaningless intermediate values.
- If the two scenes are already identical in shape and CRS, short-circuit and return unchanged. Saves 20 seconds per run, which matters when you're iterating.

## 2.2 `indices.py`

```python
EPS = 1e-6

def _norm(a, b):
    return (a - b) / (a + b + EPS)

def ndwi(green, nir):  return _norm(green, nir)   # water:      higher = wetter
def ndvi(nir, red):    return _norm(nir, red)     # vegetation: higher = greener
def nbr(nir, swir):    return _norm(nir, swir)    # burn:       drops sharply after fire
def ndbi(swir, nir):   return _norm(swir, nir)    # built-up:   higher = more impervious
```

The `+ EPS` matters — without it you get `nan` wherever both bands are zero (image edges, nodata), and a single `nan` propagates through your whole mask. Use `np.errstate(invalid="ignore", divide="ignore")` around the maths and `np.nan_to_num` after.

## 2.3 `detect.py`

```python
def detect_change(before_idx: dict, after_idx: dict) -> tuple[np.ndarray, dict]:
    deltas = {k: after_idx[k] - before_idx[k] for k in before_idx}
    mask = np.zeros(next(iter(deltas.values())).shape, dtype=np.uint8)
    mask |= (np.abs(deltas["ndwi"]) > T_NDWI)
    mask |= (np.abs(deltas["ndvi"]) > T_NDVI)
    mask |= (np.abs(deltas["nbr"])  > T_NBR)
    mask |= (np.abs(deltas["ndbi"]) > T_NDBI)
    mask = binary_opening(mask, iterations=2)    # scipy.ndimage — kills salt-and-pepper
    return mask, deltas
```

**Starting thresholds** — tune these against your actual scenes, don't trust them blind:

| Index | Δ threshold | Rationale |
|---|---|---|
| NDWI | 0.15 | below this is seasonal wetness, not flooding |
| NDVI | 0.20 | below this is phenology (normal seasonal greening) |
| NBR | 0.25 | standard dNBR low-severity burn boundary |
| NDBI | 0.10 | construction signal is subtle |

Put them in one dict at module top with a single comment explaining they're empirical. Tuning these is 80% of making the demo look good — budget real time for it in Block 5.

**Sanity check before moving on:** dump the mask as a PNG with matplotlib and look at it. If the flood mask does not visibly trace the river floodplain, your bands are wrong or the scaling is off. Fix that before building anything on top.

## 2.4 `vectorize.py`

```python
def to_polygons(mask, transform, deltas, min_area_km2=0.25):
    labeled, n = ndimage.label(mask)
    out = []
    for shape, value in rasterio.features.shapes(labeled.astype("int32"),
                                                  mask=labeled > 0,
                                                  transform=transform):
        poly = shapely.geometry.shape(shape)
        poly = poly.simplify(0.0005)          # ~50 m; keeps GeoJSON payloads small
        area = area_km2(poly)
        if area < min_area_km2:
            continue
        out.append(RegionStats(geometry=poly, area_km2=area,
                               deltas=mean_deltas_inside(deltas, shape)))
    return out
```

Three things that will bite you:

1. **`min_area_km2` is not optional.** Without it you produce 3000 single-pixel polygons, the API payload hits megabytes, and Leaflet locks up. Tune it so each AOI yields **20–80 polygons**. Tell Part A the number you're producing.
2. **`simplify()` is not optional** for the same reason. `0.0005` degrees is roughly 50 m — invisible at demo zoom, and it cuts payload size by an order of magnitude.
3. **Coordinate order.** After reprojecting to EPSG:4326, shapely coordinates are `(x, y)` = `(lon, lat)`, which is what GeoJSON wants — so `mapping(poly)` is correct as-is. But `centroid` in the contract is `(lat, lon)`. **Do not mix these up.** This is the single most common integration bug in geospatial hackathon projects. Write it on a sticky note.

---

# §3 — Block 3 · 15:00–19:00 · Classification

## 3.1 `features.py`

Per polygon, build a fixed-order feature vector:

```python
FEATURES = [
    "d_ndwi", "d_ndvi", "d_nbr", "d_ndbi",          # mean delta inside polygon
    "d_ndwi_std", "d_ndvi_std",                      # heterogeneity
    "before_ndvi", "before_ndwi", "before_ndbi",     # what was there before
    "area_km2", "compactness",                        # 4*pi*A / P^2
    "elongation",                                     # bbox aspect ratio
]
```

`compactness` and `elongation` carry real signal: floods follow river valleys and are elongated; urban expansion is blocky and compact; deforestation patches are irregular. Cheap features, genuine discriminative power — and a good answer when a judge asks *"what does your model actually learn from?"*

**Fix the feature order in one list constant and use it everywhere.** Training and inference reading features in different orders is a silent failure that produces confident nonsense.

## 3.2 Getting labels — the pragmatic path

You have no labelled dataset and no time to make one. Do this instead:

**Rule-based bootstrapping, then train on it.** Write an honest rule function:

```python
def rule_label(f: dict) -> EventType:
    if f["d_ndwi"] >  0.15 and f["d_ndvi"] < -0.05: return EventType.flood
    if f["d_ndwi"] < -0.15:                          return EventType.water_recession
    if f["d_nbr"]  < -0.25 and f["d_ndvi"] < -0.15:  return EventType.wildfire_burn
    if f["d_ndvi"] < -0.20 and abs(f["d_ndbi"]) < 0.05: return EventType.deforestation
    if f["d_ndbi"] >  0.10 and f["d_ndvi"] < -0.10:  return EventType.urban_expansion
    return EventType.no_change
```

Run all three AOIs through it, **hand-correct the labels you can see are wrong** (spot-check 50 polygons against the imagery — 20 minutes), then train a RandomForest on the corrected set.

This is a legitimate, standard technique — weak supervision / rule-based bootstrapping. **Describe it exactly that way**, and explain the honest benefit: the trained model generalises to boundary cases the rules handle badly, and gives you calibrated confidences and feature importances, which raw rules cannot. A mentor who knows the field will respect this answer. A mentor who catches you calling it "trained on ground truth" will not.

Keep the rule function in the repo. It is your fallback if the model misbehaves, and it is evidence of how the labels were made.

## 3.3 `train/train_classifier.py`

```python
clf = RandomForestClassifier(n_estimators=300, max_depth=12,
                             class_weight="balanced", random_state=42)
# stratified train/test split, then:
print(classification_report(y_test, clf.predict(X_test)))
joblib.dump({"model": clf, "features": FEATURES, "version": "rf_v1"},
            "data/models/event_classifier.joblib")
```

**Write down the real accuracy, macro-F1, and per-class F1.** You will be asked, and this number goes in the deck and in `model_info`. Never round it up, never invent it.

Save `FEATURES` *inside* the artifact. At inference, assert the loaded feature list matches the current one — that turns a silent wrong-order bug into a loud error.

## 3.4 `classify.py`

Load once at module level (lazily, cached), apply to the feature matrix, return `(event_type, confidence)` per polygon where confidence is `max(predict_proba)`.

If the model file is missing, **fall back to `rule_label` with confidence 0.5 and append a `warnings` entry.** Never raise. A degraded result beats a failed run — especially at 11:40 on Day 2.

## 3.5 `render.py`

Write `before.png`, `after.png`, `change_mask.png` + `bounds.json` into `app/static/overlays/<aoi_id>/`. C needs these for the before/after swipe, which is the single most visually persuasive thing in the demo. **Prioritise this over model tuning if you're short on time.**

- True colour: stack B04/B03/B02, apply a 2–98 percentile stretch per band, `Image.fromarray` → PNG
- Mask: RGBA with alpha 0 where unchanged, event-type colour where changed
- Cap the long edge at ~1500 px so the browser doesn't choke

## 3.6 Wire `run_analysis()` — **17:30 hard deadline**

```python
def run_analysis(req, on_progress=None):
    def p(pct, text):
        if on_progress: on_progress(pct, text)

    warnings = []
    p(10, "loading scenes")
    bundle = PROVIDERS[req.provider].load(req.aoi_id)
    p(25, "aligning")
    bundle = align(bundle)
    p(40, "computing indices")
    before_idx, after_idx = indices_for(bundle)
    p(55, "detecting change")
    mask, deltas = detect_change(before_idx, after_idx)
    p(65, "vectorizing")
    regions = to_polygons(mask, bundle.transform, deltas)
    p(75, "classifying")
    events = classify(regions)
    p(88, "scoring risk")
    cells = score_risk(bundle, events, load_env(req.aoi_id))
    p(95, "rendering overlays")
    overlays = render_all(bundle, mask, events, req.aoi_id)
    p(100, "done")
    return AnalysisResult(aoi_id=req.aoi_id, job_id=req.job_id, events=events,
                          risk_cells=cells, overlays=overlays,
                          model_info=MODEL_INFO, warnings=warnings)
```

Wrap each stage in a try/except that appends to `warnings` and continues with empty results for that stage. `run_analysis` returning a thin-but-valid result is always better than raising.

**Merge to `dev` by 17:30.** A runs the integration check and will flag coordinate-order problems immediately.

---

# §4 — Block 4 · 20:00–22:00 · Risk prediction

This is the part that makes the project novel rather than another change-detection demo. Give it real attention.

## 4.1 `risk.py` — grid construction

Build a **40×40 grid** over the AOI bbox. That is 1600 cells — comfortably inside Part A's 2500-cell budget, and visually smooth on the map. Do not go finer; Leaflet will stutter and nobody can see the difference.

Per cell, compute:

```python
CELL_FEATURES = [
    "mean_d_ndwi", "mean_d_ndvi", "mean_d_nbr", "mean_d_ndbi",
    "changed_fraction",              # fraction of cell pixels in the change mask
    "dist_to_flood_km",              # distance to nearest flood polygon
    "dist_to_burn_km",
    "rainfall_7d_mm",                # from env CSV, window before the after-date
    "rainfall_30d_mm",
    "temp_max_c",
    "slope_deg",                     # from DEM; drop the feature if no DEM
    "elevation_m",
    "before_ndvi",                   # vegetation cover proxy
    "before_ndbi",                   # built-up proxy -> exposure
]
```

## 4.2 `train/train_risk.py` — labels

Train a binary "did an event occur in/near this cell" model, then use its **probability** as the risk score.

Label construction: across all AOIs, a cell is positive if it overlaps a detected event polygon of the given class, negative otherwise. Then — and this is the important part — **build the features from the *before* state only** (before-indices, terrain, rainfall up to the before-date), never from the after-scene. Training on after-scene features leaks the answer and gives you a meaningless 0.99 accuracy that a sharp judge will immediately question.

```python
model = GradientBoostingClassifier(n_estimators=200, max_depth=3,
                                   learning_rate=0.05, random_state=42)
# risk_score = model.predict_proba(X)[:, 1]
```

`max_depth=3` on purpose: shallow trees, less overfitting on your small sample, and more interpretable importances.

## 4.3 `drivers` — do not skip this field

For each cell, report the top 3 contributing features with contributions. Global feature importances work and take one line:

```python
imp = dict(zip(CELL_FEATURES, model.feature_importances_))
```

Better, if you have 20 spare minutes: weight each importance by that cell's normalised feature value, so cells report *different* drivers. This is what makes the risk layer feel intelligent instead of decorative — clicking two different red cells and getting two different explanations is genuinely impressive, and it costs almost nothing.

Give drivers human-readable names in the output: `cumulative_rainfall_7d` reads better than `rainfall_7d_mm`. C displays these verbatim.

## 4.4 Thresholds

`risk_level` from `risk_score` at 0.25 / 0.50 / 0.75 → `low / moderate / high / severe`.

Check the distribution across your hero AOI. If every cell comes out `low`, or everything is `severe`, the layer looks broken regardless of whether the model is right. Adjust thresholds so the hero AOI shows a **believable spread** — mostly low, a band of moderate, a meaningful cluster of high/severe near the flood. Note in the README that thresholds are calibrated per-deployment. That is true of real early-warning systems too.

---

# §5 — Block 5 · 22:00–01:30 · Tuning and robustness

| Time | Task |
|---|---|
| 22:00–23:15 | **Threshold tuning across all three AOIs.** Highest-value work left. Each AOI must produce a visually convincing result. Iterate: change threshold → run → look at the map → repeat. |
| 23:15–00:00 | Populate `model_info` with real version strings and accuracy. Populate `warnings` for cloud cover, missing DEM, low polygon count. |
| 00:00–00:45 | `tests/test_pipeline.py`: indices are in `[-1, 1]`; a synthetic array with a known water patch is detected; `run_analysis` output validates as `AnalysisResult`; a missing model file degrades to rules instead of raising. |
| 00:45–01:15 | Write down your honest numbers for the deck: accuracy, macro-F1, per-class F1, cells scored, polygons detected, runtime per AOI. Hand them to C for the slide. |

## Cloud cover handling

If either scene has significant cloud, you will get spurious change. The cheap, honest fix: mask pixels where blue reflectance is very high (`B02 > 0.25`) as cloud, exclude them from the mask, and report the excluded fraction in `warnings`. Three lines, and it turns *"your model detected a flood in a cloud"* from a fatal criticism into a handled limitation you can name.

---

# §6 — Day 2, 09:00–11:00

**No new features.** Verify all three AOIs run end to end from a clean clone. Then:

- You answer **all model and accuracy questions** at judging. Rehearse these:
  - *"How accurate is it?"* → the real per-class numbers, then the limitation (cloud cover, two-date comparison, small training set)
  - *"Where did your labels come from?"* → rule-based weak supervision with hand-correction; say it plainly, explain why the trained model beats the rules alone
  - *"Why not deep learning?"* → explainability matters when the output triggers an evacuation advisory; spectral index differencing is the established method; a CNN is a drop-in behind the same `classify()` interface
  - *"Is the risk model a forecast?"* → no, it's a risk-propensity model over terrain, recent change, and rainfall. **Say this before they ask.** Volunteering the limitation reads as competence; being caught overclaiming does the opposite.

---

# §7 — Your checklist

**Tonight**
- [ ] `import rasterio` works
- [ ] 3 scene pairs downloaded, cropped, < 10% cloud, in `data/scenes/`
- [ ] `meta.json` written for each, matching the contract exactly
- [ ] `env/*.csv` written for each
- [ ] Smoke test passes: both scenes open, same CRS, non-zero arrays
- [ ] Scene files shared with A and C (USB / Drive — **not** git)
- [ ] `meta.json` + CSVs committed

**Day 1**
- [ ] 12:00 — `local` provider returns a valid `SceneBundle`
- [ ] 14:00 — mask PNG visibly traces the flood. **Eyeball it.**
- [ ] 15:30 — polygons out of `vectorize`, 20–80 per AOI
- [ ] 17:00 — classifier trained, real numbers written down
- [ ] **17:30 — `run_analysis()` merged to `dev`. Hard deadline.**
- [ ] 19:00 — overlay PNGs + `bounds.json` written for the hero AOI
- [ ] 22:00 — risk grid + risk model + `drivers` working
- [ ] 23:15 — all 3 AOIs look convincing
- [ ] 01:15 — tests green, `model_info` + `warnings` populated

---

# §8 — Failure modes, ranked by likelihood

| Symptom | Cause | Fix |
|---|---|---|
| Polygons appear off the coast of Somalia | lat/lon swapped | GeoJSON is `[lon, lat]`; `centroid` is `(lat, lon)`. Fix the one that's wrong. |
| Everything is detected as changed | forgot to divide DNs by 10000 | Scale to reflectance in the provider |
| Nothing is detected | thresholds too high, or the two scenes are the same date | Print `deltas.min()/max()` and compare against your thresholds |
| 3000 tiny polygons, map dies | no `min_area_km2` | Raise it until you get 20–80 |
| `nan` everywhere in an index | zero-denominator at nodata pixels | `+ EPS` and `np.nan_to_num` |
| `before` and `after` shapes differ | different tiles or resolutions | That's what `align.py` is for — crop to intersection, resample |
| Classifier confidently wrong | feature order differs between train and inference | Assert the saved `FEATURES` list matches at load time |
| Risk model reports 0.99 accuracy | after-scene features leaked into training | Rebuild features from before-state only. Fix this — it's the question that sinks projects. |
| `pip install rasterio` fails | Python 3.12/3.13 | Use 3.11, or conda-forge |
| Model file missing at runtime | not committed (it's git-ignored) | Share via USB, and keep the rule-based fallback |

---

# §9 — Your two non-negotiables

1. **Download the imagery tonight.** Everything else in this document is recoverable tomorrow. This is not.

2. **Merge `run_analysis()` by 17:30, even if it's rough.** A rough real pipeline at 17:30 that A can integrate beats a beautiful one at 22:00 that turns out to have the coordinates transposed. Ship early, refine in place.
