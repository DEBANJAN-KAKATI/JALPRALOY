"""Helpers for moving between regular lat/lon grids and H3 hexagons."""
from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import Polygon

from ml.common.config import WGS84


def cell_centroids(cells: pd.Series | list[str]) -> pd.DataFrame:
    latlon = [h3.cell_to_latlng(c) for c in cells]
    return pd.DataFrame({"h3": list(cells), "lat": [p[0] for p in latlon], "lon": [p[1] for p in latlon]})


def cells_to_gdf(cells: pd.Series | list[str]) -> gpd.GeoDataFrame:
    """H3 cells → polygons in EPSG:4326. h3 returns (lat, lng); shapely wants (x=lng, y=lat)."""
    polys = [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in cells]
    return gpd.GeoDataFrame({"h3": list(cells)}, geometry=polys, crs=WGS84)


def sample_at_points(da: xr.DataArray, lats, lons, method: str = "nearest") -> xr.DataArray:
    """Vectorised point sampling. Returns da with a new 'point' dimension."""
    pts_lat = xr.DataArray(np.asarray(lats), dims="point")
    pts_lon = xr.DataArray(np.asarray(lons), dims="point")
    if method == "nearest":
        return da.sel(lat=pts_lat, lon=pts_lon, method="nearest")
    return da.interp(lat=pts_lat, lon=pts_lon, method=method)


def grid_to_cells(da: xr.DataArray, cells: pd.DataFrame, name: str, method: str = "nearest") -> pd.DataFrame:
    """Sample a (lat, lon[, extra dims]) field at H3 centroids → tidy DataFrame.

    `cells` needs columns h3, lat, lon (see cell_centroids).
    """
    sampled = sample_at_points(da, cells["lat"].values, cells["lon"].values, method=method)
    sampled = sampled.assign_coords(point=cells["h3"].values).rename({"point": "h3"})
    df = sampled.rename(name).to_dataframe().reset_index()
    return df.drop(columns=[c for c in ("lat", "lon") if c in df.columns])


def nearest_grid_index(grid_lats: np.ndarray, grid_lons: np.ndarray, lats, lons) -> tuple[np.ndarray, np.ndarray]:
    """Index of the nearest grid row/col for each point (grid axes must be sorted ascending)."""
    iy = np.clip(np.searchsorted(grid_lats, lats), 1, len(grid_lats) - 1)
    iy -= (np.abs(grid_lats[iy - 1] - lats) < np.abs(grid_lats[iy] - lats)).astype(int)
    ix = np.clip(np.searchsorted(grid_lons, lons), 1, len(grid_lons) - 1)
    ix -= (np.abs(grid_lons[ix - 1] - lons) < np.abs(grid_lons[ix] - lons)).astype(int)
    return iy, ix
