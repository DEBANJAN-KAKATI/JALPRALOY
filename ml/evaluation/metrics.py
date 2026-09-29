"""Verification metrics IMD evaluators recognise, plus hydrology scores.

Categorical (yes/no event) scores come from the 2×2 contingency table:

                    observed yes   observed no
    forecast yes    hits           false alarms
    forecast no     misses         correct negatives

POD = hits / (hits + misses)                 — hit rate, want high
FAR = false alarms / (hits + false alarms)   — want low
CSI = hits / (hits + misses + false alarms)  — threat score, want high
Bias = (hits + false alarms) / (hits + misses) — 1 is unbiased
ETS = CSI corrected for hits expected by chance
"""
from __future__ import annotations

import numpy as np


def contingency(obs, fcst) -> dict[str, int]:
    o = np.asarray(obs, dtype=bool).ravel()
    f = np.asarray(fcst, dtype=bool).ravel()
    return {
        "hits": int(np.sum(f & o)),
        "misses": int(np.sum(~f & o)),
        "false_alarms": int(np.sum(f & ~o)),
        "correct_negatives": int(np.sum(~f & ~o)),
    }


def _div(a: float, b: float) -> float:
    return float(a / b) if b else float("nan")


def categorical_scores(obs, fcst) -> dict[str, float]:
    t = contingency(obs, fcst)
    h, m, fa, cn = t["hits"], t["misses"], t["false_alarms"], t["correct_negatives"]
    n = h + m + fa + cn
    hits_random = _div((h + m) * (h + fa), n)
    return {
        **t,
        "pod": _div(h, h + m),
        "far": _div(fa, h + fa),
        "csi": _div(h, h + m + fa),
        "bias": _div(h + fa, h + m),
        "ets": _div(h - hits_random, h + m + fa - hits_random),
    }


def brier(p, obs) -> float:
    p = np.asarray(p, dtype=float).ravel()
    o = np.asarray(obs, dtype=float).ravel()
    return float(np.mean((p - o) ** 2))


def brier_skill_score(p, obs, reference=None) -> float:
    """BSS > 0 means better than the reference (default: climatological base rate)."""
    o = np.asarray(obs, dtype=float).ravel()
    ref = np.full_like(o, o.mean()) if reference is None else np.asarray(reference, dtype=float).ravel()
    bs_ref = brier(ref, o)
    return float(1 - brier(p, o) / bs_ref) if bs_ref else float("nan")


def reliability_curve(p, obs, n_bins: int = 10) -> dict[str, np.ndarray]:
    """Mean forecast probability vs observed frequency per bin (plot against y = x)."""
    p = np.asarray(p, dtype=float).ravel()
    o = np.asarray(obs, dtype=float).ravel()
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    count = np.bincount(idx, minlength=n_bins)
    mean_p = np.bincount(idx, weights=p, minlength=n_bins) / np.maximum(count, 1)
    freq_o = np.bincount(idx, weights=o, minlength=n_bins) / np.maximum(count, 1)
    return {"mean_forecast": mean_p, "observed_freq": freq_o, "count": count}


def best_csi_threshold(p, obs, grid=None) -> tuple[float, float]:
    """Probability threshold that maximises CSI. Choose it on VALIDATION data only."""
    grid = np.linspace(0.05, 0.95, 19) if grid is None else grid
    best = (float("nan"), -1.0)
    for thr in grid:
        csi = categorical_scores(obs, np.asarray(p) >= thr)["csi"]
        if not np.isnan(csi) and csi > best[1]:
            best = (float(thr), float(csi))
    return best


def nse(sim, obs) -> float:
    """Nash–Sutcliffe efficiency: 1 perfect, 0 = as good as the mean, < 0 worse."""
    s = np.asarray(sim, dtype=float)
    o = np.asarray(obs, dtype=float)
    ok = ~(np.isnan(s) | np.isnan(o))
    s, o = s[ok], o[ok]
    return float(1 - np.sum((s - o) ** 2) / np.sum((o - o.mean()) ** 2))


def rmse(sim, obs) -> float:
    s = np.asarray(sim, dtype=float)
    o = np.asarray(obs, dtype=float)
    return float(np.sqrt(np.nanmean((s - o) ** 2)))
