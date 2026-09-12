import logging
import re

from pydantic import ValidationError

from app.config import settings
from app.errors import AppError
from app.schemas.aoi import AoiOut, SceneMeta
from app.schemas.common import AOI_ID_PATTERN, ErrorCode
from app.security.paths import safe_join

log = logging.getLogger("terrapulse")

# Shown when data/scenes is still empty so the app is demoable before Part B's
# imagery lands. A real meta.json for the same aoi_id takes precedence.
BUILTIN: list[dict] = [
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
    }
]


def _to_out(meta: SceneMeta) -> AoiOut:
    return AoiOut(
        **meta.model_dump(exclude={"band_map"}),
        preview_before_url=f"/static/overlays/{meta.aoi_id}/before.png",
        preview_after_url=f"/static/overlays/{meta.aoi_id}/after.png",
    )


def list_aois() -> list[AoiOut]:
    found: dict[str, AoiOut] = {}
    scenes = settings().scenes_dir

    if scenes.is_dir():
        for entry in sorted(scenes.iterdir()):
            if not entry.is_dir() or not re.fullmatch(AOI_ID_PATTERN, entry.name):
                continue
            path = entry / "meta.json"
            if not path.is_file():
                continue
            try:
                meta = SceneMeta.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError) as exc:
                log.warning("skipping %s: %s", path, exc)
                continue
            if meta.aoi_id != entry.name:
                log.warning("skipping %s: aoi_id does not match folder name", path)
                continue
            found[meta.aoi_id] = _to_out(meta)

    for raw in BUILTIN:
        found.setdefault(raw["aoi_id"], _to_out(SceneMeta.model_validate(raw)))

    return sorted(found.values(), key=lambda a: a.aoi_id)


def get_aoi(aoi_id: str) -> AoiOut:
    # resolves through the traversal guard even though the id is regex-checked
    safe_join(settings().scenes_dir, aoi_id)
    for aoi in list_aois():
        if aoi.aoi_id == aoi_id:
            return aoi
    raise AppError(404, ErrorCode.aoi_not_found, f"unknown aoi: {aoi_id}")
