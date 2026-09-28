# 12 · Keeping JalProloy live: syncing data from the sources

This guide takes the app from "demo" to "updates itself from real sources and every visitor sees fresh data".

## 1. How sync works: three loops

```
 ┌─────────────── Loop A: ingest (scheduler) ───────────────┐   ┌── Loop B: serve (API) ──┐   ┌─ Loop C: client ─┐
 │ IMERG/INSAT ─30 min─┐                                      │   │                        │   │                   │
 │ GFS/ECMWF ──6 h─────┼─► data/processed ─► engines ─► fuse ─┼──►│ PostGIS  (model runs)  │   │ fetch on open     │
 │ CWC/GloFAS ─1 h─────┤                              │       │   │ in-memory TTL cache    │◄──┤ every 5 min       │
 │ IMD daily ──daily───┘                              ▼       │   │ (live public data)     │   │ on focus / online │
 │                                         CAP alerts, push   │   │ /api/status freshness  │   │ offline: SW cache │
 └────────────────────────────────────────────────────────────┘   └────────────────────────┘   └───────────────────┘
```

| Loop | Runs where | Code | What makes it "live" |
|------|-----------|------|----------------------|
| A. Ingest + model | scheduler process | `pipelines/scheduler.py` → `ingest_*`, `run_forecast.py` | cron-like jobs pull each source on its own cadence, run engines, write a new run |
| B. Serve | FastAPI | `backend/app/services/live.py`, `news.py`, `geocode.py`, `inference.py` | every live endpoint has a TTL cache; a cache miss fetches from the source; failures fall back to the last good copy |
| C. Client | browser / PWA | `frontend/src/App.tsx`, `lib/useApi.ts`, `public/sw.js` | refetch on open, every 5 min, when the tab regains focus (if > 1 min old) and when the network returns; offline shows the cached copy |

## 2. What is live today and what is still demo

| Data | Source | Status now | Cache TTL | Endpoint |
|------|--------|-----------|-----------|----------|
| Rain outlook (7 days) | Open-Meteo | **live** | 30 min | `/api/outlook/rain` |
| Assam towns ranking | Open-Meteo | **live** | 60 min | `/api/outlook/towns` |
| Brahmaputra river watch | GloFAS via Open-Meteo Flood API | **live** | 6 h (source is daily) | `/api/rivers` |
| Regional flood events | GDACS | **live** | 30 min | `/api/events` |
| Flood & disaster news | Google News RSS (fallback GDELT) | **live** | 10 min | `/api/news` |
| Place search | Photon (OpenStreetMap) | **live** | 24 h per query | `/api/areas/suggest` |
| Flood hexagons, ranking, "why" | Engines 1–4 | **demo** until you do §4 | per run | `/api/risk/*` |

`/api/status` reports every source as `live`, `cached` (upstream failed, last good copy served), `offline` or `demo`.
The "Data sources" slide in the app displays exactly this.

## 3. Run the sync on your machine (15 minutes)

1. **Credentials** in `.env` (see [00_SETUP.md](00_SETUP.md)): `EARTHDATA_*`, `GEE_PROJECT`, `CDSAPI_KEY`.
   The live endpoints in §2 need **no keys**.
2. **One manual pass per source.** Fix any errors before automating:
   ```bash
   python -m pipelines.ingest_river_levels snap
   python -m pipelines.ingest_river_levels glofas --past-days 30
   python -m pipelines.ingest_imd --realtime --days 15
   python -m pipelines.ingest_imerg --latest 3
   python -m pipelines.ingest_nwp gfs
   ```
3. **Start the scheduler** (keeps running and pulls on cadence):
   ```bash
   python -m pipelines.scheduler
   ```
   | Job | Cadence (UTC) | Does |
   |-----|---------------|------|
   | `nowcast` | :05 and :35 every hour | IMERG Early → Engine 1 → fuse |
   | `nwp` | 04:30, 10:30, 16:30, 22:30 | GFS run (~4–5 h after init) → Engine 2 → fuse |
   | `river` | :15 every hour | GloFAS / CWC → Engine 4a → fuse |
   | `imd` | 04:45 daily | IMD real-time grid (antecedent rain) |
   | `warm` | every 5 min | calls the live endpoints so caches are always fresh; pings `HEALTHCHECK_URL` |

## 4. Switch the flood map from demo to model output

1. Train the engines (ENGINE_1…4 guides) so `ml/models/` contains the artifacts.
2. Implement the four `run_*` functions in `pipelines/run_forecast.py` (each already documents its output contract).
3. In `run_fuse`, write `runs`, `cell_forecasts`, `area_forecasts` and `alerts` to PostGIS (`backend/app/db/models.py`).
4. Implement `DatabaseProvider` in `backend/app/services/inference.py` (queries are listed in its docstring).
5. Set `DEMO_MODE=false` and restart the API. The demo notice disappears and the "Flood model" source turns **Live**.
6. Check: `curl localhost:8000/api/status` shows no `demo`, and `/api/risk/area?name=Guwahati` returns `"source": "model"`.

## 5. Run it permanently

Pick one:

| Option | Command / setup | Good for |
|--------|-----------------|----------|
| **Docker Compose** | `docker compose --profile live up -d` (starts `scheduler` next to `backend` and `db`) | a lab PC or a single VM |
| Windows Task Scheduler | a task at logon running `conda run -n jalproloi python -m pipelines.scheduler`, set to restart on failure | the team laptop during the hackathon |
| Linux systemd | `Restart=always` service running the same command | a cloud VM |
| Hosted cron (Render cron jobs / GitHub Actions `schedule:`) | run single jobs (`python -m pipelines.ingest_river_levels glofas`) on cron, writing to a hosted Postgres or object storage | free tiers; note that Actions cron can be delayed by several minutes |

Set `HEALTHCHECK_URL` to a free healthchecks.io check with a 15-minute grace period. If the scheduler dies, you get an email.

## 6. How the client stays in sync

Already implemented:
- **On open:** every panel fetches on mount; the News tab fetches every time it's opened.
- **Every 5 minutes:** `App.tsx` bumps `refreshKey`; all `useApi` hooks refetch and keep old data visible meanwhile (no flashing).
- **On return:** `visibilitychange` / `focus` refresh if data is more than 1 minute old; `online` refreshes after reconnecting.
- **Shared freshness:** the server caches each source once for all visitors. Whoever opens the app gets the same fresh copy, and the upstream APIs aren't hammered.
- **Offline:** `public/sw.js` serves the last `/api` responses when the network is down; the footer and status slide say so.
- **News badge:** counts headlines newer than the last one you saw (`localStorage`), and clears when you open News.

Next step, for instant updates: **server-sent events**. Add an endpoint that emits the latest `run_id` or source timestamp, and let the client refetch when it changes:

```python
# backend/app/api/stream.py
@router.get("/stream")
async def stream(request: Request):
    async def events():
        last = None
        while not await request.is_disconnected():
            current = latest_run_id()          # e.g. SELECT max(id) FROM runs
            if current != last:
                last = current
                yield f"event: run\ndata: {current}\n\n"
            await asyncio.sleep(15)
    return StreamingResponse(events(), media_type="text/event-stream")
```
```ts
// frontend/src/App.tsx
useEffect(() => {
  const es = new EventSource("/api/stream");
  es.addEventListener("run", refresh);
  return () => es.close();
}, [refresh]);
```

For people who don't have the app open, use **web push** from the alert logic in [08_ALERTS_CAP.md](08_ALERTS_CAP.md). The service worker already shows `push` notifications.

## 7. When a source fails

| Source | Typical failure | What the app does | What you do |
|--------|-----------------|-------------------|-------------|
| Open-Meteo / GloFAS | timeout, 429 | serves last copy (`cached`) | nothing; if it lasts hours, check their status page |
| GDACS | slow or 5xx | `cached`, then `offline` | nothing |
| Google News RSS | blocked or changed | falls back to **GDELT** automatically | for production use a licensed feed (below) |
| Photon | down / rate limited | search still returns towns and flood-map areas | self-host Photon (below) |
| IMERG / GFS | late product | engine keeps the previous run; `runs.sources` records what was used | nothing: latency is normal (see 02_DATA_SOURCES.md) |
| CWC | portal change | river engine uses GloFAS proxy | fix the parser; ask CWC for an API |

## 8. Before going beyond a prototype

- **News licensing:** Google News RSS is for "personal, non-commercial use". For an official service, switch to GDELT (already the fallback), a paid news API, or official feeds (PIB, ASDMA, IMD press releases). All of these live in `backend/app/services/news.py`.
- **Search:** run your own Photon with an India extract (`docker run komoot/photon`) and point `PHOTON_API` to it. The public instance is fair-use only.
- **Basemap:** host your own tiles (Protomaps / OpenMapTiles) instead of the free Carto style.
- **Rate etiquette:** keep the TTLs. They are why thousands of visitors cost only a few upstream calls per hour.
- **Time:** everything is stored in UTC and shown in IST, so don't mix them when adding sources.

## 9. Verify it's live (checklist)

- [ ] `curl localhost:8000/api/status`: every source `live`, none `offline`
- [ ] The "Data sources" slide shows "Updated … min ago" below each TTL
- [ ] Leave the app open for 10 min: the Refresh button's age counter resets by itself
- [ ] Turn Wi-Fi off, then on: the app refreshes by itself
- [ ] The News tab shows items from the last hour during an active event
- [ ] Kill the scheduler: the healthchecks.io email arrives
- [ ] (After §4) `/api/risk/area` returns `"source": "model"` and a `generated_at` within the last 6 h
