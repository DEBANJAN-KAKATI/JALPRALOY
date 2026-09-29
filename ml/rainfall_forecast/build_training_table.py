"""Join NWP forecasts (features) to IMD observed rainfall (target).

    python -m ml.rainfall_forecast.build_training_table --model gfs

Output: data/processed/training/rain_{model}.parquet — one row per
(init, lead_day, lat, lon) inside Assam + buffer, monsoon months only, with
rain_obs (mm) and y_heavy / y_very_heavy / y_extreme labels.

Alignment: GFS/ECMWF 0.25° and IMD 0.25° share grid points (.00/.25/.50/.75), so a
nearest-neighbour reindex is exact. The IMD day label convention must match the
NWP window — see IMD_DAY_LABEL in ml/common/config.py.
"""
from __future__ import annotations

import argparse

import pandas as pd
import xarray as xr

from ml.common.config import ASSAM_BBOX, IMD_DAY_LABEL, MONSOON_MONTHS, PROCESSED
from ml.common.imd import EXCEEDANCE_THRESHOLDS
from ml.rainfall_forecast.features import build_features

OUT_DIR = PROCESSED / "training"
BUFFER_DEG = 1.0


def main(model: str) -> None:
    nwp = xr.open_zarr(PROCESSED / "nwp" / f"{model}_daily.zarr")
    imd = xr.open_dataset(PROCESSED / "grids" / "imd_rain.nc")["rain_mm"]

    lon0, lat0, lon1, lat1 = ASSAM_BBOX
    box = dict(lat=slice(lat0 - BUFFER_DEG, lat1 + BUFFER_DEG), lon=slice(lon0 - BUFFER_DEG, lon1 + BUFFER_DEG))
    nwp = nwp.sel(**box)
    imd = imd.sel(**box).reindex(lat=nwp.lat, lon=nwp.lon, method="nearest", tolerance=0.01)

    df = build_features(nwp.load())
    # IMD date for the window that starts at valid_date 03 UTC:
    shift = pd.Timedelta(0) if IMD_DAY_LABEL == "start" else pd.Timedelta(days=1)
    obs = imd.to_dataframe().reset_index().rename(columns={"time": "imd_date", "rain_mm": "rain_obs"})
    df["imd_date"] = df["valid_date"] + shift
    df = df.merge(obs, on=["imd_date", "lat", "lon"], how="inner").drop(columns="imd_date")
    df = df[df["rain_obs"].notna() & df["valid_date"].dt.month.isin(MONSOON_MONTHS)]

    for name, thr in EXCEEDANCE_THRESHOLDS.items():
        df[f"y_{name}"] = (df["rain_obs"] >= thr).astype("int8")
    df["year"] = df["valid_date"].dt.year

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"rain_{model}.parquet"
    df.to_parquet(out, index=False)
    print(f"{len(df):,} rows -> {out}")
    print(df.groupby("year")[[c for c in df if c.startswith("y_")]].mean().round(4))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gfs")
    main(ap.parse_args().model)
