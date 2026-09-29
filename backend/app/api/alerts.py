import h3
from fastapi import APIRouter, Depends, HTTPException, Response

from app.alerts.cap import build_cap
from app.core.config import settings
from app.schemas import Alert
from app.services.inference import ForecastProvider, get_provider

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[Alert])
def list_alerts(area: str | None = None, provider: ForecastProvider = Depends(get_provider)):
    return provider.alerts(area)


@router.get("/{alert_id}/cap", response_class=Response)
def alert_cap(alert_id: str, provider: ForecastProvider = Depends(get_provider)):
    """The alert as CAP 1.2 XML — the format India's NDMA (SACHET) uses."""
    alert = next((a for a in provider.alerts(None) if a.id == alert_id), None)
    if alert is None:
        raise HTTPException(404, "No such active alert")
    summary = provider.area_summary(alert.area, "24h")
    ring = [(lat, lon) for lat, lon in h3.cell_to_boundary(h3.latlng_to_cell(*summary.center, 6))]
    xml = build_cap(
        identifier=alert.id, sender=settings.cap_sender, sent=alert.issued, status=settings.cap_status,
        event="Heavy rainfall and urban flooding", color=alert.color, probability=alert.probability,
        headline=alert.headline, description=alert.description,
        instruction="Avoid low-lying roads and drains. Keep documents and medicines ready. Call 1070 / 1077 / 112 in an emergency.",
        onset=alert.onset, expires=alert.expires, area_desc=alert.area, polygon=ring,
    )
    return Response(content=xml, media_type="application/cap+xml")
