"""Serving tables. Training data lives in parquet under data/processed; the database
only holds what the API serves: cells, areas, the latest forecast runs, alerts.

    runs ──< cell_forecasts >── cells
      └───< area_forecasts >── areas
    alerts >── areas            saved_places (users' pinned locations)
"""
from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Cell(Base):
    __tablename__ = "cells"
    h3: Mapped[str] = mapped_column(String(16), primary_key=True)
    res: Mapped[int] = mapped_column(SmallInteger, index=True)
    district: Mapped[str | None] = mapped_column(String(64), index=True)
    locality: Mapped[str | None] = mapped_column(String(128), index=True)
    population: Mapped[float | None] = mapped_column(Float)
    susceptibility: Mapped[float | None] = mapped_column(Float)
    geom = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=True))


class Area(Base):
    __tablename__ = "areas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    level: Mapped[str] = mapped_column(String(16))  # locality | circle | district | state
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"))
    lgd_code: Mapped[str | None] = mapped_column(String(16))
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True))


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    issue_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(16), default="operational")  # operational | hindcast
    sources: Mapped[dict] = mapped_column(JSON)  # {"imerg": "...", "gfs_init": "...", "models": {...}}


class CellForecast(Base):
    __tablename__ = "cell_forecasts"
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    h3: Mapped[str] = mapped_column(ForeignKey("cells.h3"), primary_key=True)
    horizon: Mapped[str] = mapped_column(String(8), primary_key=True)  # now | 6h | 24h | 72h | 120h
    rain_mm: Mapped[float] = mapped_column(Float)
    p_heavy: Mapped[float | None] = mapped_column(Float)
    p_very_heavy: Mapped[float | None] = mapped_column(Float)
    p_extreme: Mapped[float | None] = mapped_column(Float)
    p_flood: Mapped[float] = mapped_column(Float)
    rain_color: Mapped[str] = mapped_column(String(8))
    color: Mapped[str] = mapped_column(String(8))
    eta_min: Mapped[float | None] = mapped_column(Float)
    drivers: Mapped[list | None] = mapped_column(JSON)


class AreaForecast(Base):
    __tablename__ = "area_forecasts"
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), primary_key=True)
    horizon: Mapped[str] = mapped_column(String(8), primary_key=True)
    rain_mm: Mapped[float] = mapped_column(Float)
    p_flood_max: Mapped[float] = mapped_column(Float)
    p_flood_popweighted: Mapped[float] = mapped_column(Float)
    expected_affected_pop: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(8))


class AlertRow(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    color: Mapped[str] = mapped_column(String(8))
    headline: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    issued: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    onset: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    msg_type: Mapped[str] = mapped_column(String(8), default="Alert")  # Alert | Update | Cancel
    cap_xml: Mapped[str] = mapped_column(Text)


class SavedPlaceRow(Base):
    __tablename__ = "saved_places"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_ref: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    h3: Mapped[str] = mapped_column(String(16), index=True)
    channels: Mapped[list] = mapped_column(JSON)
    contact: Mapped[str | None] = mapped_column(Text)  # encrypt at rest in production
    last_color_sent: Mapped[str | None] = mapped_column(String(8))
