"""Synthetic demo provider — lets the frontend be built before any model exists.

Everything here is FAKE and labelled `source="synthetic-demo"`. Zone names are
deliberately generic ("Demo zone 3") so nobody mistakes them for predictions about
real localities.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone

import h3

from app.core.imd import Color, flood_color, rain_color_from_mm
from app.schemas import (Alert, AreaCells, AreaHit, AreaSummary, CellDetail, CellRisk, Driver, Horizon,
                         RankedArea)

SOURCE = "synthetic-demo"
GUWAHATI = (26.1445, 91.7362)
HORIZON_HOURS = {"now": 0, "6h": 6, "24h": 24, "72h": 72, "120h": 120}
# Synthetic storm: builds to a peak at 24 h, then recedes.
HORIZON_SCALE = {"now": 0.35, "6h": 0.6, "24h": 1.0, "72h": 0.75, "120h": 0.45}
# (lat, lon, spread in degrees, peak) of synthetic "low-lying" hotspots — kept tight so the
# map shows a few clear hotspots instead of a carpet of colour.
BUMPS = [(26.170, 91.765, 0.016, 0.95), (26.135, 91.700, 0.014, 0.80), (26.115, 91.800, 0.012, 0.70)]
# Demo footprint: Guwahati's south bank. Cells north of this rough Brahmaputra bank line
# (lon, lat) are the river itself and are dropped, as permanent water will be in the real model.
RIVER_BANK = [(91.58, 26.150), (91.66, 26.165), (91.70, 26.175), (91.74, 26.190), (91.80, 26.195), (91.88, 26.205)]
FOOTPRINT = (91.60, 26.070, 91.86)  # lon0, lat0, lon1


def _south_of_river(lat: float, lon: float) -> bool:
    for (x0, y0), (x1, y1) in zip(RIVER_BANK, RIVER_BANK[1:]):
        if x0 <= lon <= x1:
            return lat < y0 + (y1 - y0) * (lon - x0) / (x1 - x0)
    return False
ALIASES = {"guwahati": "Guwahati", "kamrup metropolitan": "Guwahati", "kamrup metro": "Guwahati"}


def _noise(cell: str) -> float:
    return int(hashlib.md5(cell.encode()).hexdigest()[:6], 16) / 0xFFFFFF - 0.5


class DemoProvider:
    def __init__(self, res: int = 8, k: int = 16):
        center = h3.latlng_to_cell(*GUWAHATI, res)
        lon0, lat0, lon1 = FOOTPRINT
        self.cells = sorted(c for c in h3.grid_disk(center, k)
                            if lon0 <= h3.cell_to_latlng(c)[1] <= lon1 and h3.cell_to_latlng(c)[0] >= lat0
                            and _south_of_river(*h3.cell_to_latlng(c)))
        parents = sorted({h3.cell_to_parent(c, res - 2) for c in self.cells},
                         key=lambda p: (-h3.cell_to_latlng(p)[0], h3.cell_to_latlng(p)[1]))
        self.zone_of = {c: f"Demo zone {parents.index(h3.cell_to_parent(c, res - 2)) + 1}" for c in self.cells}

    # --- helpers -------------------------------------------------------------
    def resolve(self, name: str) -> str | None:
        return ALIASES.get(name.strip().lower())

    def _p(self, cell: str, horizon: Horizon) -> float:
        lat, lon = h3.cell_to_latlng(cell)
        base = sum(peak * math.exp(-((lat - la) ** 2 + (lon - lo) ** 2) / (2 * s ** 2)) for la, lo, s, peak in BUMPS)
        return max(0.0, min(1.0, base * HORIZON_SCALE[horizon] + 0.025 * _noise(cell) + 0.02))

    def _rain(self, cell: str, horizon: Horizon) -> float:
        lat, lon = h3.cell_to_latlng(cell)
        return round(max(0.0, (40 + 160 * math.exp(-((lat - 26.2) ** 2) / 0.02)) * HORIZON_SCALE[horizon]
                         + 4 * _noise(cell[::-1])), 1)

    def _cell(self, cell: str, horizon: Horizon) -> CellRisk:
        p, r = self._p(cell, horizon), self._rain(cell, horizon)
        return CellRisk(h3=cell, p_flood=round(p, 3), color=flood_color(p), rain_mm=r, rain_color=rain_color_from_mm(r))

    # --- provider interface -------------------------------------------------
    def search(self, q: str) -> list[AreaHit]:
        q = q.strip().lower()
        if q and any(q in alias or alias in q for alias in ALIASES):
            return [AreaHit(name="Guwahati", level="district", center=GUWAHATI, covered=True, area="Guwahati",
                            district="Kamrup Metropolitan")]
        return []

    def area_cells(self, name: str, horizon: Horizon) -> AreaCells:
        return AreaCells(name=name, horizon=horizon, source=SOURCE, cells=[self._cell(c, horizon) for c in self.cells])

    def area_summary(self, name: str, horizon: Horizon) -> AreaSummary:
        cells = [self._cell(c, horizon) for c in self.cells]
        zones: dict[str, list[float]] = {}
        for c in cells:
            zones.setdefault(self.zone_of[c.h3], []).append(c.p_flood)
        ranked = sorted(((z, sum(v) / len(v)) for z, v in zones.items()), key=lambda t: -t[1])
        to_area = lambda z, p: RankedArea(name=z, p_flood=round(p, 3), color=flood_color(p))  # noqa: E731
        worst = flood_color(ranked[0][1])
        rain = sum(c.rain_mm for c in cells) / len(cells)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        # The UI shows the colour word as a badge, so the headline itself is just the sentence.
        headline = None if worst == Color.GREEN else f"{name}: synthetic demo — {ranked[0][0]} shows the highest risk"
        return AreaSummary(
            name=name, horizon=horizon, center=GUWAHATI, rain_mm=round(rain, 1), rain_color=rain_color_from_mm(rain),
            flood_color=worst, headline=headline,
            most_affected=[to_area(z, p) for z, p in ranked[:3]],
            least_affected=[to_area(z, p) for z, p in ranked[-2:]],
            nearest_shelter_km=None, generated_at=now, valid_from=now,
            valid_to=now + timedelta(hours=HORIZON_HOURS[horizon]), sources=[], source=SOURCE,
        )

    def area_for_cell(self, cell: str) -> str | None:
        """Accepts any resolution: finer cells are checked via their res-8 parent."""
        if h3.get_resolution(cell) > 8:
            cell = h3.cell_to_parent(cell, 8)
        return "Guwahati" if cell in self.zone_of else None

    def cell_detail(self, cell: str, horizon: Horizon) -> CellDetail | None:
        if cell not in self.zone_of:
            return None
        c = self._cell(cell, horizon)
        drivers = [
            Driver(feature="hand_mean", text="(synthetic) low-lying relative to nearby drains", contribution=0.3),
            Driver(feature="rain_3d", text=f"(synthetic) {c.rain_mm:.0f} mm rain expected", contribution=0.2),
        ]
        return CellDetail(**c.model_dump(), horizon=horizon, locality=self.zone_of[cell], drivers=drivers, source=SOURCE)

    def alerts(self, area: str | None) -> list[Alert]:
        s = self.area_summary("Guwahati", "24h")
        if s.flood_color in (Color.GREEN, Color.YELLOW) or (area and self.resolve(area) != "Guwahati"):
            return []
        return [Alert(
            id="demo-guwahati-24h", area="Guwahati", color=s.flood_color, headline=s.headline or "",
            description="SYNTHETIC DEMO ALERT — not a forecast. Generated to exercise the alert pipeline.",
            issued=s.generated_at, onset=s.generated_at + timedelta(hours=6), expires=s.valid_to,
            probability=s.most_affected[0].p_flood, source=SOURCE,
        )]
