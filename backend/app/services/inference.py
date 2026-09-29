"""Where forecasts come from. The API only talks to a ForecastProvider.

DemoProvider      synthetic data (DEMO_MODE=true)
DatabaseProvider  reads the per-run tables written by pipelines/run_forecast.py

The API never runs models on request: engines run on the scheduler, write results to
PostGIS, and the API serves the latest run. Requests stay fast even during a flood.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.schemas import Alert, AreaCells, AreaHit, AreaSummary, CellDetail, Horizon


class ForecastProvider(Protocol):
    def resolve(self, name: str) -> str | None: ...
    def search(self, q: str) -> list[AreaHit]: ...
    def area_summary(self, name: str, horizon: Horizon) -> AreaSummary: ...
    def area_cells(self, name: str, horizon: Horizon) -> AreaCells: ...
    def cell_detail(self, cell: str, horizon: Horizon) -> CellDetail | None: ...
    def area_for_cell(self, cell: str) -> str | None: ...
    def alerts(self, area: str | None) -> list[Alert]: ...


class DatabaseProvider:
    """TODO(backend): implement against app/db/models.py once run_forecast writes data.

    resolve/search:  SELECT name, level, ST_Y(centroid), ST_X(centroid) FROM areas
                     WHERE name ILIKE %q% ORDER BY similarity(name, q) DESC   (pg_trgm)
    area_summary:    latest run_id; area_forecasts for the area + horizon; children
                     ranked by expected_affected_pop for most/least affected
    area_cells:      cell_forecasts JOIN cells WHERE ST_Intersects(cells.geom, areas.geom)
    cell_detail:     cell_forecasts row incl. drivers JSONB
    area_for_cell:   covered area containing the cell (cells.district / locality), or None
    alerts:          alerts WHERE expires > now() AND (area = :area OR :area IS NULL)
    Cache hot responses in Redis keyed by (run_id, area, horizon).
    """

    def __getattr__(self, name):
        raise NotImplementedError("DatabaseProvider not implemented yet — set DEMO_MODE=true")


@lru_cache
def get_provider(mode: str | None = None) -> ForecastProvider:
    if mode == "live" or not settings.demo_mode:
        from app.services.live_model import LiveHydrometeoProvider

        return LiveHydrometeoProvider()
    if settings.demo_mode:
        from app.services.demo import DemoProvider

        return DemoProvider()
    return DatabaseProvider()
