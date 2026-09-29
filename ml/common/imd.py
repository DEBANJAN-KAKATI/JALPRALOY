"""IMD rainfall categories and the four-colour warning scale.

Using IMD's own thresholds and colours makes every output instantly readable by
officials. The probability → colour rules below are OUR convention; tune them with
feedback from IMD Guwahati and document any change in the model card.
"""
from __future__ import annotations

from enum import Enum

import numpy as np

# 24-hour rainfall categories (mm/day), lower bounds, from IMD's terminology.
RAIN_CATEGORIES: list[tuple[str, float]] = [
    ("no_rain", 0.0),
    ("very_light", 0.1),
    ("light", 2.5),
    ("moderate", 15.6),
    ("heavy", 64.5),
    ("very_heavy", 115.6),
    ("extremely_heavy", 204.5),
]

HEAVY = 64.5
VERY_HEAVY = 115.6
EXTREMELY_HEAVY = 204.5
EXCEEDANCE_THRESHOLDS = {"heavy": HEAVY, "very_heavy": VERY_HEAVY, "extremely_heavy": EXTREMELY_HEAVY}


class Color(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


# Colour alone fails colour-blind users: always show the word too.
COLOR_WORD = {Color.GREEN: "Low", Color.YELLOW: "Watch", Color.ORANGE: "Prepare", Color.RED: "Act"}
COLOR_HEX = {Color.GREEN: "#2e7d32", Color.YELLOW: "#f9d423", Color.ORANGE: "#f57c00", Color.RED: "#d32f2f"}
COLOR_RANK = {Color.GREEN: 0, Color.YELLOW: 1, Color.ORANGE: 2, Color.RED: 3}


def rain_category(mm: float) -> str:
    """Name of the IMD category for a 24 h rainfall amount."""
    name = RAIN_CATEGORIES[0][0]
    for cat, lower in RAIN_CATEGORIES:
        if mm >= lower:
            name = cat
    return name


def enforce_monotone(p_heavy, p_very_heavy, p_extreme):
    """Exceedance probabilities must satisfy P(≥64.5) ≥ P(≥115.6) ≥ P(≥204.5).

    Independently trained classifiers can violate this; clip downward.
    """
    p_h = np.clip(np.asarray(p_heavy, dtype=float), 0, 1)
    p_vh = np.minimum(np.clip(np.asarray(p_very_heavy, dtype=float), 0, 1), p_h)
    p_x = np.minimum(np.clip(np.asarray(p_extreme, dtype=float), 0, 1), p_vh)
    return p_h, p_vh, p_x


def rain_color(p_heavy: float, p_very_heavy: float, p_extreme: float) -> Color:
    """Map exceedance probabilities to a warning colour (tunable decision matrix)."""
    if p_extreme >= 0.4 or p_very_heavy >= 0.7:
        return Color.RED
    if p_very_heavy >= 0.4 or p_heavy >= 0.7:
        return Color.ORANGE
    if p_heavy >= 0.3:
        return Color.YELLOW
    return Color.GREEN


FLOOD_COLOR_BREAKS = (0.2, 0.4, 0.7)  # yellow / orange / red lower bounds on P(flood)


def flood_color(p_flood: float) -> Color:
    y, o, r = FLOOD_COLOR_BREAKS
    if p_flood >= r:
        return Color.RED
    if p_flood >= o:
        return Color.ORANGE
    if p_flood >= y:
        return Color.YELLOW
    return Color.GREEN


def worst(*colors: Color) -> Color:
    return max(colors, key=COLOR_RANK.__getitem__)
