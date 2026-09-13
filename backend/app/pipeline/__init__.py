"""Real geospatial + ML pipeline. Owned by Part B.

Reached through one function:

    run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult

It never raises for a recoverable problem. Every stage is wrapped: a failure
degrades that stage to an empty result, appends to warnings, and the run
continues. A thin-but-valid AnalysisResult always beats an exception, because
an exception on stage is a dead demo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.schemas.analysis import AnalysisRequest, AnalysisResult

log = logging.getLogger("terrapulse.pipeline")

MIN_AREA_KM2 = 0.25
MAX_EVENTS = 80


def run_analysis(
    req: AnalysisRequest,
    on_progress: Callable[[int, str], None] | None = None,
) -> AnalysisResult:
    from . import classify as classify_mod
    from . import detect, indices, render
    from . import risk as risk_mod
    from .align import align
    from .providers import PROVIDERS
    from .vectorize import to_polygons

    def p(pct: int, stage: str) -> None:
        if on_progress:
            try:
                on_progress(pct, stage)
            except Exception:
                pass

    warnings: list[str] = []
    events = []
    cells = []
    overlays: dict[str, str] = {}
    model_info: dict[str, str] = {}

    p(5, "loading scenes")
    provider = PROVIDERS.get(req.provider.value) or PROVIDERS["local"]
    try:
        bundle = provider.load(req.aoi_id)
    except Exception as exc:
        log.exception("scene load failed for %s", req.aoi_id)
        p(100, "failed")
        return AnalysisResult(
            aoi_id=req.aoi_id,
            job_id=req.job_id,
            warnings=[f"could not load scenes for {req.aoi_id}: {type(exc).__name__}: {exc}"],
            model_info={"pipeline": "real", "status": "no imagery"},
        )

    p(20, "aligning scenes")
    try:
        bundle = align(bundle)
    except Exception as exc:
        warnings.append(f"alignment failed ({type(exc).__name__}); using the scenes as-is")

    p(35, "computing indices")
    try:
        before_idx = indices.compute(bundle.before, bundle.band_map)
        after_idx = indices.compute(bundle.after, bundle.band_map)
    except Exception as exc:
        log.exception("indices failed")
        p(100, "failed")
        return AnalysisResult(
            aoi_id=req.aoi_id,
            job_id=req.job_id,
            warnings=[f"index computation failed: {type(exc).__name__}: {exc}"],
            model_info={"pipeline": "real", "status": "indices failed"},
        )

    p(50, "detecting change")
    mask = None
    deltas: dict = {}
    try:
        valid, stats = detect.valid_mask(
            bundle.before, bundle.after, bundle.band_map, before_idx, after_idx
        )
        if stats["cloud"] > 0.02:
            warnings.append(f"cloud masked {stats['cloud']:.1%} of the scene pair")
        if stats["nodata"] > 0.01:
            warnings.append(f"{stats['nodata']:.1%} of the overlap has no data")
        if stats["permanent_water"] > 0.01:
            warnings.append(
                f"{stats['permanent_water']:.1%} is water in both scenes and was excluded "
                "as permanent rather than reported as change"
            )
        if stats["valid"] < 0.35:
            warnings.append(
                f"only {stats['valid']:.1%} of the scene is usable; "
                "detection over this pair is unreliable"
            )
        mask, deltas, offsets = detect.detect_change(before_idx, after_idx, valid=valid)
        model_info["scene_offsets"] = ", ".join(f"{k}{v:+.3f}" for k, v in offsets.items())
        model_info["usable_fraction"] = f"{stats['valid']:.1%}"
        big = {k: v for k, v in offsets.items() if abs(v) > 0.10}
        if big:
            warnings.append(
                "large scene-wide index shift removed before thresholding "
                f"({', '.join(f'{k} {v:+.2f}' for k, v in big.items())}); "
                "the two dates differ seasonally or atmospherically"
            )
    except Exception as exc:
        warnings.append(f"change detection failed ({type(exc).__name__}); no events reported")

    p(65, "vectorizing regions")
    regions = []
    if mask is not None:
        try:
            regions = to_polygons(
                mask, bundle.transform, deltas, before_idx, min_area_km2=MIN_AREA_KM2
            )
            if not regions:
                warnings.append("no regions above the minimum area; thresholds may be too high")
        except Exception as exc:
            warnings.append(f"vectorization failed ({type(exc).__name__}); no events reported")

    p(78, "classifying regions")
    try:
        events = classify_mod.classify(regions, warnings)[:MAX_EVENTS]
        model_info.update(classify_mod.model_info())
    except Exception as exc:
        warnings.append(f"classification failed ({type(exc).__name__}); no events reported")

    p(88, "scoring risk")
    if mask is not None:
        try:
            cells = risk_mod.score_risk(bundle, events, deltas, before_idx, mask, warnings)
            model_info.update(risk_mod.model_info())
        except Exception as exc:
            log.exception("risk scoring failed")
            warnings.append(f"risk scoring failed ({type(exc).__name__}); risk layer is empty")

    p(95, "rendering overlays")
    if mask is not None:
        try:
            overlays = render.render_all(req.aoi_id, bundle, mask, events, warnings)
        except Exception as exc:
            warnings.append(f"overlay rendering failed ({type(exc).__name__})")

    model_info.setdefault("pipeline", "real")
    model_info["scenes"] = f"{bundle.meta.get('before_date')} -> {bundle.meta.get('after_date')}"
    model_info["reflectance_scale"] = str(bundle.meta.get("reflectance_scale", "auto"))

    p(100, "done")
    return AnalysisResult(
        aoi_id=req.aoi_id,
        job_id=req.job_id,
        events=events,
        risk_cells=cells,
        overlays=overlays,
        model_info=model_info,
        warnings=warnings,
    )


__all__ = ["run_analysis"]
