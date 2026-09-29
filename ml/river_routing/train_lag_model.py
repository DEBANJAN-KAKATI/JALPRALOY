"""Engine 4a: forecast downstream Brahmaputra levels from upstream gauges.

    python -m ml.river_routing.train_lag_model [--value discharge_m3s]

For each downstream station × horizon: LightGBM on level change, compared with
persistence. Reports RMSE, NSE and (if danger levels are filled in gauges.csv) the
CSI of "above danger level" warnings.
"""
from __future__ import annotations

import argparse

import joblib
import lightgbm as lgb
import pandas as pd

from ml.common.config import HINDCAST_YEAR, MODELS, gauges_csv
from ml.evaluation.metrics import categorical_scores, nse, rmse
from ml.river_routing.features import load_wide, make_features, make_target, travel_time_h

HORIZONS_H = (6, 12, 24, 48, 72)
OUT = MODELS / "river_routing"


def main(value: str) -> None:
    gauges = pd.read_csv(gauges_csv()).sort_values("order")
    wide = load_wide(value)
    order = [s for s in gauges.station if s in wide]
    print("stations with data:", order)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    for i, target in enumerate(order):
        upstream = order[:i]
        if not upstream:
            continue
        for up in upstream:
            lag, corr = travel_time_h(wide[up], wide[target])
            print(f"travel time {up} -> {target}: ~{lag} h (r={corr:.2f})")
        X = make_features(wide, target, upstream)
        danger = gauges.set_index("station").get("danger_level_m", pd.Series(dtype=float)).get(target)
        for h in HORIZONS_H:
            y = make_target(wide, target, h)
            data = X.join(y).dropna(subset=[y.name])
            years = data.index.year
            train, test = data[years != HINDCAST_YEAR], data[years == HINDCAST_YEAR]
            if len(train) < 200:
                continue
            model = lgb.LGBMRegressor(n_estimators=800, learning_rate=0.03, num_leaves=31,
                                      min_child_samples=50, verbose=-1).fit(train[X.columns], train[y.name])
            joblib.dump({"model": model, "features": list(X.columns)}, OUT / f"{target}_{h}h.joblib")
            if test.empty:
                continue
            now = wide.loc[test.index, target]
            pred, obs = now + model.predict(test[X.columns]), now + test[y.name]
            row = {"station": target, "horizon_h": h, "rmse": rmse(pred, obs), "nse": nse(pred, obs),
                   "rmse_persistence": rmse(now, obs), "nse_persistence": nse(now, obs)}
            if value == "level_m" and pd.notna(danger):
                row["csi_danger"] = categorical_scores(obs >= danger, pred >= danger)["csi"]
            rows.append(row)

    scores = pd.DataFrame(rows)
    scores.to_csv(OUT / "scores.csv", index=False)
    print(scores.round(3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--value", default="level_m", choices=["level_m", "discharge_m3s"])
    main(ap.parse_args().value)
