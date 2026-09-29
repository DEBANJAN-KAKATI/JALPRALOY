"""Warning colours for the API. Mirror of ml/common/imd.py — keep the two in sync
(the backend container does not ship the ml package)."""
from enum import Enum


class Color(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


COLOR_WORD = {Color.GREEN: "Low", Color.YELLOW: "Watch", Color.ORANGE: "Prepare", Color.RED: "Act"}
COLOR_RANK = {Color.GREEN: 0, Color.YELLOW: 1, Color.ORANGE: 2, Color.RED: 3}
FLOOD_COLOR_BREAKS = (0.2, 0.4, 0.7)


def flood_color(p: float) -> Color:
    y, o, r = FLOOD_COLOR_BREAKS
    if p >= r:
        return Color.RED
    if p >= o:
        return Color.ORANGE
    if p >= y:
        return Color.YELLOW
    return Color.GREEN


def rain_color_from_mm(mm: float) -> Color:
    """Deterministic fallback when only an amount is known (IMD 24 h categories)."""
    if mm >= 204.5:
        return Color.RED
    if mm >= 115.6:
        return Color.ORANGE
    if mm >= 64.5:
        return Color.YELLOW
    return Color.GREEN
