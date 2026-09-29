"""Open-Meteo forecast API — free, no key. Use it to prototype the UI with REAL
forecast numbers before Engine 2 exists, and as an extra NWP-ensemble input later.

    python -m pipelines.ingest_openmeteo --district-centroids

Output: data/processed/forecasts/openmeteo_latest.parquet
    point_id, time (UTC), precipitation_mm, precipitation_probability

Not a substitute for Engines 1–2: it is raw model output, not bias-corrected for
Northeast India's terrain, and it knows nothing about floods.
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd
import requests

from ml.common.config import BOUNDARIES, PROCESSED

API = "https://api.open-meteo.com/v1/forecast"


def fetch(points: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    """points: columns point_id, lat, lon. Open-Meteo accepts comma-separated coords."""
    frames = []
    for chunk_start in range(0, len(points), 50):
        chunk = points.iloc[chunk_start:chunk_start + 50]
        resp = requests.get(API, params={
            "latitude": ",".join(f"{v:.4f}" for v in chunk.lat),
            "longitude": ",".join(f"{v:.4f}" for v in chunk.lon),
            "hourly": "precipitation,precipitation_probability",
            "forecast_days": days,
            "timezone": "UTC",
        }, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        payload = payload if isinstance(payload, list) else [payload]
        for pid, item in zip(chunk.point_id, payload):
            h = item["hourly"]
            frames.append(pd.DataFrame({
                "point_id": pid,
                "time": pd.to_datetime(h["time"], utc=True),
                "precipitation_mm": h["precipitation"],
                "precipitation_probability": h.get("precipitation_probability"),
            }))
    return pd.concat(frames, ignore_index=True)


def district_centroids() -> pd.DataFrame:
    d = gpd.read_file(BOUNDARIES / "assam_districts.geojson").to_crs("EPSG:4326")
    pts = d.geometry.representative_point()
    return pd.DataFrame({"point_id": d["district"], "lat": pts.y, "lon": pts.x})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--district-centroids", action="store_true")
    a = ap.parse_args()
    pts = district_centroids() if a.district_centroids else pd.DataFrame(
        {"point_id": ["Guwahati"], "lat": [26.1445], "lon": [91.7362]})
    df = fetch(pts)
    out = PROCESSED / "forecasts" / "openmeteo_latest.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    daily = df.set_index("time").groupby("point_id")["precipitation_mm"].resample("1D").sum()
    print(daily.unstack().round(1))
