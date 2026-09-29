"""Turn a nowcast into the sentences people need:
"heavy rain cell moving NE at 25 km/h; expected over Kamrup Metro in 2–3 h".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ml.common.grid import sample_at_points

KM_PER_PIXEL = 10.0


def first_exceedance_minutes(rain_mmh: xr.DataArray, threshold: float) -> xr.DataArray:
    """Minutes until rain rate first exceeds threshold at each pixel (inf if never)."""
    exceed = rain_mmh > threshold
    lead = rain_mmh["lead"].astype(float)
    t = xr.where(exceed, lead, np.inf).min("lead")
    return t.rename("eta_min")


def eta_for_cells(ds: xr.Dataset, cells: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
    """Per-H3 ETA of heavy rain (cells: h3, lat, lon)."""
    eta = first_exceedance_minutes(ds["rain_mmh"], threshold)
    vals = sample_at_points(eta, cells.lat.values, cells.lon.values).values
    return pd.DataFrame({"h3": cells.h3.values, "eta_min": vals})


def motion_arrows(ds: xr.Dataset, stride: int = 8, min_rain_mmh: float = 1.0,
                  timestep_min: int = 30) -> pd.DataFrame:
    """Subsampled motion vectors where it is raining — for the map's arrows."""
    rain_now = ds["rain_mmh"].isel(lead=0)
    rows = []
    for iy in range(0, ds.sizes["lat"], stride):
        for ix in range(0, ds.sizes["lon"], stride):
            if float(rain_now[iy, ix]) < min_rain_mmh:
                continue
            u = float(ds["u"][iy, ix])  # pixels / timestep, +x = east
            v = float(ds["v"][iy, ix])  # pixels / timestep; pySTEPS +y = increasing row index
            if ds.lat[0] < ds.lat[-1]:
                v_north = v             # rows ascend with latitude -> +v is northward
            else:
                v_north = -v
            speed = np.hypot(u, v_north) * KM_PER_PIXEL * 60 / timestep_min
            bearing = (np.degrees(np.arctan2(u, v_north)) + 360) % 360  # 0 = moving north
            rows.append({"lat": float(ds.lat[iy]), "lon": float(ds.lon[ix]),
                         "speed_kmh": round(speed, 1), "bearing_deg": round(bearing)})
    return pd.DataFrame(rows)


def region_eta(ds: xr.Dataset, region_mask: xr.DataArray, threshold: float = 10.0,
               min_fraction: float = 0.05) -> float | None:
    """Minutes until at least `min_fraction` of the region exceeds the threshold."""
    exceed = (ds["rain_mmh"] > threshold).where(region_mask)
    frac = exceed.mean(["lat", "lon"])
    hit = frac["lead"].where(frac >= min_fraction, drop=True)
    return float(hit.min()) if hit.size else None
