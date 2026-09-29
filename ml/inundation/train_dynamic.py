"""Engine 3, Part B: dynamic flood model — P(cell flooded | terrain, rain, river, soil).

    python -m ml.inundation.train_dynamic --res 8

Rows are (cell, Sentinel-1 window). Cross-validation is grouped by YEAR (leave-one-
year-out) so a flood event never leaks between train and test; the HINDCAST_YEAR is
evaluated once, at the end. Neighbouring cells are strongly correlated, so random
row splits would report fantasy accuracy.

Outputs: ml/models/inundation/dynamic_res{R}.joblib (+ scores CSV)
"""
from __future__ import annotations

import argparse
import json

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from ml.common.config import HINDCAST_YEAR, MODELS, PROCESSED
from ml.evaluation.metrics import best_csi_threshold, brier_skill_score, categorical_scores
from ml.inundation.dataset import DYNAMIC_COLS, static_columns

OUT = MODELS / "inundation"
PARAMS = dict(n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=200,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)


def scores(y, p, thr) -> dict:
    s = categorical_scores(y, p >= thr)
    return {"auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p), "base_rate": float(np.mean(y)),
            "bss": brier_skill_score(p, y), "csi": s["csi"], "pod": s["pod"], "far": s["far"]}


def main(res: int) -> None:
    df = pd.read_parquet(PROCESSED / "training" / f"inundation_res{res}.parquet")
    feats = static_columns(df) + [c for c in DYNAMIC_COLS if c in df and df[c].notna().any()]
    dev = df[df.year != HINDCAST_YEAR]
    test = df[df.year == HINDCAST_YEAR]
    pos = dev.flooded.mean()
    params = {**PARAMS, "scale_pos_weight": min(30.0, (1 - pos) / max(pos, 1e-4))}

    # Leave-one-year-out CV on development years
    oof = pd.Series(np.nan, index=dev.index)
    iters = []
    for yr in sorted(dev.year.unique()):
        tr, va = dev[dev.year != yr], dev[dev.year == yr]
        if va.flooded.sum() == 0:
            continue
        m = lgb.LGBMClassifier(**params).fit(tr[feats], tr.flooded, eval_set=[(va[feats], va.flooded)],
                                             callbacks=[lgb.early_stopping(100, verbose=False)])
        oof.loc[va.index] = m.predict_proba(va[feats])[:, 1]
        iters.append(m.best_iteration_ or PARAMS["n_estimators"])
        print(yr, {k: round(v, 3) for k, v in scores(va.flooded, oof.loc[va.index], 0.5).items()})

    ok = oof.notna()
    thr, _ = best_csi_threshold(oof[ok], dev.flooded[ok])
    final = lgb.LGBMClassifier(**{**params, "n_estimators": int(np.median(iters))}).fit(dev[feats], dev.flooded)
    result = {"decision_prob": thr, "features": feats, "cv": scores(dev.flooded[ok], oof[ok], thr)}
    if not test.empty and test.flooded.sum():
        result["test"] = scores(test.flooded, final.predict_proba(test[feats])[:, 1], thr)
    print(json.dumps(result, indent=2, default=float))

    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "features": feats, "decision_prob": thr}, OUT / f"dynamic_res{res}.joblib")
    (OUT / f"dynamic_res{res}_scores.json").write_text(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=8)
    main(ap.parse_args().res)
