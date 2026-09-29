"""Upstream-gauge lag features for the Brahmaputra.

A rise at Dibrugarh / Neamatighat / Tezpur reaches Guwahati, then Goalpara and
Dhubri, after a travel time. We estimate that lag from data (don't hard-code it)
and give the model lagged upstream levels as features.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.common.config import PROCESSED

FREQ = "3h"
LAGS_H = (0, 6, 12, 24, 36, 48, 72)


def load_wide(value: str = "level_m") -> pd.DataFrame:
    """station columns × regular 3-hourly UTC index. Short gaps interpolated (≤ 9 h)."""
    df = pd.read_parquet(PROCESSED / "river" / "levels.parquet")
    df = df[df[value].notna()]
    wide = df.pivot_table(index="time", columns="station", values=value).sort_index()
    return wide.resample(FREQ).mean().interpolate(limit=3, limit_area="inside")


def travel_time_h(up: pd.Series, down: pd.Series, max_lag_h: int = 120) -> tuple[int, float]:
    """Lag (hours) maximising correlation of 24-h CHANGES (raw levels are dominated by
    the shared seasonal cycle, which hides the lag)."""
    step_h = pd.Timedelta(FREQ).total_seconds() / 3600
    per_day = int(24 / step_h)
    du, dd = up.diff(per_day), down.diff(per_day)
    best = (0, -1.0)
    for k in range(0, int(max_lag_h / step_h) + 1):
        c = du.shift(k).corr(dd)
        if pd.notna(c) and c > best[1]:
            best = (int(k * step_h), float(c))
    return best


def make_features(wide: pd.DataFrame, target: str, upstream: list[str]) -> pd.DataFrame:
    step_h = pd.Timedelta(FREQ).total_seconds() / 3600
    X = pd.DataFrame(index=wide.index)
    for st in [target, *upstream]:
        for lag in LAGS_H:
            X[f"{st}_lag{lag}"] = wide[st].shift(int(lag / step_h))
        X[f"{st}_d24"] = wide[st].diff(int(24 / step_h))
    doy = X.index.dayofyear
    X["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    # TODO: add sub-catchment rainfall (IMD/IMERG basin means for Subansiri, Jia Bharali,
    # Manas, Kopili...) — tributaries add water the main-stem gauges can't see coming.
    return X


def make_target(wide: pd.DataFrame, target: str, horizon_h: int) -> pd.Series:
    """Predict the CHANGE in level; adding it back to today's level is easier to learn
    and makes persistence the natural zero."""
    k = int(horizon_h / (pd.Timedelta(FREQ).total_seconds() / 3600))
    return (wide[target].shift(-k) - wide[target]).rename(f"dlevel_{horizon_h}h")
