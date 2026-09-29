"""NWP forecasts (GFS, ECMWF open data, NCUM) aggregated to IMD rainfall days.

    python -m pipelines.ingest_nwp gfs --init 2024-06-15T00      # one run
    python -m pipelines.ingest_nwp gfs --season 2023              # every 00Z run, May–Oct (training)
    python -m pipelines.ingest_nwp ecmwf                          # latest ECMWF open-data run

Output: data/processed/nwp/{model}_daily.zarr, dims (init, lead_day, lat, lon), vars:
    tp_mm      total precip in the IMD day window (03–03 UTC)
    pwat       precipitable water (kg/m²), window mean
    cape       surface CAPE (J/kg), window max
    rh850 rh700  relative humidity (%), window mean
    u850 v850    wind (m/s), window mean

IMD day d for a 00Z run covers forecast hours [3 + 24(d-1), 3 + 24d].
Engine 2 needs ARCHIVED FORECASTS for training, not analyses: GFS 0.25° is on AWS
Open Data from 2021 (Herbie fetches it); GEFS reforecast v12 covers 2000–2019.
"""
from __future__ import annotations

import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import xarray as xr

from ml.common.config import IMD_DAY_END_UTC_HOUR, NOWCAST_BBOX, PROCESSED, RAW

OUT_DIR = PROCESSED / "nwp"
LEAD_DAYS = 5
STEP_H = 6

# Herbie regex search strings against the GRIB .idx inventory. GFS files carry both
# 6-h bucket and since-init accumulations; we take "0-N hour acc" and difference it.
GFS_FIELDS = {
    "apcp": ":APCP:surface:0-[0-9]+ hour acc",
    "pwat": ":PWAT:entire atmosphere",
    "cape": ":CAPE:surface:",
    "rh850": ":RH:850 mb:",
    "rh700": ":RH:700 mb:",
    "u850": ":UGRD:850 mb:",
    "v850": ":VGRD:850 mb:",
}


def _clip(da: xr.DataArray) -> xr.DataArray:
    lon0, lat0, lon1, lat1 = NOWCAST_BBOX
    da = da.rename({"latitude": "lat", "longitude": "lon"}) if "latitude" in da.dims else da
    da = da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby(["lat", "lon"])
    return da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))


def gfs_run(init: datetime) -> xr.Dataset:
    from herbie import Herbie

    first = IMD_DAY_END_UTC_HOUR
    hours = list(range(first, first + 24 * LEAD_DAYS + 1, STEP_H))  # 3, 9, 15, ..., 123
    fields: dict[str, list[xr.DataArray]] = {k: [] for k in GFS_FIELDS}
    for fxx in hours:
        H = Herbie(init, model="gfs", product="pgrb2.0p25", fxx=fxx, save_dir=RAW / "nwp")
        for key, search in GFS_FIELDS.items():
            if key == "apcp" and (fxx - first) % 24:
                continue  # accumulations are only needed at day boundaries
            try:
                ds = H.xarray(search, remove_grib=False)
            except Exception as exc:  # missing field at this step (check with H.inventory())
                print(f"f{fxx:03d} {key}: {exc}")
                continue
            name = [v for v in ds.data_vars if v != "gribfile_projection"][0]
            da = ds[name]
            da = da.drop_vars([c for c in da.coords if c not in ("latitude", "longitude")])
            fields[key].append(_clip(da).expand_dims(fxx=[fxx]))

    stacked = {k: xr.concat(v, "fxx") for k, v in fields.items() if v}
    days = []
    for d in range(1, LEAD_DAYS + 1):
        lo, hi = first + 24 * (d - 1), first + 24 * d
        apcp = stacked["apcp"]
        tp = apcp.sel(fxx=hi) - apcp.sel(fxx=lo)  # both are "0-N hour acc" totals
        win = lambda k: stacked[k].sel(fxx=slice(lo, hi))  # noqa: E731
        days.append(xr.Dataset({
            "tp_mm": tp.clip(min=0),
            "pwat": win("pwat").mean("fxx"),
            "cape": win("cape").max("fxx"),
            "rh850": win("rh850").mean("fxx"),
            "rh700": win("rh700").mean("fxx"),
            "u850": win("u850").mean("fxx"),
            "v850": win("v850").mean("fxx"),
        }).expand_dims(lead_day=[d]))
    return xr.concat(days, "lead_day").expand_dims(init=[np.datetime64(init)])


def ecmwf_latest() -> xr.Dataset:
    """ECMWF IFS open data (0.25°). Archive on AWS only goes back to early 2023,
    so use it as a second live input and for recent-year validation."""
    from ecmwf.opendata import Client

    target = RAW / "nwp" / "ecmwf_latest.grib2"
    target.parent.mkdir(parents=True, exist_ok=True)
    steps = list(range(0, 24 * LEAD_DAYS + 1, 6))
    Client(source="ecmwf").retrieve(type="fc", param=["tp", "tcwv"], step=steps, target=str(target))
    ds = xr.open_dataset(target, engine="cfgrib")
    # TODO: difference tp (metres, since-init) into IMD day windows exactly as in gfs_run,
    # convert to mm (*1000), and add pressure-level r/u/v with levtype="pl", levelist=[850, 700].
    return ds


def ncum_latest() -> xr.Dataset:
    raise NotImplementedError(
        "NCMRWF NCUM: request access from NCMRWF (ncmrwf.gov.in); files arrive as GRIB2/NetCDF. "
        "Once you have them, reuse the same day-window aggregation as gfs_run."
    )


def save(ds: xr.Dataset, model: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{model}_daily.zarr"
    if path.exists():
        ds.to_zarr(path, append_dim="init")
    else:
        ds.to_zarr(path)
    print(f"saved {dict(ds.sizes)} -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=["gfs", "ecmwf", "ncum"])
    ap.add_argument("--init", help="e.g. 2024-06-15T00")
    ap.add_argument("--season", type=int, help="year: every 00Z run May–Oct")
    a = ap.parse_args()
    if a.model == "gfs":
        inits = (pd.date_range(f"{a.season}-05-01", f"{a.season}-10-31", freq="D")
                 if a.season else [pd.Timestamp(a.init or pd.Timestamp.utcnow().floor("D").tz_localize(None))])
        for init in inits:
            save(gfs_run(init.to_pydatetime()), "gfs")
    elif a.model == "ecmwf":
        print(ecmwf_latest())
    else:
        ncum_latest()
