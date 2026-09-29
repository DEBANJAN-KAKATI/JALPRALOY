import math

import h3
from fastapi import APIRouter, Depends, Query

from app.schemas import AreaHit, Located, Suggestion
from app.services import geocode
from app.services.geocoding import parse_direct
from app.services.inference import ForecastProvider, get_provider
from app.services.live import LiveDataUnavailable
from app.services.places import TOWNS, find_towns

router = APIRouter(prefix="/areas", tags=["areas"])


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


@router.get("/search", response_model=list[AreaHit])
def search(q: str = Query(min_length=1), provider: ForecastProvider = Depends(get_provider)):
    """Areas the flood model covers first, then towns (rain + river outlook only)."""
    direct = parse_direct(q)
    if direct:
        lat, lon, _ = direct
        area = provider.area_for_cell(h3.latlng_to_cell(lat, lon, 8))
        return [AreaHit(name=f"{lat:.4f}, {lon:.4f}", level="point", center=(lat, lon),
                        covered=area is not None, area=area)]
    hits = provider.search(q)
    covered = {h.name.lower() for h in hits}
    hits += [AreaHit(name=t.name, level="town", center=(t.lat, t.lon), covered=False, district=t.district)
             for t in find_towns(q) if t.name.lower() not in covered]
    return hits


@router.get("/locate", response_model=Located)
def locate(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
           provider: ForecastProvider = Depends(get_provider)):
    """'My location': is this point inside the hyperlocal model, and what's nearby?"""
    cell = h3.latlng_to_cell(lat, lon, 8)
    area = provider.area_for_cell(cell)
    town = min(TOWNS, key=lambda t: _km(lat, lon, t.lat, t.lon))
    return Located(lat=lat, lon=lon, h3=cell, covered=area is not None, area=area,
                   nearest_town=town.name, nearest_town_km=round(_km(lat, lon, town.lat, town.lon), 1))


@router.get("/suggest", response_model=list[Suggestion])
async def suggest(q: str = Query(min_length=1, max_length=100), lat: float | None = None, lon: float | None = None,
                  provider: ForecastProvider = Depends(get_provider)):
    """Search-as-you-type: covered areas, towns, then any OpenStreetMap place in NE India."""
    q = q.strip()
    rows: list[dict] = []
    direct = parse_direct(q)
    if direct:
        rows.append({"name": f"{direct[0]:.5f}, {direct[1]:.5f}", "subtitle": "Coordinates", "kind": "Point",
                     "center": (direct[0], direct[1]), "source": "jalproloy"})
    else:
        rows += [{"name": h.name, "subtitle": h.district or "", "kind": "Flood map", "center": h.center,
                  "source": "jalproloy"} for h in provider.search(q)]
        rows += geocode.local_suggestions(q)
        if len(q) >= 3:
            try:
                rows += await geocode.photon(q, lat, lon)
            except LiveDataUnavailable:
                pass  # OSM search down: local results still work

    out, seen = [], set()
    for r in rows:
        key = (r["name"].lower(), round(r["center"][0], 2), round(r["center"][1], 2))
        if key in seen:
            continue
        seen.add(key)
        area = provider.area_for_cell(h3.latlng_to_cell(r["center"][0], r["center"][1], 8))
        out.append(Suggestion(**r, covered=area is not None, area=area))
    return out[:10]
