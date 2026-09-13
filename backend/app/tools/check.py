"""Pre-integration check for the pipeline and scene metadata.

    python -m app.tools.check                 # every AOI found, current PIPELINE_MODE
    python -m app.tools.check kerala_flood_2018
    python -m app.tools.check --real          # force the real pipeline
    python -m app.tools.check --meta-only     # skip running the pipeline

Run this before merging pipeline work. It catches the failures that are
expensive to find during integration: transposed coordinates, polygons outside
the AOI, a risk grid too large for the map, enum drift, missing overlays.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

OK = "  ok   "
WARN = " warn  "
FAIL = " FAIL  "

_failures = 0
_warnings = 0


def _line(tag: str, text: str) -> None:
    print(f"[{tag}] {text}")


def ok(text: str) -> None:
    _line(OK, text)


def warn(text: str) -> None:
    global _warnings
    _warnings += 1
    _line(WARN, text)


def fail(text: str) -> None:
    global _failures
    _failures += 1
    _line(FAIL, text)


def header(text: str) -> None:
    print(f"\n{'=' * 66}\n{text}\n{'=' * 66}")


# --------------------------------------------------------------------- meta


META_TEMPLATE = {
    "aoi_id": "kerala_flood_2018",
    "name": "Kerala Floods — Aug 2018",
    "region": "Ernakulam, Kerala",
    "bbox": [76.10, 9.80, 76.60, 10.30],
    "center": [10.05, 76.35],
    "before_date": "2018-07-20",
    "after_date": "2018-08-22",
    "provider": "local",
    "expected_event": "flood",
    "band_map": {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5},
}


def check_meta(scenes_dir: Path) -> list[str]:
    from pydantic import ValidationError

    from app.schemas.aoi import SceneMeta
    from app.schemas.common import AOI_ID_PATTERN

    header(f"scene metadata  ({scenes_dir.resolve()})")

    if not scenes_dir.is_dir():
        fail(f"{scenes_dir} does not exist")
        return []

    folders = [d for d in sorted(scenes_dir.iterdir()) if d.is_dir()]
    if not folders:
        warn("no scene folders yet - the API will fall back to the built-in AOI")
        return []

    valid: list[str] = []
    for folder in folders:
        name = folder.name
        if not re.fullmatch(AOI_ID_PATTERN, name):
            fail(f"{name}: folder name must match {AOI_ID_PATTERN} (lowercase, digits, _)")
            continue

        path = folder / "meta.json"
        if not path.is_file():
            fail(f"{name}: no meta.json - this AOI will not appear in /aoi")
            continue

        try:
            meta = SceneMeta.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            fail(f"{name}: meta.json invalid")
            for err in exc.errors()[:5]:
                loc = ".".join(str(p) for p in err["loc"])
                print(f"          {loc}: {err['msg']}")
            continue
        except OSError as exc:
            fail(f"{name}: cannot read meta.json ({exc})")
            continue

        if meta.aoi_id != name:
            fail(f"{name}: aoi_id is '{meta.aoi_id}' but the folder is '{name}' - must match")
            continue

        lat, lon = meta.center
        min_lon, min_lat, max_lon, max_lat = meta.bbox
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            fail(
                f"{name}: center {meta.center} is outside bbox - "
                "center is (lat, lon), bbox is [min_lon, min_lat, max_lon, max_lat]"
            )
            continue
        if meta.after_date <= meta.before_date:
            warn(f"{name}: after_date is not later than before_date")

        rasters = sorted(
            p.name for p in folder.iterdir() if p.suffix.lower() in {".tif", ".tiff", ".jp2"}
        )
        if not rasters:
            warn(f"{name}: no .tif/.jp2 in the folder (fine while the provider is stubbed)")
        else:
            ok(f"{name}: meta.json valid, rasters: {', '.join(rasters)}")
            valid.append(name)
            continue

        ok(f"{name}: meta.json valid")
        valid.append(name)

    return valid


# ----------------------------------------------------------------- pipeline


def _all_points(geometry: dict) -> list[list[float]]:
    pts: list[list[float]] = []

    def walk(node):
        if not node:
            return
        if isinstance(node[0], (int, float)):
            pts.append(node)
        else:
            for child in node:
                walk(child)

    walk(geometry.get("coordinates") or [])
    return pts


def check_pipeline(aoi_id: str, bbox: list[float] | None) -> None:
    from pydantic import ValidationError

    from app.config import settings
    from app.schemas.analysis import AnalysisRequest, AnalysisResult
    from app.schemas.common import risk_level_for
    from app.services.pipeline import get_pipeline

    header(f"pipeline  (aoi={aoi_id}, mode={settings().pipeline_mode})")

    try:
        run = get_pipeline()
    except Exception as exc:
        fail(f"cannot import the pipeline: {type(exc).__name__}: {exc}")
        return

    seen: list[int] = []
    stages: list[str] = []

    def on_progress(pct, stage):
        seen.append(pct)
        stages.append(stage)

    started = time.perf_counter()
    try:
        result = run(AnalysisRequest(aoi_id=aoi_id, job_id="job_c0ffee"), on_progress)
    except Exception as exc:
        fail(f"run_analysis raised {type(exc).__name__}: {exc}")
        print("          it must never raise for a recoverable problem -")
        print("          degrade and append to result.warnings instead")
        return
    elapsed = time.perf_counter() - started

    try:
        AnalysisResult.model_validate(result.model_dump())
        ok(f"AnalysisResult is valid  ({elapsed:.1f}s)")
    except ValidationError as exc:
        fail("AnalysisResult failed schema validation")
        for err in exc.errors()[:8]:
            loc = ".".join(str(p) for p in err["loc"])
            print(f"          {loc}: {err['msg']}")
        return

    if result.aoi_id != aoi_id:
        fail(f"result.aoi_id is '{result.aoi_id}', expected '{aoi_id}'")

    # progress
    if not seen:
        warn("on_progress was never called - the UI progress bar will not move")
    else:
        if seen != sorted(seen):
            warn(f"progress went backwards: {seen}")
        if seen[-1] != 100:
            warn(f"progress ended at {seen[-1]}, not 100")
        else:
            ok(f"progress reported {len(seen)} stages: {', '.join(stages[:4])}...")

    # events
    if not result.events:
        warn("no events detected - check your thresholds against this scene pair")
    else:
        n = len(result.events)
        if n > 200:
            fail(f"{n} events - raise min_area_km2, the map will choke and payloads bloat")
        elif n > 120:
            warn(f"{n} events - aim for 20-80; consider raising min_area_km2")
        else:
            ok(f"{n} events")

        kinds = sorted({e.event_type.value for e in result.events})
        ok(f"event types: {', '.join(kinds)}")

        _check_geometry(result.events, bbox, "event")

        for e in result.events[:200]:
            if e.area_km2 <= 0:
                fail(f"event {e.event_type} has area_km2={e.area_km2}")
                break
        missing = [e for e in result.events if not e.deltas]
        if missing:
            warn(f"{len(missing)} event(s) have empty deltas - the popup shows nothing useful")

    # risk cells
    cells = result.risk_cells
    if not cells:
        warn(
            "no risk cells - the forward-looking layer is the differentiator, "
            "don't ship without it"
        )
    else:
        n = len(cells)
        if n > 2500:
            fail(f"{n} risk cells - the contract caps this at 2500; use a 40x40 grid or coarser")
        elif n > 1800:
            warn(f"{n} risk cells - close to the 2500 cap, Leaflet may stutter")
        else:
            ok(f"{n} risk cells")

        bad = [c for c in cells if c.risk_level != risk_level_for(c.risk_score)]
        if bad:
            fail(
                f"{len(bad)} cell(s) have risk_level inconsistent with risk_score "
                f"(e.g. {bad[0].cell_id}: {bad[0].risk_score} -> {bad[0].risk_level})"
            )
        else:
            ok("risk_level matches risk_score everywhere")

        spread = {}
        for c in cells:
            spread[c.risk_level.value] = spread.get(c.risk_level.value, 0) + 1
        ok(f"risk spread: {spread}")
        if len(spread) == 1:
            warn("every cell is the same risk level - the heat layer will look broken")

        no_drivers = [c for c in cells if not c.drivers]
        if no_drivers:
            warn(
                f"{len(no_drivers)} cell(s) have no drivers - "
                "the driver breakdown is what makes the risk layer look intelligent"
            )

        _check_geometry(cells, bbox, "risk cell")

    # overlays
    if not result.overlays:
        warn("no overlays - the before/after swipe is the most persuasive part of the demo")
    else:
        static = Path(__file__).resolve().parents[1] / "static"
        for name, rel in result.overlays.items():
            disk = static / rel.replace("/static/", "", 1).lstrip("/")
            if disk.is_file():
                ok(f"overlay '{name}' -> {rel}")
            else:
                warn(f"overlay '{name}' points at {rel} but {disk} does not exist")

    if result.model_info:
        ok(f"model_info: {result.model_info}")
    else:
        warn("model_info is empty - judges will ask for accuracy numbers")

    for w in result.warnings:
        _line(WARN, f"pipeline warning: {w}")


def _check_geometry(items, bbox: list[float] | None, label: str) -> None:
    """The transposed-coordinate check. This is the bug that eats integration."""
    pts: list[list[float]] = []
    for item in items:
        pts.extend(_all_points(item.geometry.model_dump()))
    if not pts:
        fail(f"{label} geometries contain no coordinates")
        return

    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]

    if max(abs(v) for v in lats) > 90:
        fail(
            f"{label} geometry has |second value| > 90 - coordinates look transposed. "
            "GeoJSON is [lon, lat], not [lat, lon]"
        )
        return

    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        pad_lon = (max_lon - min_lon) * 0.25
        pad_lat = (max_lat - min_lat) * 0.25
        outside = sum(
            1
            for lon, lat in zip(lons, lats, strict=True)
            if not (
                min_lon - pad_lon <= lon <= max_lon + pad_lon
                and min_lat - pad_lat <= lat <= max_lat + pad_lat
            )
        )
        if outside:
            fail(
                f"{outside}/{len(pts)} {label} vertices fall outside the AOI bbox {bbox} - "
                "usually a CRS or lon/lat problem"
            )
            return
        ok(f"{label} geometry inside the AOI bbox, [lon, lat] order correct")
    else:
        ok(f"{label} geometry is plausible lon/lat ({min(lons):.2f}..{max(lons):.2f}, "
           f"{min(lats):.2f}..{max(lats):.2f})")

    # centroid must be the other way round
    for item in items[:50]:
        centroid = getattr(item, "centroid", None)
        if centroid is None:
            continue
        lat, lon = centroid
        if abs(lat) > 90:
            fail(
                f"{label} centroid {centroid} looks like (lon, lat); "
                "the contract wants (lat, lon)"
            )
            return
    if any(getattr(i, "centroid", None) for i in items):
        ok(f"{label} centroid is (lat, lon) as the contract requires")


# --------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.check")
    parser.add_argument("aoi_id", nargs="?", help="check one AOI (default: all found)")
    parser.add_argument("--real", action="store_true", help="force PIPELINE_MODE=real")
    parser.add_argument("--mock", action="store_true", help="force PIPELINE_MODE=mock")
    parser.add_argument("--meta-only", action="store_true", help="do not run the pipeline")
    parser.add_argument("--template", action="store_true", help="print a meta.json template")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(META_TEMPLATE, indent=2, ensure_ascii=False))
        return 0

    os.environ.setdefault("JWT_SECRET", "check-tool-not-a-real-secret")
    if args.real:
        os.environ["PIPELINE_MODE"] = "real"
    if args.mock:
        os.environ["PIPELINE_MODE"] = "mock"

    from app.config import settings
    from app.services.aoi import list_aois

    valid = check_meta(settings().scenes_dir)

    if not args.meta_only:
        known = {a.aoi_id: a.bbox for a in list_aois()}
        targets = [args.aoi_id] if args.aoi_id else (valid or list(known)[:1])
        for aoi_id in targets:
            if aoi_id not in known:
                fail(f"{aoi_id} is not in /aoi - fix its meta.json first")
                continue
            check_pipeline(aoi_id, known[aoi_id])

    header("summary")
    if _failures:
        print(f"{_failures} failure(s), {_warnings} warning(s) - fix the failures before merging")
    elif _warnings:
        print(f"clean, with {_warnings} warning(s) - safe to merge")
    else:
        print("all checks passed")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
