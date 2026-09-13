# Part B — numbers for the deck

Every figure below is measured, not estimated. Sources are named so anyone can
re-derive them.

## Pipeline, per run

| | Kerala (kerala_flood_2018) | Bandipur (bandipur_fire_2019) |
|---|---|---|
| Scene pair | Sentinel-2 L2A, 2018-02-03 -> 2018-09-11 | 2019-02-13 -> 2019-02-26 |
| AOI area | 589 km² (Kuttanad, Alappuzha) | 588 km² (Bandipur, Karnataka) |
| Raster size | 2448 x 2483 px | |
| Events detected | **32** | |
| Event types | flood, water_recession | |
| Risk cells | **1600** (40 x 40) | |
| Risk spread | low 1255 / moderate 201 / high 93 / severe 51 | |
| Usable fraction | **48.4%** | |
| Excluded as permanent water | 45.7% (sea + Vembanad Lake) | |
| Cloud + shadow masked | 6.4% | |
| Scene offsets removed | ndwi -0.002, ndvi +0.003, nbr -0.027 | |
| Runtime | ~10 s | |

## Risk model — the number to lead with

    ROC AUC 0.901, 5-fold cross-validated, 1600 cells, 13.6% positive

Features are **pre-event only**. The importances prove it — every after-derived
feature is exactly 0.000:

| feature | importance |
|---|---|
| before_ndbi (built-up exposure) | 0.363 |
| before_ndvi (vegetation cover)  | 0.353 |
| before_ndwi (pre-existing water)| 0.285 |
| mean_d_ndwi, changed_fraction, dist_to_event_km, rainfall, temp | 0.000 |

**Caveat to state before being asked:** a single AOI means the folds are
spatially autocorrelated, so 0.901 is optimistic. A second AOI fixes this.

## Detection validated by photo-interpretation

    94.4% agreement (17 of 18) against an 83.3% majority baseline

Method: before/after true-colour crops with the detected polygon outlined; the
question asked of each was "does standing water appear inside the polygon in the
after scene". Single annotator, six ambiguous regions excluded rather than
guessed. Recorded in `data/models/reference_notes.json`.

**This check earned its keep** — it found two false-positive classes that are
now fixed:
- cloud shadow detected as new water (fix: dilate the cloud mask 30 px)
- thin slivers along canals from co-registration error, showing absurd deltas
  like dNDWI +0.97 with no visible water (fix: reject compactness < 0.08)

## Event classifier — do NOT quote its accuracy

    5-fold CV accuracy 1.000, macro F1 1.000, n=54

**This is circular and must not go on a slide.** The labels come from
`rule_label()` and the features include the exact quantities those rules
threshold on, so the model reproduces a lookup table. `model_info` carries the
caveat inline so it cannot surface bare in the API or the UI.

What the model does add: calibrated confidences instead of a flat 0.5, and
feature importances.

Top features: before_ndwi 0.212, d_ndvi 0.202, before_ndvi 0.165, d_ndwi 0.156.

## Tests

    11 pipeline tests passing
    python -m app.tools.check --real  ->  all checks passed

## Answers to rehearse

**"How accurate is it?"**
Two different numbers. The risk model is 0.901 AUC, five-fold cross-validated,
built from pre-event features only with zero leakage in the importances. For
detection we photo-interpreted 18 regions and got 94% agreement against an 83%
majority baseline. We deliberately don't quote a classifier accuracy — our
labels are rule-derived, so that number would be circular.

**"Where did your labels come from?"**
Rule-based weak supervision, then photo-interpretation of a sample against the
imagery. That's how we found our own false positives.

**"Is the risk model a forecast?"**
No. It's a risk-propensity ranking over pre-event terrain, land cover and
rainfall. It says where events tend to occur, not when one will.

**"Why is the after-scene September, not the August flood peak?"**
No cloud-free Sentinel-2 exists in the flood window — the whole Jun-Aug
catalogue over Ernakulam bottoms out at 31% cloud. That's the fundamental limit
of optical imagery for floods and it's why Sentinel-1 SAR is the production
answer, behind the same provider interface. Kuttanad's polders stayed inundated
for weeks, so 11 September still shows real flood extent.

**"Half your area is excluded — why?"**
45.7% is sea and Vembanad Lake, water in both scenes. Flood is *new* water, so
permanent water is masked rather than reported. Without that mask the ocean
alone became a 154 km² false detection — we hit exactly that and fixed it.

**"What would you do next?"**
Sentinel-1 SAR to see through cloud, a hand-labelled validation set so the
classifier number means something, and more AOIs so the risk model's folds
aren't spatially autocorrelated.
