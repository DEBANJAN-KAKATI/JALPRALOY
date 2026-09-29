"""Engine 3, Part A — MILESTONE 1: static flood susceptibility.

    python -m ml.inundation.train_susceptibility --res 8
    python -m ml.inundation.train_susceptibility --res 9 --pilot     # Guwahati

"Which parts of Guwahati are most prone?" — answered from terrain, land cover and
flood history alone. No live data needed.

Label per cell: ever flooded (flood_frac >= 0.1) in any TRAINING-year window.
Test: does the model rank the cells that flooded in the held-out HINDCAST_YEAR highest?

Outputs
    ml/models/inundation/susceptibility_res{R}.joblib
    data/processed/features/susceptibility_res{R}[_pilot].parquet   h3, susceptibility, rank_pct
"""
from __future__ import annotations

import argparse

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from ml.common.config import HINDCAST_YEAR, MODELS, PROCESSED
from ml.evaluation.metrics import best_csi_threshold, categorical_scores
from ml.inundation.dataset import load_labels, static_columns

OUT = MODELS / "inundation"


def per_cell_labels(labels: pd.DataFrame, years) -> pd.Series:
    return labels[labels.year.isin(years)].groupby("h3")["flooded"].max()


def main(res: int, pilot: bool, drop_s1_freq: bool) -> None:
    suffix = f"res{res}" + ("_pilot" if pilot else "")
    static = pd.read_parquet(PROCESSED / "features" / f"static_{suffix}.parquet")
    if "is_permanent_water" in static:
        static = static[~static["is_permanent_water"]]
    feats = static_columns(static)
    if drop_s1_freq:
        feats = [f for f in feats if not f.startswith("s1_freq_")]

    labels = load_labels(res)
    train_years = sorted(set(labels.year) - {HINDCAST_YEAR})
    y_train = per_cell_labels(labels, train_years).rename("y")
    y_test = per_cell_labels(labels, [HINDCAST_YEAR]).rename("y")

    train = static.merge(y_train, left_on="h3", right_index=True)
    X = train[feats].fillna(train[feats].median())
    model = RandomForestClassifier(n_estimators=500, min_samples_leaf=5, class_weight="balanced_subsample",
                                   n_jobs=-1, random_state=0, oob_score=True)
    model.fit(X, train["y"])
    print(f"train cells {len(train):,}  flood rate {train.y.mean():.2%}  OOB acc {model.oob_score_:.3f}")

    static["susceptibility"] = model.predict_proba(static[feats].fillna(train[feats].median()))[:, 1]
    static["rank_pct"] = static["susceptibility"].rank(pct=True)

    if not y_test.empty:
        test = static.merge(y_test, left_on="h3", right_index=True)
        p, y = test["susceptibility"].values, test["y"].values
        thr, _ = best_csi_threshold(model.oob_decision_function_[:, 1], train["y"].values)
        s = categorical_scores(y, p >= thr)
        print(f"held-out {HINDCAST_YEAR}: ROC-AUC {roc_auc_score(y, p):.3f}  PR-AUC {average_precision_score(y, p):.3f} "
              f"(base rate {y.mean():.3f})  CSI {s['csi']:.3f} POD {s['pod']:.3f} FAR {s['far']:.3f} @p>={thr:.2f}")
        top = test.nlargest(max(1, int(0.1 * len(test))), "susceptibility")
        print(f"share of {HINDCAST_YEAR} flooded cells inside the top-10% most susceptible: "
              f"{top.y.sum() / max(1, y.sum()):.1%}")

    imp = pd.Series(model.feature_importances_, index=feats).sort_values(ascending=False)
    print("top features:\n", imp.head(10).round(3))

    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feats, "medians": train[feats].median()}, OUT / f"susceptibility_{suffix}.joblib")
    static[["h3", "lat", "lon", "susceptibility", "rank_pct"] + (["locality"] if "locality" in static else [])] \
        .to_parquet(PROCESSED / "features" / f"susceptibility_{suffix}.parquet", index=False)
    if "locality" in static:
        by_loc = static.groupby("locality")["susceptibility"].agg(["mean", "max", "count"]).sort_values("mean", ascending=False)
        print("most susceptible localities:\n", by_loc.head(10).round(3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=8)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--drop-s1-freq", action="store_true",
                    help="use if s1_flood_frequency.tif was built including the hindcast year")
    a = ap.parse_args()
    main(a.res, a.pilot, a.drop_s1_freq)
