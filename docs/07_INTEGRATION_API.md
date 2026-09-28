# 07 · Integration (fusion) and API

The four engines only become one system at fusion time. `pipelines/run_forecast.py` runs the engines and
fuses their outputs, then writes the result for the API.

## Fusion per horizon

| Horizon | Rain from | Flood probability | River | Colour shown |
|---------|-----------|-------------------|-------|--------------|
| `now` | latest observed frame (IMERG/INSAT/radar) + last 24 h | Engine 3 with observed rain only | latest gauge state | flood colour |
| `6h` | Engine 1 6 h accumulation | `predict_nowcast` | Engine 4a 6 h | worst of rain and flood |
| `24h` | Engine 2 lead day 1 | `predict_scenarios` (category integration) | Engine 4a 24 h | worst of rain and flood |
| `72h` | Engine 2 days 1–3 (cumulative) | scenarios on the 3-day total | Engine 4a 72 h | worst of rain and flood |
| `120h` | Engine 2 days 1–5 | scenarios on the 5-day total | Engine 4a max over 72 h (limit) | worst of rain and flood |

Per cell:
```
p_pluvial = Engine 3 (rain scenarios + antecedent + terrain)
p_fluvial = HAND-based river inundation from Engine 4a (cells near the main stem)
p_flood   = 1 − (1 − p_pluvial)(1 − p_fluvial)
color     = worst(rain_color, flood_color(p_flood))
```

**Multi-day probabilities.** Engine 2 gives per-day probabilities. For cumulative windows, either train
Engine 2 directly on 3-day and 5-day sums (cleanest) or approximate with the per-day maximum. Record which one you used.

**Blending at the seam (6–24 h).** Engine 1 skill decays fast after ~3 h. Weight Engine 1 down and Engine 2 up
linearly over 3–12 h rather than switching abruptly.

## Aggregation

cell → locality (res-9 `locality` column) → circle → district (`district` column) → state.
Use `ml/impact/risk.py::aggregate` at each level. Store `area_forecasts` for every level, so the API never
aggregates on request.

## Run bookkeeping

Each fusion writes a `runs` row with the issue time and the exact inputs used, e.g.
`{"imerg_until": "...", "gfs_init": "...", "models": {"rain": "gfs_heavy@2025-06-01", ...}}`.
Judges and officials can then ask "what was this based on?" and you can answer precisely.

## API (FastAPI, `/api` prefix)

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/health` | `{status, demo_mode}` |
| GET | `/api/areas/search?q=` | areas, or an H3 id / "lat,lon" parsed directly |
| GET | `/api/risk/area?name=Guwahati&horizon=24h` | `AreaSummary`: rain, colours, headline, most/least affected |
| GET | `/api/risk/area/cells?name=&horizon=` | every hexagon for the map |
| GET | `/api/risk/cell/{h3}?horizon=` | one hexagon with `drivers` (the "why") |
| GET | `/api/alerts?area=` | active alerts |
| GET | `/api/alerts/{id}/cap` | CAP 1.2 XML |
| GET/POST/DELETE | `/api/saved-places` | user-pinned locations with `min_color` (in-memory for now) |
| GET | `/api/areas/locate?lat=&lon=` | "My location": covered by the pilot? nearest town |
| GET | `/api/outlook/rain?lat=&lon=` | **live** 7-day daily rain (Open-Meteo, raw NWP) |
| GET | `/api/outlook/towns` | **live** Assam towns ranked by wettest day in 5 days |
| GET | `/api/rivers` | **live** Brahmaputra main stem: GloFAS discharge vs same season (10 y), 7-day peak |
| GET | `/api/events` | **live** GDACS flood events, NE India + neighbours, last 45 days |
| GET | `/api/status` | every data source: live / cached / offline / demo |

The live endpoints (`backend/app/services/live.py`) cache responses (30 min–6 h). If an upstream API fails
they serve the last good copy and mark the source `cached`, and with no copy they return 503. They are real
data that surround the model outputs, so the site stays useful before the engines are trained.

Schemas: `backend/app/schemas.py`. Interactive docs: http://localhost:8000/docs.

Example `AreaSummary` (shape only; values here are illustrative):
```json
{
  "name": "Guwahati", "horizon": "24h", "center": [26.1445, 91.7362],
  "rain_mm": 142.0, "rain_color": "orange", "flood_color": "orange",
  "headline": "Guwahati: very heavy rain likely; low-lying areas near the Bharalu at high risk",
  "most_affected": [{"name": "<locality>", "p_flood": 0.81, "color": "red", "expected_affected_pop": 12400}],
  "least_affected": [{"name": "<locality>", "p_flood": 0.06, "color": "green", "expected_affected_pop": 40}],
  "generated_at": "2026-06-14T04:30:00Z", "valid_from": "...", "valid_to": "...",
  "sources": ["IMD", "GPM IMERG", "GFS", "CWC"], "source": "model"
}
```

## Switching from demo to real data

1. Load `cells` and `areas` from the parquet files and boundaries (a one-off loader script; `geopandas.to_postgis`).
2. Make `run_fuse` write `runs`, `cell_forecasts`, `area_forecasts`, `alerts`.
3. Implement `DatabaseProvider` in `backend/app/services/inference.py`. The docstring lists the queries.
4. Cache hot responses in Redis keyed by `(run_id, area, horizon)`.
5. Set `DEMO_MODE=false`. The frontend needs no changes, and the demo notice disappears automatically.

## Done when

- [ ] One command produces a fused run for the pilot with all five horizons
- [ ] API serves it with `source: "model"`
- [ ] p95 latency of `/api/risk/area/cells` under 300 ms (cache warm)
