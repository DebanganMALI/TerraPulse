"""Live Copernicus / Sentinel Hub adapter.

Same interface as LocalProvider so `provider="sentinel"` is a config switch, not
a code change. Not wired to the network yet - the demo path is `local`.
Credentials come from SENTINEL_CLIENT_ID / SENTINEL_CLIENT_SECRET.
"""

from app.config import settings
from app.pipeline.providers.base import SceneBundle

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


class SentinelProvider:
    def __init__(self) -> None:
        s = settings()
        self.client_id = s.sentinel_client_id
        self.client_secret = s.sentinel_client_secret

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def load(self, aoi_id: str) -> SceneBundle:
        if not self.configured:
            raise RuntimeError(
                "sentinel provider needs SENTINEL_CLIENT_ID and SENTINEL_CLIENT_SECRET"
            )
        # OAuth2 client-credentials -> token, then POST the AOI bbox and the two
        # date windows to PROCESS_URL, read the returned GeoTIFF through
        # rasterio.MemoryFile and return a SceneBundle.
        raise NotImplementedError("live fetch not implemented; use provider=local")
