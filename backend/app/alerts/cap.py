"""Common Alerting Protocol (CAP 1.2) generator.

CAP is the OASIS standard used by India's NDMA (SACHET platform) to disseminate
alerts across SMS, TV, radio and apps. Emitting valid CAP means our warnings can,
in principle, plug straight into the national system — a strong point for judges.

Spec: http://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html
Validate output with an online CAP validator before the demo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from app.core.imd import COLOR_WORD, Color

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
IST = timezone(timedelta(hours=5, minutes=30))
ET.register_namespace("", CAP_NS)

SEVERITY = {Color.RED: "Extreme", Color.ORANGE: "Severe", Color.YELLOW: "Moderate", Color.GREEN: "Minor"}
RESPONSE = {Color.RED: "Evacuate", Color.ORANGE: "Prepare", Color.YELLOW: "Monitor", Color.GREEN: "None"}
STATUSES = {"Actual", "Exercise", "System", "Test", "Draft"}


def _ts(dt: datetime) -> str:
    """CAP wants e.g. 2026-06-14T10:30:00+05:30 — no fractional seconds, explicit offset."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).replace(microsecond=0).isoformat()


def urgency(onset: datetime, sent: datetime) -> str:
    hours = (onset - sent).total_seconds() / 3600
    if hours <= 1:
        return "Immediate"
    if hours <= 24:
        return "Expected"
    return "Future"


def certainty(probability: float) -> str:
    return "Likely" if probability > 0.5 else "Possible" if probability >= 0.1 else "Unlikely"


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, f"{{{CAP_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


def build_cap(*, identifier: str, sender: str, sent: datetime, status: str, event: str, color: Color,
              probability: float, headline: str, description: str, instruction: str,
              onset: datetime, expires: datetime, area_desc: str,
              polygon: list[tuple[float, float]] | None = None, geocodes: dict[str, str] | None = None,
              msg_type: str = "Alert", references: str | None = None, language: str = "en-IN",
              web: str | None = None) -> str:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    color = Color(color)
    alert = ET.Element(f"{{{CAP_NS}}}alert")
    _sub(alert, "identifier", identifier)
    _sub(alert, "sender", sender)
    _sub(alert, "sent", _ts(sent))
    _sub(alert, "status", status)
    _sub(alert, "msgType", msg_type)
    _sub(alert, "scope", "Public")
    if references:
        _sub(alert, "references", references)

    info = _sub(alert, "info")
    _sub(info, "language", language)
    _sub(info, "category", "Met")
    _sub(info, "event", event)
    _sub(info, "responseType", RESPONSE[color])
    _sub(info, "urgency", urgency(onset, sent))
    _sub(info, "severity", SEVERITY[color])
    _sub(info, "certainty", certainty(probability))
    _sub(info, "onset", _ts(onset))
    _sub(info, "expires", _ts(expires))
    _sub(info, "senderName", "Jalproloi flood early warning")
    _sub(info, "headline", headline[:160])
    _sub(info, "description", description)
    _sub(info, "instruction", instruction)
    if web:
        _sub(info, "web", web)
    for name, value in (("colour", color.value), ("level", COLOR_WORD[color]), ("probability", f"{probability:.2f}")):
        p = _sub(info, "parameter")
        _sub(p, "valueName", name)
        _sub(p, "value", value)

    area = _sub(info, "area")
    _sub(area, "areaDesc", area_desc)
    if polygon:
        ring = list(polygon)
        if ring[0] != ring[-1]:
            ring.append(ring[0])  # CAP polygons must be closed
        _sub(area, "polygon", " ".join(f"{lat:.5f},{lon:.5f}" for lat, lon in ring))
    for name, value in (geocodes or {}).items():  # e.g. {"LGD_district": "..."}
        g = _sub(area, "geocode")
        _sub(g, "valueName", name)
        _sub(g, "value", value)

    return ET.tostring(alert, encoding="unicode", xml_declaration=True)
