"""Geospatial + ML pipeline. Owned by Part B.

The only seam with the rest of the app:

    run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult

Rules: never raise for a recoverable problem - degrade and append to
result.warnings. Call on_progress at each stage. Do not import app.api,
app.db or app.services.
"""

import logging
from collections.abc import Callable

import shapely.geometry

from app.pipeline import classify as classify_mod
from app.pipeline import detect, indices, render, risk, vectorize
from app.pipeline.align import align
from app.pipeline.providers.local import LocalProvider
from app.pipeline.providers.sentinel import SentinelProvider
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    DetectedEvent,
)
from app.schemas.common import EventType, Geometry, Provider

log = logging.getLogger("terrapulse")

PROVIDERS = {
    Provider.local: LocalProvider(),
    Provider.sentinel: SentinelProvider(),
}


def run_analysis(
    req: AnalysisRequest,
    on_progress: Callable[[int, str], None] | None = None,
) -> AnalysisResult:
    warnings: list[str] = []
    events: list[DetectedEvent] = []
    cells: list = []
    overlays: dict[str, str] = {}
    model_info: dict[str, str] = {}

    def p(pct: int, stage: str) -> None:
        if on_progress:
            on_progress(pct, stage)

    p(8, "loading scenes")
    try:
        bundle = PROVIDERS[req.provider].load(req.aoi_id)
    except Exception as exc:
        log.exception("scene load failed for %s", req.aoi_id)
        return AnalysisResult(
            aoi_id=req.aoi_id,
            job_id=req.job_id,
            warnings=[f"could not load scenes: {type(exc).__name__}: {exc}"],
        )

    p(20, "aligning rasters")
    try:
        bundle = align(bundle)
    except Exception as exc:
        warnings.append(f"alignment skipped: {exc}")

    p(35, "computing indices")
    before_idx = indices.compute(bundle, "before")
    after_idx = indices.compute(bundle, "after")
    deltas = detect.deltas_of(before_idx, after_idx)

    p(48, "masking cloud")
    try:
        cloud = indices.cloud_mask(bundle, "before") | indices.cloud_mask(bundle, "after")
        fraction = float(cloud.mean())
        if fraction > 0.02:
            warnings.append(f"{fraction:.1%} of pixels excluded as cloud")
        if fraction > 0.35:
            warnings.append("heavy cloud cover: detection may be unreliable")
    except Exception:
        cloud = None

    p(58, "detecting change")
    mask = detect.detect_change(deltas, exclude=cloud)
    if not mask.any():
        warnings.append("no change detected above threshold; check detect.THRESHOLDS")

    p(70, "vectorizing regions")
    regions = vectorize.to_regions(mask, bundle.transform, deltas, before_idx)
    if len(regions) > 150:
        warnings.append(f"{len(regions)} regions; raise vectorize.MIN_AREA_KM2")
        regions = regions[:150]

    p(82, "classifying regions")
    labels, model_info = classify_mod.classify(regions)

    for region, (etype, confidence) in zip(regions, labels, strict=False):
        if etype is EventType.no_change:
            continue
        events.append(
            DetectedEvent(
                event_type=etype,
                confidence=round(confidence, 3),
                area_km2=region.area_km2,
                centroid=region.centroid,
                geometry=Geometry.model_validate(
                    shapely.geometry.mapping(region.geometry)
                ),
                deltas={k: round(v, 4) for k, v in region.deltas.items()},
            )
        )

    p(90, "scoring risk")
    try:
        cells = risk.score_grid(
            shape=mask.shape,
            transform=bundle.transform,
            deltas=deltas,
            before_idx=before_idx,
            mask=mask,
            regions=regions,
            labels=labels,
            aoi_id=req.aoi_id,
        )
    except Exception as exc:
        log.exception("risk scoring failed")
        warnings.append(f"risk layer unavailable: {exc}")

    p(96, "rendering overlays")
    try:
        overlays = render.render_all(bundle, mask, req.aoi_id)
    except Exception as exc:
        warnings.append(f"overlays unavailable: {exc}")

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
