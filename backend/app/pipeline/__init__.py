"""Real geospatial + ML pipeline. Owned by Part B.

Part B replaces this file with a working run_analysis(). Contract:

    def run_analysis(req: AnalysisRequest, on_progress=None) -> AnalysisResult

Rules:
  - never raise for a recoverable problem; degrade and append to result.warnings
  - call on_progress(percent, stage_text) at each stage
  - do not import from app.api, app.db or app.services

Until then PIPELINE_MODE=mock routes to app.pipeline.mock instead.
"""

from collections.abc import Callable

from app.schemas.analysis import AnalysisRequest, AnalysisResult


def run_analysis(
    req: AnalysisRequest,
    on_progress: Callable[[int, str], None] | None = None,
) -> AnalysisResult:
    raise NotImplementedError("real pipeline not implemented yet; set PIPELINE_MODE=mock")
