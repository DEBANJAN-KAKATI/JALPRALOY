"""Engine 4a inference: latest gauge state -> downstream level forecasts + warnings.

    python -m ml.river_routing.predict

Output rows: station, horizon_h, level_m, above_warning, above_danger, text
e.g. "Goalpara: expected to cross danger level in ~48 h".
"""
from __future__ import annotations

import joblib
import pandas as pd

from ml.common.config import MODELS, gauges_csv
from ml.river_routing.features import load_wide, make_features

MODEL_DIR = MODELS / "river_routing"


def predict_latest(value: str = "level_m") -> pd.DataFrame:
    gauges = pd.read_csv(gauges_csv()).sort_values("order").set_index("station")
    wide = load_wide(value)
    order = [s for s in gauges.index if s in wide]
    rows = []
    for i, target in enumerate(order[1:], start=1):
        X = make_features(wide, target, order[:i]).iloc[[-1]]
        now = float(wide[target].iloc[-1])
        for path in sorted(MODEL_DIR.glob(f"{target}_*h.joblib")):
            h = int(path.stem.split("_")[-1].rstrip("h"))
            b = joblib.load(path)
            level = now + float(b["model"].predict(X[b["features"]])[0])
            warn, danger = gauges.loc[target, "warning_level_m"], gauges.loc[target, "danger_level_m"]
            rows.append({
                "station": target, "horizon_h": h, "issue_time": wide.index[-1], "level_m": round(level, 2),
                "above_warning": bool(pd.notna(warn) and level >= warn),
                "above_danger": bool(pd.notna(danger) and level >= danger),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        first_danger = df[df.above_danger].groupby("station").horizon_h.min()
        df["text"] = df.station.map(lambda s: f"{s}: expected to cross danger level in ~{first_danger[s]} h"
                                    if s in first_danger else "")
    return df


if __name__ == "__main__":
    print(predict_latest())
