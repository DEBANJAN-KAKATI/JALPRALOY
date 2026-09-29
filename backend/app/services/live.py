"""Live public data — REAL numbers from free APIs, cached and labelled with their source.

    Open-Meteo forecast   rain outlook (raw NWP, not yet bias-corrected by Engine 2)
    Open-Meteo Flood API  GloFAS modelled river discharge (not CWC gauge readings)
    GDACS                 flood events reported by the Global Disaster Alert system

Every fetch goes through `cached()`: fresh data is reused for `ttl` seconds; if an
upstream API fails we serve the last good copy and mark the source "cached"; with no
copy at all the endpoint returns 503 and the source shows "offline". The /api/status
endpoint exposes this so the UI never pretends stale data is live.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.imd import Color, rain_color_from_mm
from app.services.places import GAUGES, TOWNS

log = logging.getLogger(__name__)

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
FLOOD_API = "https://flood-api.open-meteo.com/v1/flood"
GDACS_API = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
REGION_BBOX = (84.0, 20.0, 100.0, 30.5)  # lon0, lat0, lon1, lat1 — NE India + neighbours
REGION_ISO3 = {"IND", "BGD", "BTN", "NPL", "MMR", "CHN"}
CLIMATOLOGY_YEARS = 10
SEASON_WINDOW_DAYS = 15


class LiveDataUnavailable(RuntimeError):
    pass


@dataclass
class SourceState:
    name: str
    status: str = "idle"  # idle | live | cached | offline
    updated: datetime | None = None
    detail: str = ""


STATUS: dict[str, SourceState] = {
    "open-meteo": SourceState("Open-Meteo rain forecast"),
    "glofas": SourceState("GloFAS river discharge"),
    "gdacs": SourceState("GDACS flood events"),
    "news": SourceState("Flood & disaster news"),
    "geocoder": SourceState("Place search (OpenStreetMap / Photon)"),
}
_CACHE: dict[str, tuple[float, Any]] = {}


async def get_json(url: str, params: dict) -> Any:
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0), headers={"User-Agent": "jalproloi/0.1"}) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def cached(key: str, source: str, ttl: float, fetch: Callable[[], Awaitable[Any]], force: bool = False) -> Any:
    now = time.time()
    hit = _CACHE.get(key)
    if not force and hit and now - hit[0] < ttl:
        return hit[1]
    state = STATUS[source]
    try:
        value = await fetch()
    except Exception as exc:  # network, HTTP or parse error
        log.warning("%s fetch failed: %s", source, exc)
        if hit:
            state.status = "cached"
            state.detail = f"upstream failed; showing data from {datetime.fromtimestamp(hit[0], timezone.utc):%d %b %H:%M} UTC"
            return hit[1]
        state.status, state.detail = "offline", str(exc)[:160]
        raise LiveDataUnavailable(source) from exc
    _CACHE[key] = (now, value)
    state.status, state.updated, state.detail = "live", datetime.now(timezone.utc), ""
    return value


def _as_list(payload: Any) -> list:
    return payload if isinstance(payload, list) else [payload]


# --- Rain outlook -------------------------------------------------------------
def parse_rain_days(daily: dict) -> list[dict]:
    out = []
    probs = daily.get("precipitation_probability_max") or [None] * len(daily["time"])
    for d, mm, p in zip(daily["time"], daily["precipitation_sum"], probs):
        mm = float(mm or 0.0)
        out.append({"date": d, "rain_mm": round(mm, 1), "probability": p, "color": rain_color_from_mm(mm)})
    return out


async def rain_outlook(lat: float, lon: float, days: int = 7, force: bool = False) -> dict:
    async def fetch():
        payload = await get_json(FORECAST_API, {
            "latitude": lat, "longitude": lon, "forecast_days": days, "timezone": "Asia/Kolkata",
            "daily": "precipitation_sum,precipitation_probability_max",
        })
        return parse_rain_days(payload["daily"])

    rows = await cached(f"rain:{lat:.2f}:{lon:.2f}:{days}", "open-meteo", 1800, fetch, force=force)
    return {"lat": lat, "lon": lon, "days": rows, "source": "open-meteo",
            "total_mm": round(sum(r["rain_mm"] for r in rows), 1), "max_mm": max(r["rain_mm"] for r in rows)}


async def town_outlook(days: int = 5, force: bool = False) -> list[dict]:
    async def fetch():
        payload = _as_list(await get_json(FORECAST_API, {
            "latitude": ",".join(str(t.lat) for t in TOWNS), "longitude": ",".join(str(t.lon) for t in TOWNS),
            "forecast_days": days, "timezone": "Asia/Kolkata", "daily": "precipitation_sum",
        }))
        return rank_towns([(t, parse_rain_days(p["daily"])) for t, p in zip(TOWNS, payload)])

    return await cached(f"towns:{days}", "open-meteo", 3600, fetch, force=force)


def rank_towns(rows) -> list[dict]:
    out = []
    for town, days in rows:
        peak = max(days, key=lambda d: d["rain_mm"])
        out.append({"name": town.name, "district": town.district, "lat": town.lat, "lon": town.lon,
                    "total_mm": round(sum(d["rain_mm"] for d in days), 1), "max_mm": peak["rain_mm"],
                    "max_date": peak["date"], "color": peak["color"]})
    return sorted(out, key=lambda r: (-r["max_mm"], -r["total_mm"]))


# --- River watch --------------------------------------------------------------
RIVER_LEVELS = [(0.75, Color.GREEN, "Normal"), (0.90, Color.YELLOW, "Above normal"),
                (0.97, Color.ORANGE, "High"), (1.01, Color.RED, "Very high")]


def season_values(series: dict[str, float], day: date, years: list[int]) -> list[float]:
    """Discharge within ±SEASON_WINDOW_DAYS of `day`'s calendar date in earlier years."""
    vals = []
    for y in years:
        centre = date(y, day.month, min(day.day, 28))
        for k in range(-SEASON_WINDOW_DAYS, SEASON_WINDOW_DAYS + 1):
            v = series.get((centre + timedelta(days=k)).isoformat())
            if v is not None:
                vals.append(v)
    return vals


def classify(value: float, reference: list[float]) -> tuple[float, Color, str]:
    if not reference:
        return float("nan"), Color.GREEN, "Unknown"
    pct = sum(v < value for v in reference) / len(reference)
    for upper, color, word in RIVER_LEVELS:
        if pct < upper:
            return pct, color, word
    return pct, Color.RED, "Very high"


def analyse_station(times: list[str], values: list[float | None], today: date) -> dict:
    series = {t: float(v) for t, v in zip(times, values) if v is not None}
    past = sorted(d for d in series if d <= today.isoformat())
    if not past:
        raise ValueError("no discharge up to today")
    now_d = past[-1]
    q_now = series[now_d]
    q_prev = series.get(past[-2]) if len(past) > 1 else None
    years = list(range(today.year - CLIMATOLOGY_YEARS, today.year))
    reference = sorted(season_values(series, date.fromisoformat(now_d), years))
    pct, color, word = classify(q_now, reference)

    change = None if q_prev is None else q_now - q_prev
    trend = "steady" if change is None or abs(change) < 0.01 * q_now else ("rising" if change > 0 else "falling")
    future = [(d, series[d]) for d in sorted(series) if d > now_d]
    peak = max(future, key=lambda t: t[1]) if future else (now_d, q_now)
    p_pct, p_color, p_word = classify(peak[1], season_values(series, date.fromisoformat(peak[0]), years))
    spark = [{"date": d, "q": round(series[d]), "forecast": d > now_d}
             for d in sorted(series) if (date.fromisoformat(now_d) - timedelta(days=30)).isoformat() <= d]
    return {
        "date": now_d, "discharge": round(q_now), "change_24h": None if change is None else round(change),
        "trend": trend, "percentile": round(pct, 3), "color": color, "status": word,
        "season_median": round(reference[len(reference) // 2]) if reference else None,
        # A "peak" only means something if the forecast actually rises above today.
        "rise_expected": peak[1] > 1.02 * q_now,
        "peak_date": peak[0], "peak_discharge": round(peak[1]), "peak_color": p_color, "peak_status": p_word,
        "series": spark,
    }


async def river_watch(force: bool = False) -> list[dict]:
    today = datetime.now(timezone.utc).date()

    async def fetch():
        payload = _as_list(await get_json(FLOOD_API, {
            "latitude": ",".join(str(g.glofas_lat) for g in GAUGES),
            "longitude": ",".join(str(g.glofas_lon) for g in GAUGES),
            "daily": "river_discharge",
            "start_date": date(today.year - CLIMATOLOGY_YEARS, 1, 1).isoformat(),
            "end_date": (today + timedelta(days=7)).isoformat(),
        }))
        out = []
        for g, p in zip(GAUGES, payload):
            s = analyse_station(p["daily"]["time"], p["daily"]["river_discharge"], today)
            out.append({"station": g.name, "order": g.order, "lat": g.lat, "lon": g.lon, **s})
        return out

    return await cached(f"rivers:{today}", "glofas", 6 * 3600, fetch, force=force)


# --- GDACS flood events -------------------------------------------------------
GDACS_COLOR = {"Green": Color.GREEN, "Orange": Color.ORANGE, "Red": Color.RED}


def filter_gdacs(features: list[dict]) -> dict[str, list[dict]]:
    lon0, lat0, lon1, lat1 = REGION_BBOX
    region, india = [], []
    for f in features:
        p = f.get("properties", {})
        lon, lat = f.get("geometry", {}).get("coordinates", [None, None])[:2]
        iso3 = {c.get("iso3") for c in p.get("affectedcountries") or []} | {p.get("iso3")}
        ev = {
            "id": f"{p.get('eventid')}-{p.get('episodeid')}", "name": p.get("name") or "Flood",
            "country": p.get("country", ""), "alert_level": p.get("alertlevel", "Green"),
            "color": GDACS_COLOR.get(p.get("alertlevel"), Color.GREEN), "from_date": p.get("fromdate"),
            "to_date": p.get("todate"), "is_current": str(p.get("iscurrent")).lower() == "true",
            "lat": lat, "lon": lon, "url": (p.get("url") or {}).get("report"),
        }
        if lat is not None and lon0 <= lon <= lon1 and lat0 <= lat <= lat1 and iso3 & REGION_ISO3:
            region.append(ev)
        elif "IND" in iso3:
            india.append(ev)
    severity = {"Green": 0, "Orange": 1, "Red": 2}

    def order(events: list[dict]) -> list[dict]:
        # current first, then most severe, then most recent (two stable sorts)
        events = sorted(events, key=lambda e: e["to_date"] or "", reverse=True)
        return sorted(events, key=lambda e: (not e["is_current"], -severity.get(e["alert_level"], 0)))

    return {"region": order(region), "india_other": order(india)[:5]}


async def flood_events(days: int = 45, force: bool = False) -> dict:
    today = datetime.now(timezone.utc).date()

    async def fetch():
        payload = await get_json(GDACS_API, {
            "eventlist": "FL", "fromDate": (today - timedelta(days=days)).isoformat(),
            "toDate": today.isoformat(), "alertlevel": "Green;Orange;Red",
        })
        return filter_gdacs(payload.get("features", []))

    return await cached(f"gdacs:{today}:{days}", "gdacs", 1800, fetch, force=force)


async def sync_all_sources() -> dict[str, Any]:
    """Force re-sync all live sources simultaneously and update timestamps."""
    import asyncio
    results = await asyncio.gather(
        rain_outlook(26.14, 91.73, days=7, force=True),
        town_outlook(days=5, force=True),
        river_watch(force=True),
        flood_events(days=45, force=True),
        return_exceptions=True
    )
    return {
        "synced": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"id": k, "name": s.name, "status": s.status, "updated": s.updated, "detail": s.detail}
            for k, s in STATUS.items()
        ]
    }
