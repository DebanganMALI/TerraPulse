from pathlib import Path

from app.errors import AppError
from app.schemas.common import ErrorCode


def safe_join(root: Path, *parts: str) -> Path:
    """Resolve a request-driven path and refuse anything outside root.

    resolve() runs before the containment check on purpose: without it a symlink
    inside root would pass the test and still read outside it.
    """
    root = root.resolve()
    target = (root / Path(*parts)).resolve()
    if target != root and root not in target.parents:
        raise AppError(400, ErrorCode.validation_error, "invalid path")
    return target
