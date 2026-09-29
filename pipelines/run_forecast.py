"""The orchestrator: run engines for the current time, fuse them, publish.

    python -m pipelines.run_forecast --engines nowcast rainfall river fuse
    python -m pipelines.run_forecast --engines fuse --issue-time 2022-06-14T00:00   # hindcast replay

Each engine writes its own output under data/processed/forecasts/<run_id>/; `fuse`
combines the latest output of every engine into per-cell, per-horizon risk and
writes it to PostGIS for the API. See docs/07_INTEGRATION_API.md for the maths.

Engine output contracts (parquet, one row per cell × horizon):
    nowcast   h3, lead_min, rain_mm_6h, p_rain_gt_10mmh, eta_min, motion_u, motion_v
    rainfall  h3, lead_day, p_heavy, p_very_heavy, p_extreme, rain_mm_expected
    river     station, horizon_h, level_m, p_above_warning, p_above_danger
    inundation h3, horizon, p_flood, drivers(json)
    impact    area_id, horizon, expected_affected_pop, rank
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from ml.common.config import PROCESSED

FORECASTS = PROCESSED / "forecasts"


def run_nowcast(issue: datetime, out) -> None:
    # TODO(Engine 1): from ml.nowcast.pysteps_baseline import nowcast_for_issue_time
    raise NotImplementedError("Engine 1 — see docs/ENGINE_1_NOWCAST.md")


def run_rainfall(issue: datetime, out) -> None:
    # TODO(Engine 2): from ml.rainfall_forecast.predict import predict_latest
    raise NotImplementedError("Engine 2 — see docs/ENGINE_2_RAINFALL_FORECAST.md")


def run_river(issue: datetime, out) -> None:
    # TODO(Engine 4a): from ml.river_routing.predict import predict_latest
    raise NotImplementedError("Engine 4 — see docs/ENGINE_4_RIVER_IMPACT.md")


def run_fuse(issue: datetime, out) -> None:
    """1. load latest outputs of engines 1, 2, 4a
    2. Engine 3: p_flood per cell & horizon (ml.inundation.predict.predict_scenarios)
    3. Engine 4b: impact ranking per area (ml.impact.risk)
    4. colours (ml.common.imd), drivers (ml.inundation.explain)
    5. write cell_forecasts + area_forecasts tables; create/update alerts (backend/app/alerts)
    """
    raise NotImplementedError("Fusion — see docs/07_INTEGRATION_API.md")


ENGINES = {"nowcast": run_nowcast, "rainfall": run_rainfall, "river": run_river, "fuse": run_fuse}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", nargs="+", choices=list(ENGINES), required=True)
    ap.add_argument("--issue-time", help="UTC ISO time; default now. Hindcasts MUST only read data available then.")
    a = ap.parse_args()
    issue = datetime.fromisoformat(a.issue_time).replace(tzinfo=timezone.utc) if a.issue_time else datetime.now(timezone.utc)
    run_dir = FORECASTS / issue.strftime("%Y%m%d%H%M")
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in a.engines:
        ENGINES[name](issue, run_dir)
