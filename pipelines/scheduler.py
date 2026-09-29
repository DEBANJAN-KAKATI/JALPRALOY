"""Periodic sync: keeps data and forecasts fresh.

    python -m pipelines.scheduler

Cadence (from the plan):
    every 30 min   satellite rainfall + nowcast (Engine 1) + fused forecast
    every 6 h      NWP download + Engine 2 (GFS runs 00/06/12/18 UTC, ~4–5 h latency)
    every 1 h      river levels (Engine 4)
    daily 04 UTC   IMD real-time gridded rainfall (antecedent rain for Engine 3)
    every 5 min    warm the API's live-data caches (news, rivers, rain, events)

Heartbeat: set HEALTHCHECK_URL (e.g. a free healthchecks.io ping URL) to get an
email when the scheduler stops. Full guide: docs/12_LIVE_DATA_SYNC.md

Swap to Celery beat if you need distributed workers; APScheduler is enough for a
single backend box.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys

import requests

from apscheduler.schedulers.blocking import BlockingScheduler

log = logging.getLogger("scheduler")


def run(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", module, *args]
    log.info("running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        log.error("%s failed:\n%s", module, result.stderr[-2000:])


def job_nowcast() -> None:
    run("pipelines.ingest_imerg", "--latest", "3")
    run("pipelines.run_forecast", "--engines", "nowcast", "fuse")


def job_nwp() -> None:
    run("pipelines.ingest_nwp", "gfs")
    run("pipelines.run_forecast", "--engines", "rainfall", "fuse")


def job_river() -> None:
    run("pipelines.ingest_river_levels", "glofas", "--past-days", "10")
    run("pipelines.run_forecast", "--engines", "river", "fuse")


def job_imd_daily() -> None:
    run("pipelines.ingest_imd", "--realtime", "--days", "15")


API_URL = os.environ.get("API_URL", "http://localhost:8000")
WARM_PATHS = ["/api/news?scope=assam", "/api/news?scope=india", "/api/rivers", "/api/events",
              "/api/outlook/towns", "/api/outlook/rain?lat=26.14&lon=91.74"]


def job_warm_api() -> None:
    """Hit the live endpoints so the server refreshes its caches before users ask:
    the first visitor after a quiet spell then gets fresh data instantly."""
    for path in WARM_PATHS:
        try:
            requests.get(API_URL + path, timeout=60)
        except requests.RequestException as exc:
            log.warning("warm %s failed: %s", path, exc)
    if os.environ.get("HEALTHCHECK_URL"):
        try:
            requests.get(os.environ["HEALTHCHECK_URL"], timeout=10)
        except requests.RequestException:
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job_nowcast, "cron", minute="5,35", id="nowcast", max_instances=1, coalesce=True)
    sched.add_job(job_nwp, "cron", hour="4,10,16,22", minute=30, id="nwp", max_instances=1, coalesce=True)
    sched.add_job(job_river, "cron", minute=15, id="river", max_instances=1, coalesce=True)
    sched.add_job(job_imd_daily, "cron", hour=4, minute=45, id="imd", max_instances=1, coalesce=True)
    sched.add_job(job_warm_api, "interval", minutes=5, id="warm", max_instances=1, coalesce=True)
    log.info("scheduler started")
    sched.start()


if __name__ == "__main__":
    main()
