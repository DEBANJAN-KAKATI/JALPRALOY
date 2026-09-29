"""Download Assam state + district boundaries, and Guwahati localities from OSM.

    python -m pipelines.prepare_boundaries            # state + districts
    python -m pipelines.prepare_boundaries --localities   # + Guwahati localities

Outputs (data/static/boundaries/):
    assam_state.geojson        one polygon
    assam_districts.geojson    column `district`
    guwahati_localities.geojson  points with `locality` (OSM place=suburb/neighbourhood/...)

geoBoundaries can lag administrative changes. Cross-check the district list
against the current LGD directory (lgdirectory.gov.in) before training.
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import requests

from ml.common.config import BOUNDARIES, PILOT_BBOX, ensure_dirs

GB_API = "https://www.geoboundaries.org/api/current/gbOpen/IND/{adm}/"


def fetch_geoboundaries(adm: str) -> gpd.GeoDataFrame:
    meta = requests.get(GB_API.format(adm=adm), timeout=60).json()
    return gpd.read_file(meta["gjDownloadURL"])


def build_state_and_districts() -> None:
    adm1 = fetch_geoboundaries("ADM1")
    assam = adm1[adm1["shapeName"].str.lower() == "assam"]
    if assam.empty:
        raise RuntimeError(f"Assam not found; names available: {sorted(adm1['shapeName'])}")
    assam[["shapeName", "geometry"]].to_file(BOUNDARIES / "assam_state.geojson", driver="GeoJSON")

    adm2 = fetch_geoboundaries("ADM2")
    inside = adm2.representative_point().within(assam.union_all())
    districts = adm2[inside][["shapeName", "shapeID", "geometry"]].rename(columns={"shapeName": "district"})
    districts.to_file(BOUNDARIES / "assam_districts.geojson", driver="GeoJSON")
    print(f"{len(districts)} districts written. Check against LGD:", sorted(districts["district"]))


def build_guwahati_localities() -> None:
    """OSM place nodes inside the pilot box. Each H3 res-9 cell later takes the
    name of its nearest locality point (a Voronoi assignment) — crude but effective.
    Replace with GMC ward polygons if you can obtain them."""
    import osmnx as ox

    west, south, east, north = PILOT_BBOX
    tags = {"place": ["suburb", "neighbourhood", "quarter", "locality", "village", "hamlet"]}
    gdf = ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)
    gdf = gdf[gdf["name"].notna()].copy()
    gdf["geometry"] = gdf.geometry.representative_point()
    out = gdf[["name", "place", "geometry"]].rename(columns={"name": "locality"}).reset_index(drop=True)
    out.to_file(BOUNDARIES / "guwahati_localities.geojson", driver="GeoJSON")
    print(f"{len(out)} localities written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--localities", action="store_true")
    args = ap.parse_args()
    ensure_dirs()
    build_state_and_districts()
    if args.localities:
        build_guwahati_localities()
