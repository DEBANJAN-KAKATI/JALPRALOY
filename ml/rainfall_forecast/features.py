"""Feature engineering shared by training and prediction — one function, so the two
can never drift apart."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

NWP_VARS = ["tp_mm", "pwat", "cape", "rh850", "rh700", "u850", "v850"]


def neighbourhood(ds: xr.Dataset, var: str, size: int = 3) -> xr.Dataset:
    """NWP places rain in roughly the right area, not the exact pixel. Max/mean over a
    3×3 (≈75 km) window lets the model forgive small displacement errors."""
    r = ds[var].rolling(lat=size, lon=size, center=True, min_periods=1)
    return xr.Dataset({f"{var}_max{size}": r.max(), f"{var}_mean{size}": r.mean()})


def build_features(nwp: xr.Dataset, static: pd.DataFrame | None = None) -> pd.DataFrame:
    """nwp: dims (init, lead_day, lat, lon) with NWP_VARS.
    static: optional per-grid-point columns (lat, lon, elev_mean, ...).
    Returns one row per (init, lead_day, lat, lon)."""
    extra = [neighbourhood(nwp, "tp_mm", 3), neighbourhood(nwp, "tp_mm", 5), neighbourhood(nwp, "pwat", 3)]
    ds = xr.merge([nwp[NWP_VARS], *extra])
    ds["wind850"] = np.hypot(ds.u850, ds.v850)
    # Moisture transport proxy: southerly/westerly flow of moist air into the NE hills.
    ds["ivt_proxy"] = ds.pwat * ds.wind850
    df = ds.to_dataframe().reset_index()

    valid = pd.to_datetime(df["init"]) + pd.to_timedelta(df["lead_day"] - 1, unit="D")
    doy = valid.dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["valid_date"] = valid.dt.normalize()
    if static is not None:
        df = df.merge(static, on=["lat", "lon"], how="left")
    return df


FEATURES_EXCLUDE = {"init", "valid_date", "rain_obs", "year"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in FEATURES_EXCLUDE and not c.startswith("y_")]
