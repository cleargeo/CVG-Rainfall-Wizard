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
"""cn_raster_from_nlcd.py — Build a spatially varying CN raster from NLCD + SSURGO HSG.

Combines:
  1. NLCD 2021 land cover raster (user-supplied or downloaded)
  2. SSURGO Hydrologic Soil Group (HSG) polygon/raster (user-supplied)

To produce a per-pixel NRCS Curve Number raster for use with the Rainfall Wizard
distributed runoff depth grid.

Reference
---------
USDA-NRCS TR-55 (1986) — Urban Hydrology for Small Watersheds.
NLCD 2021: https://www.mrlc.gov/data/nlcd-2021-land-cover-conus

Usage::

    python tools/cn_raster_from_nlcd.py \\
        --nlcd path/to/nlcd_2021.tif \\
        --hsg  path/to/hsg.tif \\
        --output path/to/cn_output.tif

NLCD class codes and TR-55 CN lookup (HSG B)
----------------------------------------------
11  Open Water          → CN 98 (water body)
21  Dev. Open Space     → CN 68
22  Dev. Low Intensity  → CN 75
23  Dev. Med Intensity  → CN 83
24  Dev. High Intensity → CN 90
31  Barren Land         → CN 77
41  Deciduous Forest    → CN 60
42  Evergreen Forest    → CN 58
43  Mixed Forest        → CN 60
52  Shrub/Scrub         → CN 66
71  Grassland/Herbaceous→ CN 71
81  Pasture/Hay         → CN 69
82  Cultivated Crops    → CN 81
90  Woody Wetlands      → CN 78
95  Emergent Herb. Wetlands → CN 78
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# NRCS TR-55 CN lookup table: NLCD_code → {HSG: CN}
# HSG: A=1, B=2, C=3, D=4
CN_TABLE: Dict[int, Dict[int, int]] = {
    11:  {1: 98, 2: 98, 3: 98, 4: 98},   # Open Water
    21:  {1: 49, 2: 68, 3: 79, 4: 84},   # Developed, Open Space
    22:  {1: 61, 2: 75, 3: 83, 4: 87},   # Developed, Low Intensity
    23:  {1: 74, 2: 83, 3: 88, 4: 90},   # Developed, Medium Intensity
    24:  {1: 82, 2: 90, 3: 93, 4: 95},   # Developed, High Intensity
    31:  {1: 63, 2: 77, 3: 85, 4: 88},   # Barren Land
    41:  {1: 36, 2: 60, 3: 73, 4: 79},   # Deciduous Forest
    42:  {1: 36, 2: 58, 3: 73, 4: 79},   # Evergreen Forest
    43:  {1: 36, 2: 60, 3: 73, 4: 79},   # Mixed Forest
    52:  {1: 35, 2: 66, 3: 77, 4: 85},   # Shrub/Scrub
    71:  {1: 30, 2: 58, 3: 71, 4: 78},   # Grassland/Herbaceous
    81:  {1: 39, 2: 61, 3: 74, 4: 80},   # Pasture/Hay
    82:  {1: 67, 2: 78, 3: 85, 4: 89},   # Cultivated Crops
    90:  {1: 40, 2: 68, 3: 79, 4: 86},   # Woody Wetlands
    95:  {1: 40, 2: 68, 3: 79, 4: 86},   # Emergent Herbaceous Wetlands
}

HSG_DEFAULT = 2  # HSG B assumed when no HSG data


def _rasterio_available() -> bool:
    try:
        import rasterio  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def build_cn_raster(
    nlcd_path: Path,
    hsg_path: Optional[Path],
    output_path: Path,
    default_hsg: int = HSG_DEFAULT,
) -> int:
    """Build CN raster from NLCD + HSG inputs.  Returns exit code."""
    if not _rasterio_available():
        print("ERROR: rasterio and numpy are required. pip install rasterio numpy")
        return 1

    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    print(f"\nCVG Rainfall Wizard — CN Raster Builder")
    print(f"  NLCD:   {nlcd_path}")
    print(f"  HSG:    {hsg_path or 'Not provided — using HSG ' + chr(64 + default_hsg)}")
    print(f"  Output: {output_path}\n")

    with rasterio.open(nlcd_path) as nlcd_ds:
        nlcd = nlcd_ds.read(1)
        profile = nlcd_ds.profile.copy()
        nodata_nlcd = nlcd_ds.nodata or 0

    # Build CN lookup arrays
    cn_by_pixel = np.full(nlcd.shape, 70, dtype=np.uint8)  # default CN 70

    if hsg_path and hsg_path.exists():
        with rasterio.open(hsg_path) as hsg_ds:
            # Reproject HSG to NLCD grid if needed
            if hsg_ds.crs != profile.get("crs"):
                hsg_arr = np.empty(nlcd.shape, dtype=np.uint8)
                reproject(
                    source=rasterio.band(hsg_ds, 1),
                    destination=hsg_arr,
                    src_transform=hsg_ds.transform,
                    src_crs=hsg_ds.crs,
                    dst_transform=profile["transform"],
                    dst_crs=profile["crs"],
                    resampling=Resampling.nearest,
                )
            else:
                hsg_arr = hsg_ds.read(1)
    else:
        hsg_arr = np.full(nlcd.shape, default_hsg, dtype=np.uint8)

    # Apply CN lookup table
    for nlcd_code, hsg_map in CN_TABLE.items():
        for hsg_val, cn_val in hsg_map.items():
            mask = (nlcd == nlcd_code) & (hsg_arr == hsg_val)
            cn_by_pixel[mask] = cn_val

    # Mask out nodata
    nodata_mask = nlcd == int(nodata_nlcd)
    cn_by_pixel[nodata_mask] = 0

    # Write output
    out_profile = profile.copy()
    out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(cn_by_pixel.astype(np.uint8), 1)

    valid = cn_by_pixel[cn_by_pixel > 0]
    print(f"  CN raster written: {output_path}")
    print(f"  Pixels: {len(valid):,}  |  Mean CN: {float(np.mean(valid)):.1f}  "
          f"|  Range: {int(np.min(valid))}–{int(np.max(valid))}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a spatially varying CN raster from NLCD + SSURGO HSG."
    )
    parser.add_argument("--nlcd", required=True, metavar="PATH",
                        help="NLCD 2021 land cover raster (.tif).")
    parser.add_argument("--hsg", default=None, metavar="PATH",
                        help="SSURGO Hydrologic Soil Group raster (.tif). "
                             "Integer codes: 1=A, 2=B, 3=C, 4=D. "
                             "Optional — defaults to HSG B if not provided.")
    parser.add_argument("--output", required=True, metavar="PATH",
                        help="Output CN raster path (.tif).")
    parser.add_argument("--default-hsg", type=int, default=HSG_DEFAULT,
                        choices=[1, 2, 3, 4], metavar="HSG",
                        help="Default HSG code when no HSG raster is provided (1=A,2=B,3=C,4=D).")
    args = parser.parse_args(argv)
    return build_cn_raster(
        nlcd_path=Path(args.nlcd),
        hsg_path=Path(args.hsg) if args.hsg else None,
        output_path=Path(args.output),
        default_hsg=args.default_hsg,
    )


if __name__ == "__main__":
    sys.exit(main())
