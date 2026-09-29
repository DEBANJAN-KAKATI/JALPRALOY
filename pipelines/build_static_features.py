"""Terrain + land-cover + flood-history features for every H3 cell (Engine 3 inputs).

    python -m pipelines.build_static_features terrain          # DEM -> HAND, slope, TWI, stream distance
    python -m pipelines.build_static_features zonal --res 8    # rasters -> per-cell table
    python -m pipelines.build_static_features zonal --res 9 --pilot

Inputs
    data/raw/gee/dem_glo30.tif              (pipelines/gee/export_static_layers.py) or FABDEM
    data/raw/gee/landcover_fractions.tif    bands: built, water, crop, tree, wetland, grass (0–1)
    data/raw/gee/jrc_occurrence.tif         % of time surface water, 1984–2021
    data/raw/gee/s1_flood_frequency.tif     fraction of monsoon S1 passes flooded (TRAIN years only!)
Outputs
    data/processed/terrain/*.tif            (UTM 46N, 30 m)
    data/processed/features/static_res{R}[_pilot].parquet

HAND (Height Above Nearest Drainage) is the single most useful flood feature:
a cell 1 m above the nearest channel floods far more easily than one 30 m above.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from ml.common.config import PROCESSED, RAW, UTM_CRS
from ml.common.grid import cells_to_gdf

TERRAIN = PROCESSED / "terrain"
GEE = RAW / "gee"
FEATURES = PROCESSED / "features"

# Flow-accumulation threshold (in 30 m cells) that defines a "stream".
# 1000 cells ≈ 0.9 km² catchment. Lower it for urban drains, raise it for rivers only.
STREAM_THRESHOLD_CELLS = 1000


def build_terrain(dem_path: Path) -> None:
    """DEM -> hydrologically conditioned derivatives with WhiteboxTools."""
    import rioxarray  # noqa: F401  (registers .rio)
    import xarray as xr
    from whitebox import WhiteboxTools

    TERRAIN.mkdir(parents=True, exist_ok=True)
    dem_utm = TERRAIN / "dem_utm.tif"
    if not dem_utm.exists():
        da = xr.open_dataarray(dem_path, engine="rasterio").squeeze(drop=True)
        da.rio.reproject(UTM_CRS, resolution=30).rio.to_raster(dem_utm)

    wbt = WhiteboxTools()
    wbt.set_working_dir(str(TERRAIN.resolve()))
    wbt.verbose = False
    # Breaching keeps real channels (roads/embankments) better than filling.
    wbt.breach_depressions_least_cost("dem_utm.tif", "dem_breached.tif", dist=100, fill=True)
    wbt.d8_flow_accumulation("dem_breached.tif", "flow_acc.tif", out_type="cells")
    wbt.extract_streams("flow_acc.tif", "streams.tif", threshold=STREAM_THRESHOLD_CELLS)
    wbt.elevation_above_stream("dem_breached.tif", "streams.tif", "hand.tif")
    wbt.slope("dem_breached.tif", "slope.tif", units="degrees")
    wbt.d8_flow_accumulation("dem_breached.tif", "sca.tif", out_type="specific contributing area")
    wbt.wetness_index("sca.tif", "slope.tif", "twi.tif")
    wbt.euclidean_distance("streams.tif", "dist_stream.tif")
    print("terrain rasters written to", TERRAIN)


def zonal(raster: Path, cells: gpd.GeoDataFrame, ops: list[str], prefix: str) -> pd.DataFrame:
    """Per-cell statistics with exactextract (fractional pixel coverage, fast C++)."""
    from exactextract import exact_extract

    with rasterio.open(raster) as src:
        crs = src.crs
        names = [d or f"b{i + 1}" for i, d in enumerate(src.descriptions)]
    vec = cells.to_crs(crs)
    df = exact_extract(str(raster), vec, ops, include_cols=["h3"], output="pandas")
    rename = {}
    for col in df.columns:
        if col == "h3":
            continue
        new = col
        # multi-band rasters come back as band_1_mean etc.; use the band descriptions
        for i, n in enumerate(names):
            new = new.replace(f"band_{i + 1}_", f"{n}_")
        rename[col] = f"{prefix}_{new}"
    return df.rename(columns=rename)


def build_zonal(res: int, pilot: bool) -> None:
    suffix = f"res{res}" + ("_pilot" if pilot else "")
    cells_df = pd.read_parquet(PROCESSED / "h3" / f"cells_{suffix}.parquet")
    cells = cells_to_gdf(cells_df["h3"])

    layers = [
        (TERRAIN / "dem_breached.tif", ["mean", "min", "stdev"], "elev"),
        (TERRAIN / "hand.tif", ["mean", "min", "median"], "hand"),
        (TERRAIN / "slope.tif", ["mean"], "slope"),
        (TERRAIN / "twi.tif", ["mean", "max"], "twi"),
        (TERRAIN / "dist_stream.tif", ["min", "mean"], "dist_stream"),
        (GEE / "landcover_fractions.tif", ["mean"], "lc"),
        (GEE / "jrc_occurrence.tif", ["mean", "max"], "jrc_occ"),
        (GEE / "s1_flood_frequency.tif", ["mean", "max"], "s1_freq"),
    ]
    out = cells_df.copy()
    for path, ops, prefix in layers:
        if not path.exists():
            print(f"skip {path.name} (missing)")
            continue
        out = out.merge(zonal(path, cells, ops, prefix), on="h3", how="left")
        print(f"added {prefix}")

    # Derived: permanent water cells are rivers/beels, not "floods". Flag, don't drop.
    if "jrc_occ_mean" in out:
        out["is_permanent_water"] = out["jrc_occ_mean"].fillna(0) > 80
    if "hand_min" in out:
        out["log_hand_min"] = np.log1p(out["hand_min"].clip(lower=0))

    FEATURES.mkdir(parents=True, exist_ok=True)
    out.to_parquet(FEATURES / f"static_{suffix}.parquet", index=False)
    print(f"{len(out):,} cells x {out.shape[1]} columns -> static_{suffix}.parquet")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("terrain")
    t.add_argument("--dem", type=Path, default=GEE / "dem_glo30.tif")
    z = sub.add_parser("zonal")
    z.add_argument("--res", type=int, default=8)
    z.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    if a.cmd == "terrain":
        build_terrain(a.dem)
    else:
        build_zonal(a.res, a.pilot)
