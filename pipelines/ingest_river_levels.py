"""River levels / discharge for Engine 4.

    python -m pipelines.ingest_river_levels snap                      # find main-stem GloFAS cells (once)
    python -m pipelines.ingest_river_levels glofas --past-days 92     # Open-Meteo GloFAS proxy
    python -m pipelines.ingest_river_levels glofas --start 1995-01-01 --end 2025-12-31
    python -m pipelines.ingest_river_levels import-csv path/to/wris_download.csv --station Guwahati

Output: data/processed/river/levels.parquet with columns
    station, time (UTC), level_m, discharge_m3s, source

Sources, best first:
  1. CWC gauge levels (FFS portal, ffs.india-water.gov.in) — the real thing. Historical
     series via India-WRIS or a formal request to CWC. Scrape gently if at all, and
     prefer a data request: IMD/CWC are the problem owners.
  2. GloFAS modelled discharge via the free Open-Meteo Flood API — no key, history
     from 1984 plus forecasts. Good for learning travel-time relationships while you
     wait for gauge data. It is discharge, not stage, and it is modelled.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests

from ml.common.config import PROCESSED, gauges_csv

OUT = PROCESSED / "river" / "levels.parquet"
FLOOD_API = "https://flood-api.open-meteo.com/v1/flood"


def load_gauges() -> pd.DataFrame:
    return pd.read_csv(gauges_csv()).sort_values("order")


def snap_to_main_stem(radius_steps: int = 3, step_deg: float = 0.05) -> pd.DataFrame:
    """GloFAS returns the river cell nearest to a point, which at a town is often a
    small tributary (e.g. ~6 m³/s at Guwahati instead of ~15,000 m³/s). Search a
    (2r+1)² neighbourhood and keep the cell with the highest mean discharge, i.e. the
    Brahmaputra main stem. Writes glofas_lat/glofas_lon into gauges.csv."""
    g = load_gauges()
    offsets = [(dy * step_deg, dx * step_deg) for dy in range(-radius_steps, radius_steps + 1)
               for dx in range(-radius_steps, radius_steps + 1)]
    best = []
    for _, row in g.iterrows():
        pts = [(round(row.lat + dy, 3), round(row.lon + dx, 3)) for dy, dx in offsets]
        resp = requests.get(FLOOD_API, params={
            "latitude": ",".join(str(p[0]) for p in pts), "longitude": ",".join(str(p[1]) for p in pts),
            "daily": "river_discharge", "past_days": 60, "forecast_days": 1}, timeout=120)
        resp.raise_for_status()
        means = [pd.Series(item["daily"]["river_discharge"], dtype=float).mean() for item in resp.json()]
        i = max(range(len(pts)), key=lambda k: means[k])
        best.append(pts[i])
        print(f"{row.station:12} -> {pts[i]}  mean {means[i]:,.0f} m³/s")
    g["glofas_lat"], g["glofas_lon"] = [p[0] for p in best], [p[1] for p in best]
    g.to_csv(gauges_csv(), index=False)
    # Sanity check: main-stem discharge should grow downstream.
    return g


def fetch_glofas(start: str | None = None, end: str | None = None, past_days: int = 92) -> pd.DataFrame:
    g = load_gauges()
    if g[["glofas_lat", "glofas_lon"]].isna().any().any():
        raise SystemExit("run `python -m pipelines.ingest_river_levels snap` first")
    params = {
        "latitude": ",".join(map(str, g.glofas_lat)),
        "longitude": ",".join(map(str, g.glofas_lon)),
        "daily": "river_discharge",
    }
    if start and end:
        params.update(start_date=start, end_date=end)
    else:
        params.update(past_days=past_days, forecast_days=30)
    resp = requests.get(FLOOD_API, params=params, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    payload = payload if isinstance(payload, list) else [payload]
    frames = []
    for station, item in zip(g.station, payload):
        d = item["daily"]
        frames.append(pd.DataFrame({
            "station": station,
            "time": pd.to_datetime(d["time"], utc=True),
            "level_m": float("nan"),
            "discharge_m3s": d["river_discharge"],
            "source": "glofas-openmeteo",
        }))
    return pd.concat(frames, ignore_index=True)


def fetch_cwc_current() -> pd.DataFrame:
    raise NotImplementedError(
        "Implement once you have confirmed CWC's data access terms. Record for each station: "
        "observation time (convert IST->UTC), level_m, trend, warning/danger levels. "
        "Store danger levels in data/static/gauges.csv."
    )


def import_csv(path: Path, station: str, time_col: str = "time", level_col: str = "level_m",
               tz: str = "Asia/Kolkata") -> pd.DataFrame:
    """Import a manual download (India-WRIS / CWC). Adjust column names to the file."""
    raw = pd.read_csv(path)
    t = pd.to_datetime(raw[time_col])
    t = t.dt.tz_localize(tz) if t.dt.tz is None else t
    return pd.DataFrame({
        "station": station, "time": t.dt.tz_convert("UTC"), "level_m": raw[level_col],
        "discharge_m3s": raw.get("discharge_m3s"), "source": f"csv:{path.name}",
    })


def append(df: pd.DataFrame) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        df = pd.concat([pd.read_parquet(OUT), df]).drop_duplicates(["station", "time", "source"], keep="last")
    df.sort_values(["station", "time"]).to_parquet(OUT, index=False)
    print(f"{len(df):,} rows -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("glofas")
    g.add_argument("--start")
    g.add_argument("--end")
    g.add_argument("--past-days", type=int, default=92)
    c = sub.add_parser("import-csv")
    c.add_argument("path", type=Path)
    c.add_argument("--station", required=True)
    sub.add_parser("cwc")
    sub.add_parser("snap")
    a = ap.parse_args()
    if a.cmd == "glofas":
        append(fetch_glofas(a.start, a.end, a.past_days))
    elif a.cmd == "snap":
        snap_to_main_stem()
    elif a.cmd == "import-csv":
        append(import_csv(a.path, a.station))
    else:
        append(fetch_cwc_current())
