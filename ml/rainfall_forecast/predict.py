"""Engine 2 inference: latest NWP run -> exceedance probabilities per grid point and
per H3 cell.

    python -m ml.rainfall_forecast.predict --model gfs [--init 2022-06-13T00]

Output: data/processed/forecasts/<run>/rainfall_grid.parquet and rainfall_cells.parquet
    h3, lead_day, p_heavy, p_very_heavy, p_extreme, rain_mm_expected, color
"""
from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd
import xarray as xr

from ml.common.config import H3_RES_STATE, MODELS, PROCESSED
from ml.common.grid import nearest_grid_index
from ml.common.imd import enforce_monotone, rain_color
from ml.rainfall_forecast.features import build_features

MODEL_DIR = MODELS / "rainfall_forecast"


def predict_grid(nwp_run: xr.Dataset, model: str = "gfs") -> pd.DataFrame:
    meta = json.loads((MODEL_DIR / f"{model}_meta.json").read_text())
    df = build_features(nwp_run)
    X = df[meta["features"]]
    probs = {}
    for name in ("heavy", "very_heavy", "extreme"):
        key = "extremely_heavy" if name == "extreme" else name
        m = joblib.load(MODEL_DIR / f"{model}_{key}.joblib")
        probs[name] = m["iso"].predict(m["clf"].predict_proba(X)[:, 1])
    p_h, p_vh, p_x = enforce_monotone(probs["heavy"], probs["very_heavy"], probs["extreme"])
    out = df[["init", "lead_day", "lat", "lon"]].copy()
    out["p_heavy"], out["p_very_heavy"], out["p_extreme"] = p_h, p_vh, p_x
    out["rain_mm_expected"] = np.clip(joblib.load(MODEL_DIR / f"{model}_amount.joblib").predict(X), 0, None)
    out["color"] = [rain_color(a, b, c).value for a, b, c in zip(p_h, p_vh, p_x)]
    return out


def grid_to_h3(grid: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """Each hexagon inherits its 0.25° parent grid point. Honest about resolution:
    Engine 2 knows nothing finer than ~25 km — Engine 3 adds the local detail."""
    lats = np.sort(grid.lat.unique())
    lons = np.sort(grid.lon.unique())
    iy, ix = nearest_grid_index(lats, lons, cells.lat.values, cells.lon.values)
    key = pd.DataFrame({"h3": cells.h3.values, "lat": lats[iy], "lon": lons[ix]})
    return key.merge(grid, on=["lat", "lon"]).drop(columns=["lat", "lon"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gfs")
    ap.add_argument("--init")
    a = ap.parse_args()
    nwp = xr.open_zarr(PROCESSED / "nwp" / f"{a.model}_daily.zarr")
    run = nwp.sel(init=[np.datetime64(a.init)]) if a.init else nwp.isel(init=[-1])
    grid = predict_grid(run.load(), a.model)
    cells = pd.read_parquet(PROCESSED / "h3" / f"cells_res{H3_RES_STATE}.parquet")
    out_dir = PROCESSED / "forecasts" / pd.Timestamp(run.init.values[0]).strftime("%Y%m%d%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    grid.to_parquet(out_dir / "rainfall_grid.parquet", index=False)
    grid_to_h3(grid, cells).to_parquet(out_dir / "rainfall_cells.parquet", index=False)
    print(grid.groupby("lead_day")[["p_heavy", "p_very_heavy", "p_extreme"]].max())
