from fastapi import APIRouter, Path

from app.schemas.aoi import AoiOut
from app.schemas.common import AOI_ID_PATTERN
from app.security.deps import CurrentUser
from app.services import aoi as service

router = APIRouter(prefix="/aoi", tags=["aoi"])


@router.get("", response_model=list[AoiOut])
def list_aois(user: CurrentUser) -> list[AoiOut]:
    return service.list_aois()


@router.get("/{aoi_id}", response_model=AoiOut)
def get_aoi(user: CurrentUser, aoi_id: str = Path(pattern=AOI_ID_PATTERN)) -> AoiOut:
    return service.get_aoi(aoi_id)
