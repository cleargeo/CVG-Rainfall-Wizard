# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# Protected under US and International copyright, trade secret,
# trademark, cybersecurity, and intellectual property law.
# This Product is developed under CVG's Agentic Development Framework (ADF).
# Unauthorized use, replication, or modification is strictly prohibited.
# -----------------------------------------------------------------------------
# Author      : Alex Zelenski, GISP
# Organization: Clearview Geographic, LLC
# Contact     : azelenski@clearviewgeographic.com  |  386-957-2314
# License     : Proprietary -- CVG-ADF
# =============================================================================
"""
io.py — Raster and vector I/O utilities for the Rainfall Wizard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject
    from rasterio.mask import mask as rio_mask
    _RASTERIO_OK = True
except ImportError:
    _RASTERIO_OK = False
    log.warning("rasterio not available — raster I/O disabled.")

try:
    import fiona
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    _FIONA_OK = True
except ImportError:
    _FIONA_OK = False
    log.warning("fiona/shapely not available — vector I/O disabled.")


@dataclass
class RasterData:
    data: np.ndarray
    transform: Any
    crs: Any
    nodata: float
    width: int
    height: int
    dtype: str = "float32"

    @property
    def shape(self) -> Tuple[int, int]:
        return (self.height, self.width)

    @property
    def resolution_m(self) -> Tuple[float, float]:
        if self.transform is None:
            return (0.0, 0.0)
        return (abs(self.transform.a), abs(self.transform.e))

    def masked_array(self) -> np.ma.MaskedArray:
        return np.ma.masked_equal(self.data.copy(), self.nodata)

    def stats(self) -> Dict[str, Optional[float]]:
        arr = self.masked_array()
        if arr.count() == 0:
            return {"min": None, "max": None, "mean": None, "std": None}
        return {
            "min": float(arr.min()),
            "max": float(arr.max()),
            "mean": float(arr.mean()),
            "std": float(arr.std()),
        }


def read_raster(path: str | Path) -> RasterData:
    if not _RASTERIO_OK:
        raise ImportError("rasterio required.")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raster not found: {p}")
    with rasterio.open(p) as src:
        data = src.read(1).astype("float32")
        nodata = float(src.nodata) if src.nodata is not None else -9999.0
        return RasterData(
            data=data, transform=src.transform, crs=src.crs,
            nodata=nodata, width=src.width, height=src.height,
        )


def write_raster(raster: RasterData, path: str | Path, compress: bool = True) -> None:
    if not _RASTERIO_OK:
        raise ImportError("rasterio required.")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    profile: Dict[str, Any] = {
        "driver": "GTiff", "dtype": raster.dtype,
        "width": raster.width, "height": raster.height,
        "count": 1, "crs": raster.crs,
        "transform": raster.transform, "nodata": raster.nodata,
    }
    if compress:
        profile.update({"compress": "lzw", "tiled": True, "blockxsize": 256, "blockysize": 256})
    with rasterio.open(p, "w", **profile) as dst:
        dst.write(raster.data.astype(raster.dtype), 1)
    log.info("Raster written → %s", p)


def reproject_to_match(source: RasterData, target: RasterData) -> RasterData:
    if not _RASTERIO_OK:
        raise ImportError("rasterio required.")
    dst_data = np.full((target.height, target.width), source.nodata, dtype="float32")
    reproject(
        source=source.data, destination=dst_data,
        src_transform=source.transform, src_crs=source.crs, src_nodata=source.nodata,
        dst_transform=target.transform, dst_crs=target.crs, dst_nodata=source.nodata,
        resampling=Resampling.bilinear,
    )
    import dataclasses
    return dataclasses.replace(source, data=dst_data,
                               transform=target.transform, crs=target.crs,
                               width=target.width, height=target.height)


def clip_to_aoi(raster: RasterData, aoi_path: str | Path) -> RasterData:
    if not _RASTERIO_OK or not _FIONA_OK:
        raise ImportError("rasterio and fiona required.")
    with fiona.open(Path(aoi_path), "r") as src:
        shapes = [f["geometry"] for f in src]
    import rasterio.io as rio_io
    memfile = rio_io.MemoryFile()
    profile = {
        "driver": "GTiff", "dtype": "float32",
        "width": raster.width, "height": raster.height, "count": 1,
        "crs": raster.crs, "transform": raster.transform, "nodata": raster.nodata,
    }
    with memfile.open(**profile) as ds:
        ds.write(raster.data, 1)
        clipped, clipped_transform = rio_mask(ds, shapes, crop=True, nodata=raster.nodata)
    data = clipped[0].astype("float32")
    import dataclasses
    return dataclasses.replace(raster, data=data, transform=clipped_transform,
                               width=data.shape[1], height=data.shape[0])


def load_aoi_shapes(path: str | Path) -> List[Any]:
    if not _FIONA_OK:
        raise ImportError("fiona required.")
    with fiona.open(Path(path), "r") as src:
        return [shape(f["geometry"]) for f in src if f["geometry"]]


def compute_stats(arr: np.ndarray, nodata: float) -> Dict[str, Any]:
    """Compute descriptive statistics for a depth/elevation grid array.

    Parameters
    ----------
    arr : np.ndarray
        2-D float array (e.g., a flood depth grid).
    nodata : float
        NoData sentinel value.  Cells matching this value are excluded.

    Returns
    -------
    dict
        Keys: ``min``, ``max``, ``mean``, ``std`` (all float or None when no
        valid data is present).
    """
    valid = arr[arr != nodata]
    valid = valid[np.isfinite(valid)]
    if valid.size == 0:
        return {"min": None, "max": None, "mean": None, "std": None}
    return {
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid)),
    }
