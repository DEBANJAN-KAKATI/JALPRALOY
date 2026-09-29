"""Real public data around the model outputs: rain outlook, river watch, flood events,
and the status of every data source."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas import FloodEvents, NewsFeed, RainOutlook, RiverStation, SourceStatus, TownOutlook
from app.services import live, news as news_service

router = APIRouter(tags=["live data"])


async def _guard(coro):
    try:
        return await coro
    except live.LiveDataUnavailable as exc:
        raise HTTPException(503, f"{exc} is unreachable and nothing is cached yet") from exc


@router.post("/sync")
async def trigger_sync():
    """Forces synchronization across all real-time pipelines and returns updated source statuses."""
    return await live.sync_all_sources()


@router.get("/outlook/rain", response_model=RainOutlook)
async def rain_outlook(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                       days: int = Query(7, ge=1, le=16), fresh: bool = Query(False)):
    """Daily rain for a point (Open-Meteo, IST calendar days). Raw model output."""
    return await _guard(live.rain_outlook(round(lat, 2), round(lon, 2), days, force=fresh))


@router.get("/outlook/towns", response_model=list[TownOutlook])
async def town_outlook(fresh: bool = Query(False)):
    """Assam towns ranked by their wettest day in the next 5 days."""
    return await _guard(live.town_outlook(days=5, force=fresh))


@router.get("/rivers", response_model=list[RiverStation])
async def rivers(fresh: bool = Query(False)):
    """Brahmaputra main stem, upstream -> downstream: GloFAS discharge vs the same
    season of the previous 10 years, plus the 7-day forecast peak."""
    return await _guard(live.river_watch(force=fresh))


@router.get("/events", response_model=FloodEvents)
async def events(fresh: bool = Query(False)):
    """GDACS flood events of the last 45 days in NE India and neighbouring countries."""
    return await _guard(live.flood_events(days=45, force=fresh))


@router.get("/news", response_model=NewsFeed)
async def news(scope: Literal["assam", "india"] = "assam", lang: str = "en", fresh: bool = Query(False)):
    """Flood/disaster headlines (title must contain a flood or disaster keyword).
    Cached 10 min server-side, so every visitor sees the same, fresh list."""
    return await _guard(news_service.news(scope, lang, force=fresh))


@router.get("/status", response_model=list[SourceStatus])
def status():
    from datetime import datetime, timezone
    model = SourceStatus(
        id="flood-model",
        name="Flood model (Hyperlocal Live Hydrometeo)" if not settings.demo_mode else "Flood model (Engines 1–4)",
        status="demo" if settings.demo_mode else "live",
        updated=datetime.now(timezone.utc) if not settings.demo_mode else None,
        detail="synthetic demo data" if settings.demo_mode else "fused with live Open-Meteo precipitation & GloFAS river discharge",
    )
    return [model] + [SourceStatus(id=k, name=s.name, status=s.status, updated=s.updated, detail=s.detail)
                      for k, s in live.STATUS.items()]
