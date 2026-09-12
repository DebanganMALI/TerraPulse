from collections.abc import Callable

from app.config import settings
from app.schemas.analysis import AnalysisRequest, AnalysisResult

PipelineFn = Callable[..., AnalysisResult]


def get_pipeline() -> PipelineFn:
    """Resolve the pipeline at call time.

    Imported inside the function on purpose: a broken app/pipeline/__init__.py
    from Part B must not stop the API from booting.
    """
    if settings().pipeline_mode == "real":
        from app.pipeline import run_analysis
    else:
        from app.pipeline.mock import run_analysis
    return run_analysis


def describe_pipeline() -> dict[str, str | bool]:
    mode = settings().pipeline_mode
    try:
        get_pipeline()
        loaded = True
    except Exception:
        loaded = False
    return {"pipeline_mode": mode, "pipeline_loaded": loaded}


__all__ = ["AnalysisRequest", "describe_pipeline", "get_pipeline"]
