from .base import ImageryProvider, SceneBundle
from .local import LocalProvider
from .sentinel import SentinelProvider

PROVIDERS: dict[str, ImageryProvider] = {
    "local": LocalProvider(),
    "sentinel": SentinelProvider(),
}

__all__ = ["PROVIDERS", "ImageryProvider", "LocalProvider", "SceneBundle", "SentinelProvider"]
