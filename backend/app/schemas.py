from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.imd import Color

Horizon = Literal["now", "6h", "24h", "72h", "120h"]
Source = Literal["model", "synthetic-demo", "live-hydrometeo"]


class Driver(BaseModel):
    feature: str
    text: str
    contribution: float


class CellRisk(BaseModel):
    h3: str
    p_flood: float = Field(ge=0, le=1)
    color: Color
    rain_mm: float
    rain_color: Color


class CellDetail(CellRisk):
    horizon: Horizon
    locality: str | None = None
    drivers: list[Driver] = []
    source: Source


class RankedArea(BaseModel):
    name: str
    p_flood: float
    color: Color
    expected_affected_pop: float | None = None


class AreaSummary(BaseModel):
    name: str
    horizon: Horizon
    center: tuple[float, float]  # (lat, lon)
    rain_mm: float
    rain_color: Color
    flood_color: Color
    headline: str | None
    most_affected: list[RankedArea]
    least_affected: list[RankedArea]
    nearest_shelter_km: float | None = None
    generated_at: datetime
    valid_from: datetime
    valid_to: datetime
    sources: list[str]
    source: Source


class AreaCells(BaseModel):
    name: str
    horizon: Horizon
    source: Source
    cells: list[CellRisk]


class AreaHit(BaseModel):
    name: str
    level: Literal["locality", "circle", "district", "state", "town", "point"]
    center: tuple[float, float]
    # True when the hyperlocal flood model has hexagons here (pilot: Guwahati only)
    covered: bool = True
    area: str | None = None  # the covered area to request risk for (None if not covered)
    district: str | None = None


class Located(BaseModel):
    lat: float
    lon: float
    h3: str
    covered: bool
    area: str | None = None
    nearest_town: str
    nearest_town_km: float


class Alert(BaseModel):
    id: str
    area: str
    color: Color
    headline: str
    description: str
    issued: datetime
    onset: datetime
    expires: datetime
    probability: float
    source: Source


class SavedPlaceIn(BaseModel):
    name: str
    lat: float
    lon: float
    channels: list[Literal["push", "sms", "telegram"]] = ["push"]
    contact: str | None = None  # phone / chat id; store encrypted in production
    min_color: Color = Color.ORANGE  # alert when the place reaches this level or worse


class SavedPlace(SavedPlaceIn):
    id: str
    h3: str


# --- Live public data (real, labelled) ---------------------------------------
LiveStatus = Literal["idle", "live", "cached", "offline", "demo"]


class RainDay(BaseModel):
    date: str
    rain_mm: float
    probability: float | None
    color: Color


class RainOutlook(BaseModel):
    lat: float
    lon: float
    days: list[RainDay]
    total_mm: float
    max_mm: float
    source: str


class TownOutlook(BaseModel):
    name: str
    district: str
    lat: float
    lon: float
    total_mm: float
    max_mm: float
    max_date: str
    color: Color


class RiverPoint(BaseModel):
    date: str
    q: float
    forecast: bool


class RiverStation(BaseModel):
    station: str
    order: int
    lat: float
    lon: float
    date: str
    discharge: float
    change_24h: float | None
    trend: Literal["rising", "falling", "steady"]
    percentile: float
    color: Color
    status: str
    season_median: float | None
    rise_expected: bool
    peak_date: str
    peak_discharge: float
    peak_color: Color
    peak_status: str
    series: list[RiverPoint]


class FloodEvent(BaseModel):
    id: str
    name: str
    country: str
    alert_level: str
    color: Color
    from_date: str | None
    to_date: str | None
    is_current: bool
    lat: float | None
    lon: float | None
    url: str | None


class FloodEvents(BaseModel):
    region: list[FloodEvent]
    india_other: list[FloodEvent]


class SourceStatus(BaseModel):
    id: str
    name: str
    status: LiveStatus
    updated: datetime | None = None
    detail: str = ""


class Suggestion(BaseModel):
    """One row of the search-as-you-type dropdown."""
    name: str
    subtitle: str = ""
    kind: str  # City, Town, Village, Locality, Road, Hospital, …
    center: tuple[float, float]
    covered: bool = False  # inside the hyperlocal flood map
    area: str | None = None
    source: Literal["jalproloy", "osm"]


class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published: datetime | None
    keywords: list[str]
    local: bool


class NewsFeed(BaseModel):
    items: list[NewsItem]
    provider: Literal["google-news", "gdelt"]
    fetched_at: datetime
    scope: Literal["assam", "india"]
    lang: str
