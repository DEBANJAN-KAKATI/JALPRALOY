"""The "why" panel: turn SHAP contributions into one plain sentence per cell.

    "low-lying: 2.8 m above nearest drainage · 140 mm rain in last 3 days · river rising"

Explainability wins trust with officials and judges. Keep templates short and
concrete; show at most three reasons, only those that INCREASE risk.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TEMPLATES = {
    "hand_mean": "low-lying: {v:.1f} m above nearest drainage",
    "hand_min": "low-lying: parts only {v:.1f} m above nearest drainage",
    "log_hand_min": "low-lying relative to nearby drains",
    "slope_mean": "flat ground ({v:.1f}°) — water drains slowly",
    "twi_mean": "water naturally collects here (wetness index {v:.1f})",
    "twi_max": "water naturally collects here",
    "dist_stream_min": "{v:.0f} m from a river or drain",
    "lc_built_mean": "{v:.0%} paved or built-up — little soaks in",
    "lc_wetland_mean": "wetland / beel area",
    "s1_freq_mean": "flooded in {v:.0%} of past monsoon satellite passes",
    "rain_1d": "{v:.0f} mm rain in 24 h",
    "rain_3d": "{v:.0f} mm rain in last 3 days",
    "rain_7d": "{v:.0f} mm rain in last 7 days — ground is saturated",
    "rain_15d": "wet fortnight: {v:.0f} mm in 15 days",
    "rain_max1d_7d": "a {v:.0f} mm downpour this week",
    "river_q_anom": "Brahmaputra flow {v:+.0%} vs normal for this date",
    "soil_moisture": "soil already wet ({v:.2f} m³/m³)",
}


def explain(model, X: pd.DataFrame, top_k: int = 3) -> list[list[dict]]:
    """Per-row list of the top positive contributors with human text."""
    import shap

    sv = shap.TreeExplainer(model).shap_values(X)
    sv = sv[1] if isinstance(sv, list) else sv  # binary classifiers may return [neg, pos]
    out = []
    for i in range(len(X)):
        order = np.argsort(-sv[i])
        reasons = []
        for j in order:
            if sv[i, j] <= 0 or len(reasons) == top_k:
                break
            col = X.columns[j]
            if col not in TEMPLATES:
                continue
            reasons.append({"feature": col, "contribution": float(sv[i, j]),
                            "text": TEMPLATES[col].format(v=float(X.iloc[i, j]))})
        out.append(reasons)
    return out


def sentence(reasons: list[dict]) -> str:
    return " · ".join(r["text"] for r in reasons) or "no single dominant factor"
