"""Engine 2: LightGBM bias-correction of NWP → P(heavy), P(very heavy), P(extremely heavy).

    python -m ml.rainfall_forecast.train_lgbm --model gfs

Design
  * One GLOBAL model with lat/lon/elevation/lead_day features instead of one model per
    grid cell: per-cell models see only ~150 monsoon days/year and overfit. The plan's
    "per grid cell" idea is recovered by the location features. Try per-region models
    (Brahmaputra valley / Barak valley / hills) as an experiment.
  * Three binary exceedance classifiers, then isotonic calibration on the validation
    year, then monotone clipping.
  * A Tweedie regressor for expected rainfall (mm) — what the UI shows as "Rain expected".
  * Split by YEAR. HINDCAST_YEAR is never used for training, tuning or calibration.
Every score is printed next to the raw-NWP baseline. If you can't beat raw NWP at a
lead time, say so and fall back to it there.
"""
from __future__ import annotations

import argparse
import json

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

from ml.common.config import HINDCAST_YEAR, MODELS, PROCESSED, VALIDATION_YEAR
from ml.common.imd import EXCEEDANCE_THRESHOLDS
from ml.evaluation.metrics import best_csi_threshold, brier_skill_score, categorical_scores
from ml.rainfall_forecast.features import feature_columns

OUT = MODELS / "rainfall_forecast"
PARAMS = dict(n_estimators=3000, learning_rate=0.03, num_leaves=63, min_child_samples=100,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)


def split(df: pd.DataFrame):
    test = df[df.year == HINDCAST_YEAR]
    val = df[df.year == VALIDATION_YEAR]
    train = df[~df.year.isin([HINDCAST_YEAR, VALIDATION_YEAR])]
    if train.empty or val.empty:
        raise SystemExit(f"need train years plus val year {VALIDATION_YEAR}; have {sorted(df.year.unique())}")
    return train, val, test


def report(name: str, y, p, thr_prob: float, raw_nwp_yes) -> dict:
    s = categorical_scores(y, p >= thr_prob)
    base = categorical_scores(y, raw_nwp_yes)
    return {
        "event": name, "n_events": int(np.sum(y)), "auc": float(roc_auc_score(y, p)) if 0 < np.sum(y) < len(y) else None,
        "bss": brier_skill_score(p, y), "csi": s["csi"], "pod": s["pod"], "far": s["far"],
        "csi_raw_nwp": base["csi"], "pod_raw_nwp": base["pod"], "far_raw_nwp": base["far"],
    }


def main(model: str) -> None:
    df = pd.read_parquet(PROCESSED / "training" / f"rain_{model}.parquet")
    feats = feature_columns(df)
    train, val, test = split(df)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"features": feats, "val_year": VALIDATION_YEAR, "test_year": HINDCAST_YEAR, "events": {}}
    rows = []

    for name, thr in EXCEEDANCE_THRESHOLDS.items():
        y = f"y_{name}"
        pos = train[y].mean()
        clf = lgb.LGBMClassifier(**PARAMS, scale_pos_weight=min(50.0, (1 - pos) / max(pos, 1e-4)))
        clf.fit(train[feats], train[y], eval_set=[(val[feats], val[y])],
                callbacks=[lgb.early_stopping(200, verbose=False)])
        # scale_pos_weight distorts probabilities -> recalibrate on the validation year
        iso = IsotonicRegression(out_of_bounds="clip").fit(clf.predict_proba(val[feats])[:, 1], val[y])
        p_val = iso.predict(clf.predict_proba(val[feats])[:, 1])
        thr_prob, _ = best_csi_threshold(p_val, val[y])
        joblib.dump({"clf": clf, "iso": iso}, OUT / f"{model}_{name}.joblib")
        meta["events"][name] = {"threshold_mm": thr, "decision_prob": thr_prob,
                                "best_iteration": int(clf.best_iteration_ or PARAMS["n_estimators"])}

        for split_name, part in (("val", val), ("test", test)):
            if part.empty or part[y].sum() == 0:
                continue
            for lead in sorted(part.lead_day.unique()):
                q = part[part.lead_day == lead]
                p = iso.predict(clf.predict_proba(q[feats])[:, 1])
                rows.append({"split": split_name, "lead_day": int(lead),
                             **report(name, q[y].values, p, thr_prob, q["tp_mm"].values >= thr)})

    reg = lgb.LGBMRegressor(**{**PARAMS, "objective": "tweedie", "tweedie_variance_power": 1.3})
    reg.fit(train[feats], train["rain_obs"], eval_set=[(val[feats], val["rain_obs"])],
            callbacks=[lgb.early_stopping(200, verbose=False)])
    joblib.dump(reg, OUT / f"{model}_amount.joblib")

    (OUT / f"{model}_meta.json").write_text(json.dumps(meta, indent=2))
    scores = pd.DataFrame(rows)
    scores.to_csv(OUT / f"{model}_scores.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(scores.round(3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gfs")
    main(ap.parse_args().model)
