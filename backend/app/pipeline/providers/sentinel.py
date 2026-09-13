from __future__ import annotations

from app.config import settings

from .base import SceneBundle

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


class SentinelUnavailable(RuntimeError):
    pass


class SentinelProvider:
    """Copernicus Sentinel Hub adapter.

    Interface and config plumbing only. The demo path is `local` with cached scenes;
    this exists so the provider layer is genuinely pluggable, not so we can claim
    live ingest works. Do not enable it in a demo without testing it first.
    """

    @property
    def configured(self) -> bool:
        s = settings()
        return bool(s.sentinel_client_id and s.sentinel_client_secret)

    def load(self, aoi_id: str) -> SceneBundle:
        # OAuth2 client-credentials against TOKEN_URL, then POST the AOI bbox and the
        # two date windows to PROCESS_URL requesting B02/B03/B04/B08/B11 as GeoTIFF.
        # rasterio.MemoryFile on the response bytes gives the same SceneBundle as local.
        raise SentinelUnavailable("sentinel provider is not implemented; use provider='local'")
