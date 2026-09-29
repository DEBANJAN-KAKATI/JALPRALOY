"""Exposure and vulnerability per H3 cell (Engine 4b inputs).

    python -m ml.impact.build_exposure --res 9 --pilot

Exposure
    population       WorldPop 2020 constrained 100 m (worldpop.org, IND) — zonal SUM
    hospitals, schools, shelters   OSM amenities (osmnx; for all of Assam use a Geofabrik
                     extract + pyrosm instead of the Overpass API)
    buildings        OSM or Google Open Buildings count
    road_km          OSM drivable road length
Vulnerability (0–1, higher = more vulnerable)
    kutcha_share     Census 2011 Houselisting tables (share of kutcha/semi-pucca houses)
                     joined by district/village; TODO — until then NaN
    dist_shelter_km  distance to nearest relief shelter (ASDMA relief camps if available,
                     else schools as a proxy)
Output: data/processed/features/exposure_res{R}[_pilot].parquet
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd

from ml.common.config import PILOT_BBOX, PROCESSED, RAW, UTM_CRS
from ml.common.grid import cells_to_gdf

WORLDPOP = RAW / "worldpop" / "ind_ppp_2020_constrained.tif"
OSM_TAGS = {
    "hospital": {"amenity": ["hospital", "clinic", "doctors"]},
    "school": {"amenity": ["school", "college", "university"]},
    "shelter": {"amenity": ["shelter"], "emergency": ["assembly_point"]},
}


def population(cells: gpd.GeoDataFrame) -> pd.DataFrame:
    from exactextract import exact_extract

    if not WORLDPOP.exists():
        print(f"missing {WORLDPOP}; population = NaN")
        return pd.DataFrame({"h3": cells.h3, "population": np.nan})
    df = exact_extract(str(WORLDPOP), cells, ["sum"], include_cols=["h3"], output="pandas")
    return df.rename(columns={"sum": "population"})


def osm_counts(cells: gpd.GeoDataFrame, bbox) -> pd.DataFrame:
    import osmnx as ox

    out = pd.DataFrame({"h3": cells.h3})
    points = {}
    for name, tags in OSM_TAGS.items():
        try:
            f = ox.features_from_bbox(bbox=bbox, tags=tags)
            f = gpd.GeoDataFrame(geometry=f.geometry.representative_point(), crs="EPSG:4326")
        except Exception as exc:  # no features of this type
            print(name, exc)
            f = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        points[name] = f
        joined = gpd.sjoin(f, cells[["h3", "geometry"]], predicate="within")
        out = out.merge(joined.groupby("h3").size().rename(name).reset_index(), on="h3", how="left")
    out = out.fillna(0)

    # Distance to nearest shelter (schools as fallback — they are the usual relief camps)
    shelters = pd.concat([points["shelter"], points["school"]]).to_crs(UTM_CRS)
    centroids = cells.to_crs(UTM_CRS).centroid
    if len(shelters):
        nearest = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=centroids, crs=UTM_CRS).assign(h3=cells.h3.values),
                                    shelters, distance_col="d")
        out = out.merge(nearest.groupby("h3")["d"].min().div(1000).rename("dist_shelter_km").reset_index(), on="h3", how="left")
    return out


def main(res: int, pilot: bool) -> None:
    suffix = f"res{res}" + ("_pilot" if pilot else "")
    cells_df = pd.read_parquet(PROCESSED / "h3" / f"cells_{suffix}.parquet")
    cells = cells_to_gdf(cells_df.h3)
    bbox = PILOT_BBOX  # TODO: state-wide via Geofabrik extract
    df = cells_df.merge(population(cells), on="h3", how="left").merge(osm_counts(cells, bbox), on="h3", how="left")
    df["kutcha_share"] = np.nan  # TODO: Census 2011 HLO join
    out = PROCESSED / "features" / f"exposure_{suffix}.parquet"
    df.to_parquet(out, index=False)
    print(df.describe().T.round(2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=9)
    ap.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    main(a.res, a.pilot)
