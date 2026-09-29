"""Engine 3 inference: combine rainfall uncertainty with the dynamic flood model.

The flood model was trained on OBSERVED rain. At forecast time rain is uncertain, so
we integrate over rainfall scenarios weighted by Engine 2's category probabilities:

    P(flood) = Σ_k  P(rain in category k) · P(flood | rain = r_k, terrain, antecedent, river)

with categories below-heavy / heavy / very heavy / extremely heavy and
    P(below) = 1 - p_heavy,  P(heavy) = p_heavy - p_very_heavy,
    P(v.heavy) = p_very_heavy - p_extreme,  P(extreme) = p_extreme.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from ml.common.config import MODELS

# Representative 24-h rain for each category (mm). The below-heavy scenario uses the
# regression estimate capped at 64.4 instead of a fixed value.
SCENARIO_MM = {"heavy": 90.0, "very_heavy": 160.0, "extreme": 250.0}


def load(res: int = 8) -> dict:
    return joblib.load(MODELS / "inundation" / f"dynamic_res{res}.joblib")


def _with_new_rain(base: pd.DataFrame, add_mm: np.ndarray) -> pd.DataFrame:
    """Future rain `add_mm` falls on top of observed antecedent rain."""
    df = base.copy()
    for col in [c for c in df.columns if c.startswith("rain_") and c.endswith("d") and not c.startswith("rain_max")]:
        df[col] = df[col] + add_mm
    if "rain_max1d_7d" in df:
        df["rain_max1d_7d"] = np.maximum(df["rain_max1d_7d"], add_mm)
    return df


def predict_scenarios(features: pd.DataFrame, rain: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """features: one row per h3 with static + antecedent + river columns (as of issue time)
    rain: h3, p_heavy, p_very_heavy, p_extreme, rain_mm_expected (one lead day)"""
    df = features.merge(rain, on="h3", how="inner")
    model, feats = bundle["model"], bundle["features"]
    w = {
        "below": 1 - df.p_heavy,
        "heavy": df.p_heavy - df.p_very_heavy,
        "very_heavy": df.p_very_heavy - df.p_extreme,
        "extreme": df.p_extreme,
    }
    amounts = {"below": np.minimum(df.rain_mm_expected.values, 64.4), **{k: np.full(len(df), v) for k, v in SCENARIO_MM.items()}}
    p = np.zeros(len(df))
    for k, weight in w.items():
        p += weight.values * model.predict_proba(_with_new_rain(df, amounts[k])[feats])[:, 1]
    return pd.DataFrame({"h3": df.h3.values, "p_flood": np.clip(p, 0, 1)})


def predict_nowcast(features: pd.DataFrame, rain_mm_6h: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """0–6 h: deterministic nowcast accumulation added to antecedent rain.
    Limitation: the model is daily; a sub-daily model trained on IMERG is the upgrade."""
    df = features.merge(rain_mm_6h, on="h3", how="inner")
    p = bundle["model"].predict_proba(_with_new_rain(df, df.rain_mm_6h.values)[bundle["features"]])[:, 1]
    return pd.DataFrame({"h3": df.h3.values, "p_flood": p})


def combine_pluvial_fluvial(p_pluvial: np.ndarray, p_fluvial: np.ndarray) -> np.ndarray:
    """Either mechanism floods the cell. Independence is an approximation (both come
    from the same storm), so this is an upper-ish bound; document it as such."""
    return 1 - (1 - p_pluvial) * (1 - p_fluvial)
