import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

from app.pipeline.providers.base import SceneBundle

TARGET_CRS = CRS.from_epsg(4326)


def _reproject(
    array: np.ndarray, src_transform, src_crs, dst_transform, dst_crs, shape
) -> np.ndarray:
    out = np.zeros((array.shape[0], *shape), dtype="float32")
    for i in range(array.shape[0]):
        reproject(
            source=array[i],
            destination=out[i],
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )
    return out


def align(bundle: SceneBundle) -> SceneBundle:
    """Put both scenes on the same EPSG:4326 grid.

    Short-circuits when they already match, which is the common case for a pair
    cut from the same tile - saves ~20s per run while tuning.
    """
    same_shape = bundle.before.shape == bundle.after.shape
    if same_shape and bundle.crs == TARGET_CRS:
        return bundle

    h, w = bundle.before.shape[1], bundle.before.shape[2]
    left, bottom, right, top = rasterio.transform.array_bounds(h, w, bundle.transform)

    dst_transform, dst_w, dst_h = calculate_default_transform(
        bundle.crs, TARGET_CRS, w, h, left, bottom, right, top
    )
    shape = (dst_h, dst_w)

    before = _reproject(
        bundle.before, bundle.transform, bundle.crs, dst_transform, TARGET_CRS, shape
    )
    after = _reproject(
        bundle.after, bundle.transform, bundle.crs, dst_transform, TARGET_CRS, shape
    )

    return bundle._replace(
        before=before, after=after, transform=dst_transform, crs=TARGET_CRS
    )
