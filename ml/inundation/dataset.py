"""Build Engine 3 training tables.

    python -m ml.inundation.dataset --res 8

Inputs
    data/processed/features/static_res{R}.parquet     (pipelines/build_static_features.py)
    data/raw/gee/s1_labels_{year}.csv                 (pipelines/gee/s1_flood_mapping.py labels)
    data/processed/grids/imd_rain.nc                  (antecedent + event rainfall)
    data/processed/river/levels.parquet               (optional: main-stem river state)
    data/raw/gee/era5l_sm_{year}.tif                  (optional: soil moisture)
Output
    data/processed/training/inundation_res{R}.parquet — one row per (h3, window)

Label: flooded = flood_frac >= FLOOD_FRAC (share of the cell's observed area under
water). Rows with little valid radar coverage are dropped; permanent-water cells
are dropped (a river is not a flood).
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import xarray as xr

from ml.common.config import PROCESSED, RAW
from ml.common.grid import nearest_grid_index

FLOOD_FRAC = 0.10
MIN_OBSERVED = 0.5
RAIN_WINDOWS_D = (1, 3, 7, 15, 30)

# Feature groups. The dynamic model uses all; the susceptibility model only STATIC.
# s1_freq_* is static but derived from SAR history: must be computed on TRAIN years only.
STATIC_PREFIXES = ("elev_", "hand_", "slope_", "twi_", "dist_stream_", "lc_", "jrc_occ_", "s1_freq_", "log_hand")
DYNAMIC_COLS = [f"rain_{d}d" for d in RAIN_WINDOWS_D] + ["rain_max1d_7d", "river_q_anom", "soil_moisture"]


def static_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith(STATIC_PREFIXES)]


def load_labels(res: int) -> pd.DataFrame:
    """All exported label CSVs, restricted to cells of resolution `res`
    (res-8 state labels and res-9 pilot labels can share the folder)."""
    import h3

    files = sorted((RAW / "gee").glob("s1_labels_*.csv"))
    if not files:
        raise SystemExit("no s1_labels_*.csv in data/raw/gee — run pipelines.gee.s1_flood_mapping labels")
    lab = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    lab = lab[lab["h3"].map(h3.get_resolution) == res]
    lab = lab[lab["observed"] >= MIN_OBSERVED].copy()
    lab["flood_frac"] = lab["flooded"] / lab["observed"]
    lab["flooded"] = (lab["flood_frac"] >= FLOOD_FRAC).astype("int8")
    lab["window_end"] = pd.to_datetime(lab["window_end"])
    lab["year"] = lab["window_end"].dt.year
    return lab[["h3", "window_start", "window_end", "year", "flood_frac", "flooded"]]


def rainfall_features(cells: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Accumulated observed rain ending at each date, sampled at each cell's IMD grid point."""
    rain = xr.open_dataset(PROCESSED / "grids" / "imd_rain.nc")["rain_mm"].fillna(0).sortby(["lat", "lon"])
    iy, ix = nearest_grid_index(rain.lat.values, rain.lon.values, cells.lat.values, cells.lon.values)
    arr = rain.values  # (time, lat, lon)
    times = pd.DatetimeIndex(rain.time.values)
    frames = []
    for d in dates:
        end = times.searchsorted(d, side="right")  # include day d
        row = {"h3": cells.h3.values, "window_end": d}
        for w in RAIN_WINDOWS_D:
            row[f"rain_{w}d"] = arr[max(0, end - w):end, iy, ix].sum(axis=0)
        row["rain_max1d_7d"] = arr[max(0, end - 7):end, iy, ix].max(axis=0)
        frames.append(pd.DataFrame(row))
    return pd.concat(frames, ignore_index=True)


def river_features(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Brahmaputra state per window: discharge anomaly vs day-of-year climatology at
    Guwahati. TODO: per-cell nearest-reach mapping instead of one value for all."""
    path = PROCESSED / "river" / "levels.parquet"
    if not path.exists():
        return pd.DataFrame({"window_end": dates, "river_q_anom": np.nan})
    q = pd.read_parquet(path)
    q = q[q.station == "Guwahati"].set_index("time")["discharge_m3s"].tz_convert(None).resample("1D").mean()
    clim = q.groupby(q.index.dayofyear).transform("mean")
    anom = (q - clim) / clim.replace(0, np.nan)
    return pd.DataFrame({"window_end": dates, "river_q_anom": anom.reindex(dates, method="nearest").values})


def main(res: int) -> None:
    static = pd.read_parquet(PROCESSED / "features" / f"static_res{res}.parquet")
    if "is_permanent_water" in static:
        static = static[~static["is_permanent_water"]]
    labels = load_labels(res).merge(static[["h3"]], on="h3")
    dates = pd.DatetimeIndex(sorted(labels["window_end"].unique()))
    cells = static[static.h3.isin(labels.h3.unique())][["h3", "lat", "lon"]]

    df = (labels
          .merge(rainfall_features(cells, dates), on=["h3", "window_end"], how="left")
          .merge(river_features(dates), on="window_end", how="left")
          .merge(static, on="h3", how="left"))
    df["soil_moisture"] = np.nan  # TODO: sample era5l_sm_{year}.tif at cell centroids for window_end
    out = PROCESSED / "training" / f"inundation_res{res}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"{len(df):,} rows, flood rate {df.flooded.mean():.3%} -> {out}")
    print(df.groupby("year").flooded.agg(["count", "mean"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=8)
    main(ap.parse_args().res)
