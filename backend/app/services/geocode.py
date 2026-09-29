"""Search-as-you-type, Google-Maps style.

Order of results:
  1. areas the flood model covers (instant, from the provider)
  2. our Assam towns (instant)
  3. any OpenStreetMap place — localities, villages, roads, hospitals, schools… —
     from Photon (komoot), a geocoder built for autocomplete, limited to NE India
     and biased towards the current map centre.
Nominatim's usage policy forbids autocomplete, which is why Photon is used here.
For production, self-host Photon with an India extract (docs/12_LIVE_DATA_SYNC.md).
"""
from __future__ import annotations

import os

from app.services.live import cached, get_json
from app.services.places import find_towns

PHOTON_API = os.environ.get("PHOTON_API", "https://photon.komoot.io/api/")  # self-host for production
NE_INDIA_BBOX = "88.0,21.9,97.5,29.5"  # lon0,lat0,lon1,lat1: Assam + neighbours + North Bengal

KIND_LABEL = {
    "city": "City", "town": "Town", "village": "Village", "hamlet": "Village", "suburb": "Locality",
    "neighbourhood": "Locality", "quarter": "Locality", "locality": "Locality", "district": "District",
    "county": "District", "state": "State", "hospital": "Hospital", "clinic": "Clinic", "school": "School",
    "college": "College", "university": "University", "river": "River", "stream": "Stream",
    "railway_station": "Station", "station": "Station", "aerodrome": "Airport", "bus_station": "Bus station",
}


def _photon_to_suggestion(f: dict) -> dict | None:
    p = f.get("properties", {})
    lon, lat = f.get("geometry", {}).get("coordinates", [None, None])[:2]
    name = p.get("name") or p.get("street")
    if not name or lat is None:
        return None
    value = p.get("osm_value", "")
    kind = KIND_LABEL.get(value) or ("Road" if p.get("osm_key") == "highway" else value.replace("_", " ").capitalize() or "Place")
    context = [p.get(k) for k in ("district", "city", "county", "state") if p.get(k) and p.get(k) != name]
    subtitle = ", ".join(dict.fromkeys(context))  # unique, in order
    return {"name": name, "subtitle": subtitle, "kind": kind, "center": (lat, lon), "source": "osm"}


async def photon(q: str, lat: float | None, lon: float | None, limit: int = 8) -> list[dict]:
    params: dict = {"q": q, "limit": limit, "bbox": NE_INDIA_BBOX}
    if lat is not None and lon is not None:
        params.update(lat=round(lat, 2), lon=round(lon, 2))  # rounded so nearby users share the cache

    async def fetch():
        payload = await get_json(PHOTON_API, params)
        rows = [s for s in (_photon_to_suggestion(f) for f in payload.get("features", [])) if s]
        seen, out = set(), []
        for s in rows:  # Photon often returns the same road as several segments
            key = (s["name"].lower(), s["subtitle"].lower(), s["kind"])
            if key not in seen:
                seen.add(key)
                out.append(s)
        return out

    return await cached(f"photon:{q.lower()}:{params.get('lat')}:{params.get('lon')}", "geocoder", 86400, fetch)


def local_suggestions(q: str) -> list[dict]:
    return [{"name": t.name, "subtitle": f"{t.district}, Assam" if t.district != t.name else "Assam",
             "kind": "Town", "center": (t.lat, t.lon), "source": "jalproloy"} for t in find_towns(q)[:4]]
