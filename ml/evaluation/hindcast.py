"""Hindcast replay — the most convincing thing to show at SIH.

    python -m ml.evaluation.hindcast --event guwahati-2022-06 --lead-hours 72 48 24 12 6

Replays a real past flood: for each issue time before the event, run the whole
system using ONLY data that would have been available at that moment, then compare
the warnings with what actually happened (S1 flood maps, IMD rainfall, CWC levels,
the waterlogging list).

Leakage checklist (every item must be true):
  [ ] no model was trained, tuned or calibrated on the event year
  [ ] S1 flood-frequency feature excludes the event year
  [ ] inputs respect latency: IMERG Early ~4 h, GFS ~4–5 h, IMD daily next morning
  [ ] thresholds/colour rules were fixed before looking at the event
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from ml.common.config import PROCESSED

LATENCY = {"imerg_early": timedelta(hours=4), "gfs": timedelta(hours=5), "imd_daily": timedelta(hours=30)}


@dataclass
class Event:
    name: str
    area: str
    onset_utc: datetime        # when flooding/heavy rain began — take it from records, not from the model
    obs_window: tuple[str, str]
    notes: str = ""


EVENTS = {
    # Fill onset from IMD / ASDMA records before running. Keep the source in notes.
    "guwahati-2022-06": Event("guwahati-2022-06", "Kamrup Metropolitan",
                              datetime(2022, 6, 14, 0, 0), ("2022-06-14", "2022-06-18"),
                              notes="VERIFY onset time against IMD Guwahati / ASDMA reports"),
}


def latest_available(kind: str, issue: datetime) -> datetime:
    """Newest data timestamp usable at `issue` for a given product."""
    return issue - LATENCY[kind]


def replay(event: Event, lead_hours: list[int]) -> pd.DataFrame:
    rows = []
    for lead in lead_hours:
        issue = event.onset_utc - timedelta(hours=lead)
        # TODO: call pipelines.run_forecast engines with issue_time=issue, reading only
        # data <= latest_available(...). Then load that run's fused cell/area forecasts.
        rows.append({"event": event.name, "lead_h": lead, "issue_utc": issue,
                     "imerg_until": latest_available("imerg_early", issue),
                     "gfs_init": (issue - LATENCY["gfs"]).replace(hour=(issue - LATENCY["gfs"]).hour // 6 * 6,
                                                                 minute=0, second=0, microsecond=0),
                     "area_color": None, "p_flood_max": None, "hits_waterlogging_pts": None})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="guwahati-2022-06", choices=list(EVENTS))
    ap.add_argument("--lead-hours", type=int, nargs="+", default=[72, 48, 24, 12, 6])
    a = ap.parse_args()
    df = replay(EVENTS[a.event], a.lead_hours)
    out = PROCESSED / "hindcasts" / f"{a.event}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df)
