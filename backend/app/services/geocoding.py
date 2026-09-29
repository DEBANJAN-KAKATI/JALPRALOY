"""Place search. Order of lookup:
1. our own `areas` table (localities, circles, districts) — exact and fuzzy (pg_trgm)
2. H3 cell id typed directly
3. lat,lon typed directly
4. (optional) Nominatim for anything else — respect its usage policy: max 1 req/s,
   a real User-Agent, and cache results. Self-host Nominatim for production.
"""
from __future__ import annotations

import re

import h3

LATLON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_direct(q: str, res: int = 8) -> tuple[float, float, str] | None:
    """'26.14, 91.73' or an H3 id -> (lat, lon, h3)."""
    if h3.is_valid_cell(q.strip()):
        lat, lon = h3.cell_to_latlng(q.strip())
        return lat, lon, q.strip()
    m = LATLON.match(q)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return lat, lon, h3.latlng_to_cell(lat, lon, res)
    return None
