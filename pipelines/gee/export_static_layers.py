"""Export static rasters for Assam from Earth Engine to Google Drive (folder "jalproloi").
Download the GeoTIFFs into data/raw/gee/ afterwards.

    python -m pipelines.gee.export_static_layers                 # all layers, whole state
    python -m pipelines.gee.export_static_layers --pilot         # Kamrup Metro only (fast)
    python -m pipelines.gee.export_static_layers --only era5l --year 2022

Layers
    dem_glo30             Copernicus GLO-30 DSM, 30 m. It is a SURFACE model (roofs, trees);
                          for urban Guwahati consider FABDEM (forest/building-removed, free
                          for research) and drop it in data/raw/gee/dem_glo30.tif instead.
    landcover_fractions   ESA WorldCover v200 class fractions at 100 m
                          (bands: built, water, crop, tree, wetland, grass)
    jrc_occurrence        JRC Global Surface Water occurrence (%), 30 m
    merit_hand            MERIT Hydro HAND, ~90 m (a ready-made fallback for your own HAND)
    era5l_sm_{year}       ERA5-Land daily top-layer soil moisture, May–Oct, one band per day
"""
from __future__ import annotations

import argparse
import os

import ee

from ml.common.config import ASSAM_BBOX, PILOT_BBOX

FOLDER = "jalproloi"
WORLDCOVER = {"tree": 10, "grass": 30, "crop": 40, "built": 50, "water": 80, "wetland": 90}


def export(img: ee.Image, name: str, region: ee.Geometry, scale: float) -> None:
    task = ee.batch.Export.image.toDrive(
        image=img, description=name, folder=FOLDER, fileNamePrefix=name,
        region=region, scale=scale, crs="EPSG:4326", maxPixels=1e13)
    task.start()
    print(f"started {name}: {task.id}")


def dem(region):
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").filterBounds(region)
    return col.mosaic().setDefaultProjection(col.first().projection()).toFloat()


def landcover_fractions():
    lc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    bands = [lc.eq(v).rename(k) for k, v in WORLDCOVER.items()]
    return (ee.Image.cat(bands).toFloat()
            .reduceResolution(ee.Reducer.mean(), maxPixels=1024)
            .reproject(ee.Projection("EPSG:4326").atScale(100)))


def era5l_soil_moisture(year: int):
    col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
           .filterDate(f"{year}-05-01", f"{year}-11-01")
           .select("volumetric_soil_water_layer_1"))
    # One band per day, named sm_YYYYMMDD
    return col.toBands().regexpRename(r"^(\d{8})_.*", "sm_$1").toFloat()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--only", choices=["dem", "landcover", "jrc", "hand", "era5l"])
    ap.add_argument("--year", type=int, default=2022)
    a = ap.parse_args()
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    region = ee.Geometry.Rectangle(list(PILOT_BBOX if a.pilot else ASSAM_BBOX))
    tag = "_pilot" if a.pilot else ""
    jobs = {
        "dem": lambda: export(dem(region), f"dem_glo30{tag}", region, 30),
        "landcover": lambda: export(landcover_fractions(), f"landcover_fractions{tag}", region, 100),
        "jrc": lambda: export(ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0).toFloat(),
                              f"jrc_occurrence{tag}", region, 30),
        "hand": lambda: export(ee.Image("MERIT/Hydro/v1_0_1").select("hnd").toFloat(), f"merit_hand{tag}", region, 90),
        "era5l": lambda: export(era5l_soil_moisture(a.year), f"era5l_sm_{a.year}{tag}", region, 11132),
    }
    for key in ([a.only] if a.only else [k for k in jobs if k != "era5l"]):
        jobs[key]()
