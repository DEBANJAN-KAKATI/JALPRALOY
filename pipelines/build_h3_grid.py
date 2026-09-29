"""Tile Assam with H3 hexagons — the unit every engine predicts on.

    python -m pipelines.build_h3_grid              # res 8, whole state (~100k cells)
    python -m pipelines.build_h3_grid --pilot      # + res 9 for Kamrup Metropolitan

Outputs data/processed/h3/cells_res{R}[_pilot].parquet with columns:
    h3, res, district, lat, lon[, locality]

H3 assigns a cell to a polygon by its centroid, so district polygons that tile
the state give every cell exactly one district.
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import h3
import pandas as pd

from ml.common.config import BOUNDARIES, H3_RES_CITY, H3_RES_STATE, PILOT_DISTRICT, PROCESSED
from ml.common.grid import cell_centroids

OUT = PROCESSED / "h3"


def polyfill_districts(districts: gpd.GeoDataFrame, res: int) -> pd.DataFrame:
    frames = []
    for _, row in districts.iterrows():
        cells = h3.geo_to_cells(row.geometry, res)  # accepts shapely via __geo_interface__
        frames.append(pd.DataFrame({"h3": list(cells), "district": row["district"]}))
    df = pd.concat(frames, ignore_index=True).drop_duplicates("h3")
    df = df.merge(cell_centroids(df["h3"]), on="h3")
    df["res"] = res
    return df[["h3", "res", "district", "lat", "lon"]]


def attach_localities(cells: pd.DataFrame) -> pd.DataFrame:
    path = BOUNDARIES / "guwahati_localities.geojson"
    if not path.exists():
        print("No localities file; run prepare_boundaries --localities to name cells")
        return cells
    loc = gpd.read_file(path).to_crs("EPSG:32646")
    pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs="EPSG:4326").to_crs("EPSG:32646")
    joined = gpd.sjoin_nearest(pts, loc[["locality", "geometry"]], how="left", distance_col="locality_dist_m")
    joined = joined.drop_duplicates("h3")
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


def main(pilot: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    districts = gpd.read_file(BOUNDARIES / "assam_districts.geojson").to_crs("EPSG:4326")

    state = polyfill_districts(districts, H3_RES_STATE)
    state.to_parquet(OUT / f"cells_res{H3_RES_STATE}.parquet", index=False)
    print(f"res {H3_RES_STATE}: {len(state):,} cells")

    if pilot:
        d = districts[districts["district"].str.lower() == PILOT_DISTRICT.lower()]
        if d.empty:
            raise SystemExit(f"{PILOT_DISTRICT!r} not in districts file: {sorted(districts['district'])}")
        city = attach_localities(polyfill_districts(d, H3_RES_CITY))
        city.to_parquet(OUT / f"cells_res{H3_RES_CITY}_pilot.parquet", index=False)
        print(f"res {H3_RES_CITY} pilot: {len(city):,} cells")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    main(ap.parse_args().pilot)
