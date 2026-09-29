"""IMD 0.25° daily gridded rainfall — the training TARGET for Engine 2 and the
antecedent-rain source for Engine 3.

    python -m pipelines.ingest_imd --start 2000 --end 2025
    python -m pipelines.ingest_imd --realtime --days 10    # recent days (IMD real-time grids)

Output: data/processed/grids/imd_rain.nc  (time, lat, lon) mm/day, clipped to NOWCAST_BBOX.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

import numpy as np
import xarray as xr

from ml.common.config import NOWCAST_BBOX, PROCESSED, RAW

RAW_DIR = RAW / "imd"
OUT = PROCESSED / "grids" / "imd_rain.nc"


def _clip(ds: xr.Dataset) -> xr.Dataset:
    lon0, lat0, lon1, lat1 = NOWCAST_BBOX
    ds = ds.sortby("lat")
    return ds.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))


def _tidy(ds: xr.Dataset) -> xr.Dataset:
    ds = ds.rename({"rain": "rain_mm"}) if "rain" in ds else ds
    ds["rain_mm"] = ds["rain_mm"].where(ds["rain_mm"] > -998)  # -999 = outside India / missing
    ds["rain_mm"].attrs.update(units="mm/day", source="IMD 0.25deg gridded (Pai et al.)")
    return _clip(ds)


def historical(start_yr: int, end_yr: int) -> xr.Dataset:
    import imdlib as imd

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    imd.get_data("rain", start_yr, end_yr, fn_format="yearwise", file_dir=str(RAW_DIR))
    data = imd.open_data("rain", start_yr, end_yr, "yearwise", str(RAW_DIR))
    return _tidy(data.get_xarray())


def realtime(days: int) -> xr.Dataset:
    import imdlib as imd

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days)
    data = imd.get_real_data("rain", start.isoformat(), end.isoformat(), file_dir=str(RAW_DIR))
    return _tidy(data.get_xarray())


def check_day_alignment(imd: xr.DataArray, reference_daily: xr.DataArray) -> dict[int, float]:
    """Correlate IMD with an independent daily series (e.g. IMERG summed 03–03 UTC)
    shifted by -1/0/+1 day. The shift with the clearly highest correlation tells you
    how IMD labels its rainfall day — set IMD_DAY_LABEL in ml/common/config.py."""
    a = imd.mean(["lat", "lon"])
    b = reference_daily.mean(["lat", "lon"])
    out = {}
    for shift in (-1, 0, 1):
        s = b.shift(time=shift)
        both = xr.align(a, s, join="inner")
        out[shift] = float(np.corrcoef(both[0].values, both[1].values)[0, 1])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--end", type=int, default=date.today().year - 1)
    ap.add_argument("--realtime", action="store_true")
    ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if a.realtime:
        ds = realtime(a.days)
        ds.to_netcdf(OUT.with_name("imd_rain_realtime.nc"))
    else:
        ds = historical(a.start, a.end)
        ds.to_netcdf(OUT)
    print(ds)
