"""Sentinel-1 SAR flood maps for past Assam monsoons — Engine 3 LABELS.

Radar sees through monsoon cloud; optical satellites don't. Method: change
detection (UN-SPIDER recommended practice): a pixel is flooded in a window when its
VV backscatter drops sharply versus the dry-season baseline AND is dark enough to be
open water, excluding permanent water, steep slopes and high HAND.

    python -m pipelines.gee.s1_flood_mapping frequency --years 2017 2018 2019 2020 2021 2023
    python -m pipelines.gee.s1_flood_mapping labels --year 2022 --cells-asset projects/<p>/assets/h3_res8

`frequency` -> GeoTIFF in Google Drive folder "jalproloi" (download to data/raw/gee/).
`labels`    -> CSV per year: h3, window_start, window_end, flooded, observed
               flooded  = fraction of the cell flooded
               observed = fraction of the cell with a valid radar look
               -> flood_frac = flooded / observed (compute in pandas)

!! Leakage: compute `frequency` from TRAINING years only. If the hindcast year is
   included, the susceptibility model is fed the answer.

Known limits: SAR double-bounce in dense urban areas hides street flooding (hence the
hand-curated Guwahati waterlogging list); vegetation-covered water is under-detected;
Sentinel-1 revisit was 12 days from Dec 2021 until Sentinel-1C (launched Dec 2024).
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta

import ee

from ml.common.config import ASSAM_BBOX

DIFF_DB = -3.0        # backscatter drop vs baseline (dB)
WATER_DB = -18.0      # absolute VV darkness for open water (dB)
MAX_SLOPE_DEG = 5
MAX_HAND_M = 20
WINDOW_DAYS = 12
SEASON = ("06-01", "10-01")
BASELINE = ("01-01", "03-31")
DRIVE_FOLDER = "jalproloi"


def init() -> None:
    ee.Initialize(project=os.environ["GEE_PROJECT"])


def aoi() -> ee.Geometry:
    return ee.Geometry.Rectangle(list(ASSAM_BBOX))


def s1_vv(region, start: str, end: str) -> ee.ImageCollection:
    return (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region).filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV"))


def static_mask(region) -> ee.Image:
    """1 where flooding is physically plausible and not permanent water."""
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0)
    dem_col = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").filterBounds(region)
    dem = dem_col.mosaic().setDefaultProjection(dem_col.first().projection())
    slope = ee.Terrain.slope(dem)
    hand = ee.Image("MERIT/Hydro/v1_0_1").select("hnd")
    return occurrence.lt(80).And(slope.lt(MAX_SLOPE_DEG)).And(hand.lt(MAX_HAND_M))


def flood_window(region, year: int, start: date, end: date, mask: ee.Image) -> ee.Image:
    b0, b1 = (f"{year}-{d}" for d in BASELINE)
    before = s1_vv(region, b0, b1).median().focal_median(50, "circle", "meters")
    after = s1_vv(region, start.isoformat(), end.isoformat()).min().focal_median(50, "circle", "meters")
    observed = after.mask().reduce(ee.Reducer.min()).unmask(0).And(mask)
    flooded = (after.subtract(before).lt(DIFF_DB).And(after.lt(WATER_DB))).unmask(0).And(observed)
    return flooded.rename("flooded").addBands(observed.rename("observed")).toFloat()


def windows(year: int):
    d = date.fromisoformat(f"{year}-{SEASON[0]}")
    end = date.fromisoformat(f"{year}-{SEASON[1]}")
    while d < end:
        yield d, min(d + timedelta(days=WINDOW_DAYS), end)
        d += timedelta(days=WINDOW_DAYS)


def export_frequency(years: list[int]) -> None:
    region, mask = aoi(), static_mask(aoi())
    imgs = [flood_window(region, y, s, e, mask) for y in years for s, e in windows(y)]
    col = ee.ImageCollection(imgs)
    freq = col.select("flooded").sum().divide(col.select("observed").sum().max(1)).rename("s1_flood_freq")
    task = ee.batch.Export.image.toDrive(
        image=freq.toFloat(), description=f"s1_flood_frequency_{years[0]}_{years[-1]}",
        folder=DRIVE_FOLDER, fileNamePrefix="s1_flood_frequency",
        region=region, scale=30, crs="EPSG:4326", maxPixels=1e13)
    task.start()
    print("started", task.id, "- watch it at https://code.earthengine.google.com/tasks")


def export_labels(year: int, cells_asset: str) -> None:
    """Per-H3 flood fractions for every window of one monsoon. Upload the H3 grid as a
    table asset first (see docs/ENGINE_3_INUNDATION.md, step A4)."""
    region, mask = aoi(), static_mask(aoi())
    cells = ee.FeatureCollection(cells_asset)
    tables = []
    for s, e in windows(year):
        stats = flood_window(region, year, s, e, mask).reduceRegions(
            collection=cells, reducer=ee.Reducer.mean(), scale=30, tileScale=4)
        stats = stats.map(lambda f, s=s, e=e: ee.Feature(None, {
            "h3": f.get("h3"), "flooded": f.get("flooded"), "observed": f.get("observed"),
            "window_start": s.isoformat(), "window_end": e.isoformat()}))
        tables.append(stats)
    merged = ee.FeatureCollection(tables).flatten()
    task = ee.batch.Export.table.toDrive(
        collection=merged, description=f"s1_labels_{year}", folder=DRIVE_FOLDER,
        fileNamePrefix=f"s1_labels_{year}", fileFormat="CSV",
        selectors=["h3", "window_start", "window_end", "flooded", "observed"])
    task.start()
    print("started", task.id)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frequency")
    f.add_argument("--years", type=int, nargs="+", required=True)
    lab = sub.add_parser("labels")
    lab.add_argument("--year", type=int, required=True)
    lab.add_argument("--cells-asset", required=True)
    a = ap.parse_args()
    init()
    if a.cmd == "frequency":
        export_frequency(a.years)
    else:
        export_labels(a.year, a.cells_asset)
