"""GPM IMERG half-hourly rainfall (0.1°) — Engine 1 input and a daily rainfall proxy.

    python -m pipelines.ingest_imerg --start 2022-06-10 --end 2022-06-20            # history (Final/Late)
    python -m pipelines.ingest_imerg --latest 3                                       # last 3 h (Early run)

Output: data/processed/grids/imerg.zarr  var `rain_mmh` (time, lat, lon), appended per run.

Runs and latency (why this matters for "now"):
    Early  GPM_3IMERGHHE  ~4 h behind real time  -> live nowcasting (stale; see guide)
    Late   GPM_3IMERGHHL  ~14 h                  -> near-real-time analysis
    Final  GPM_3IMERGHH   ~3.5 months            -> training + hindcasts
For large historical pulls, Earth Engine's NASA/GPM_L3/IMERG_V07 is often faster.

Requires a NASA Earthdata login AND approving the "NASA GESDISC DATA ARCHIVE"
application in your Earthdata profile, or downloads fail with 401/403.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import xarray as xr

from ml.common.config import NOWCAST_BBOX, PROCESSED, RAW

RAW_DIR = RAW / "imerg"
OUT = PROCESSED / "grids" / "imerg.zarr"
PRODUCTS = {"early": "GPM_3IMERGHHE", "late": "GPM_3IMERGHHL", "final": "GPM_3IMERGHH"}


def download(start: datetime, end: datetime, run: str) -> list[Path]:
    import earthaccess

    earthaccess.login(strategy="environment")  # EARTHDATA_USERNAME / EARTHDATA_PASSWORD
    lon0, lat0, lon1, lat1 = NOWCAST_BBOX
    results = earthaccess.search_data(
        short_name=PRODUCTS[run], version="07",
        temporal=(start.isoformat(), end.isoformat()), bounding_box=(lon0, lat0, lon1, lat1),
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return [Path(p) for p in earthaccess.download(results, str(RAW_DIR))]


def open_imerg(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path, group="Grid", engine="h5netcdf", decode_times=True)
    da = ds["precipitation"]  # V07 name (V06 was precipitationCal), mm/h
    da = da.transpose("time", "lat", "lon")  # files are stored (time, lon, lat)
    lon0, lat0, lon1, lat1 = NOWCAST_BBOX
    da = da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    return da.rename("rain_mmh").to_dataset()


def to_zarr(paths: list[Path]) -> None:
    if not paths:
        print("nothing downloaded")
        return
    ds = xr.concat([open_imerg(p) for p in sorted(paths)], dim="time").sortby("time")
    idx = ds.indexes["time"]
    if hasattr(idx, "to_datetimeindex"):  # IMERG uses a Julian calendar -> cftime
        ds = ds.assign_coords(time=idx.to_datetimeindex())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        existing = xr.open_zarr(OUT)["time"].values
        ds = ds.sel(time=~ds["time"].isin(existing))
        if ds.sizes["time"]:
            ds.chunk({"time": 48}).to_zarr(OUT, append_dim="time")
    else:
        ds.chunk({"time": 48}).to_zarr(OUT)
    print(f"{ds.sizes.get('time', 0)} new frames -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--latest", type=int, help="hours back from now (Early run)")
    ap.add_argument("--run", choices=list(PRODUCTS), default="final")
    a = ap.parse_args()
    if a.latest:
        now = datetime.now(timezone.utc)
        files = download(now - timedelta(hours=a.latest + 6), now, "early")
    else:
        files = download(datetime.fromisoformat(a.start), datetime.fromisoformat(a.end), a.run)
    to_zarr(files)
