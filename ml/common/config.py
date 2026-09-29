"""Project-wide constants shared by pipelines/ and ml/.

Anything two engines must agree on (paths, region, grid resolutions, time
conventions, data splits) lives here so there is exactly one source of truth.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("JALPROLOI_DATA", ROOT / "data"))
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
STATIC = DATA / "static"
BOUNDARIES = STATIC / "boundaries"
MODELS = ROOT / "ml" / "models"

# --- Region (lon_min, lat_min, lon_max, lat_max) --------------------------------
ASSAM_BBOX = (89.6, 24.1, 96.1, 28.0)
# Rain reaching Assam comes from Bangladesh, Meghalaya, Bhutan, Arunachal and the
# Bay of Bengal, so the nowcast domain must be far larger than the state itself.
NOWCAST_BBOX = (85.0, 20.0, 100.0, 30.5)
# Approximate box around Kamrup Metropolitan; the real polygon comes from
# pipelines/prepare_boundaries.py.
PILOT_BBOX = (91.50, 25.95, 92.20, 26.30)
PILOT_DISTRICT = "Kamrup Metropolitan"
GUWAHATI_CENTER = (26.1445, 91.7362)  # (lat, lon)

# --- Grids ---------------------------------------------------------------------
H3_RES_STATE = 8   # ~0.74 km² per cell, whole of Assam (~100k cells)
H3_RES_CITY = 9    # ~0.10 km² per cell, Guwahati pilot
WGS84 = "EPSG:4326"
UTM_CRS = "EPSG:32646"  # metric CRS for terrain analysis (UTM 46N covers 90–96°E)
IMD_GRID_RES = 0.25

# --- Time conventions ----------------------------------------------------------
# Everything is stored in UTC. IMD's rainfall day is the 24 h ending 0830 IST
# (= 03 UTC). Verify which date IMD's gridded files label that window with, using
# pipelines/ingest_imd.py::check_day_alignment, and set this accordingly.
IMD_DAY_END_UTC_HOUR = 3
IMD_DAY_LABEL = "start"  # "start" or "end" of the 03–03 UTC window — VERIFY
MONSOON_MONTHS = (5, 6, 7, 8, 9, 10)  # pre-monsoon + monsoon for Assam

# Forecast horizons served by the API
HORIZONS_H = {"now": 0, "6h": 6, "24h": 24, "72h": 72, "120h": 120}

# --- Validation discipline -----------------------------------------------------
# The hindcast demo event must come from a year that NO model has seen.
# 2022 had the major June floods including Guwahati waterlogging.
HINDCAST_YEAR = 2022
VALIDATION_YEAR = 2024


def ensure_dirs() -> None:
    for p in (RAW, PROCESSED, STATIC, BOUNDARIES, MODELS):
        p.mkdir(parents=True, exist_ok=True)


def gauges_csv() -> Path:
    return STATIC / "gauges.csv"
