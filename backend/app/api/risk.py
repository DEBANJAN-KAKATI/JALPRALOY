from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import AreaCells, AreaSummary, CellDetail, Horizon
from app.services.inference import ForecastProvider, get_provider

router = APIRouter(prefix="/risk", tags=["risk"])


def _area(name: str, provider: ForecastProvider) -> str:
    resolved = provider.resolve(name)
    if not resolved:
        raise HTTPException(404, f"Unknown area {name!r}")
    return resolved


@router.get("/area", response_model=AreaSummary)
def area_summary(name: str = Query(..., examples=["Guwahati"]), horizon: Horizon = "24h",
                 mode: str | None = Query(None), provider: ForecastProvider = Depends(get_provider)):
    """Answer-first summary: rain, flood level, most/least affected places."""
    active = get_provider(mode) if mode else provider
    return active.area_summary(_area(name, active), horizon)


@router.get("/area/cells", response_model=AreaCells)
def area_cells(name: str, horizon: Horizon = "24h", mode: str | None = Query(None),
               provider: ForecastProvider = Depends(get_provider)):
    """Every hexagon in the area, for the map layer."""
    active = get_provider(mode) if mode else provider
    return active.area_cells(_area(name, active), horizon)


@router.get("/cell/{h3_id}", response_model=CellDetail)
def cell(h3_id: str, horizon: Horizon = "24h", mode: str | None = Query(None),
         provider: ForecastProvider = Depends(get_provider)):
    """One hexagon with its 'why' drivers."""
    active = get_provider(mode) if mode else provider
    detail = active.cell_detail(h3_id, horizon)
    if detail is None:
        raise HTTPException(404, "Cell not covered")
    return detail
