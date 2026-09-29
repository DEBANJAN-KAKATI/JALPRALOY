"""Engine 4b: risk = hazard × exposure × vulnerability, and the most/least affected ranking.

Primary ranking metric: EXPECTED AFFECTED POPULATION = Σ P(flood) × population.
It is in people, so officials can act on it and it adds up across levels
(cell -> locality -> circle -> district -> state). The composite index is shown as a
secondary 0–1 score for colouring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.common.imd import flood_color


def _norm(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.quantile(0.02), s.quantile(0.98)
    return ((s - lo) / (hi - lo)).clip(0, 1) if hi > lo else s * 0


def cell_risk(df: pd.DataFrame) -> pd.DataFrame:
    """df: h3, p_flood, population, hospital, school, kutcha_share, dist_shelter_km"""
    out = df.copy()
    pop = out["population"].fillna(0)
    out["expected_affected_pop"] = out["p_flood"] * pop
    zero = pd.Series(0.0, index=out.index)
    facilities = out.get("hospital", zero).fillna(0) * 3 + out.get("school", zero).fillna(0)
    exposure = 0.7 * _norm(np.log1p(pop)) + 0.3 * _norm(facilities)
    vuln_parts = [_norm(out[c]) for c in ("kutcha_share", "dist_shelter_km") if c in out and out[c].notna().any()]
    vulnerability = sum(vuln_parts) / len(vuln_parts) if vuln_parts else 0.5
    out["risk_index"] = out["p_flood"] * exposure * (0.5 + 0.5 * vulnerability)
    return out


def aggregate(cells: pd.DataFrame, by: str) -> pd.DataFrame:
    """Roll up to an area level (column `by` holds the area name)."""
    g = cells.groupby(by)
    pop = g["population"].sum()
    agg = pd.DataFrame({
        "p_flood_max": g["p_flood"].max(),
        "p_flood_popweighted": g.apply(lambda d: np.average(d.p_flood, weights=d.population.fillna(0) + 1e-9)),
        "expected_affected_pop": g["expected_affected_pop"].sum(),
        "population": pop,
        "cells_red": g["p_flood"].apply(lambda s: int((s >= 0.7).sum())),
        "risk_index": g["risk_index"].mean(),
    })
    agg["color"] = agg["p_flood_popweighted"].map(lambda p: flood_color(p).value)
    return agg.sort_values("expected_affected_pop", ascending=False).reset_index()


def rank(agg: pd.DataFrame, n: int = 5) -> dict[str, list[dict]]:
    cols = [agg.columns[0], "p_flood_popweighted", "expected_affected_pop", "color"]
    most = agg.head(n)[cols]
    least = agg.sort_values("p_flood_popweighted").head(n)[cols]
    return {"most_affected": most.to_dict("records"), "least_affected": least.to_dict("records")}
