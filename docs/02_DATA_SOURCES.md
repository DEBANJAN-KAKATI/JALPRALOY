# 02 · Data sources

For each source: what it is for, how to get it, which script, and what will bite you.

## Summary

| Data | Engine | Script | Access |
|------|--------|--------|--------|
| IMD 0.25° daily gridded rainfall (1901–) | 2 target, 3 antecedent | `pipelines/ingest_imd.py` | `imdlib`, free |
| GPM IMERG half-hourly 0.1° | 1 input, 3 proxy | `pipelines/ingest_imerg.py` | NASA Earthdata (or GEE `NASA/GPM_L3/IMERG_V07`) |
| INSAT-3D/3DR HEM rainfall | 1 live input | *(add `ingest_insat.py`)* | MOSDAC registration |
| IMD Doppler radar (Guwahati, Mohanbari) | 1 (0–2 h, city scale) | *(add once data arrives)* | Formal IMD request |
| GFS 0.25° | 2 | `pipelines/ingest_nwp.py gfs` | Herbie (NOMADS live, AWS archive 2021–) |
| ECMWF IFS open data | 2 (second model) | `pipelines/ingest_nwp.py ecmwf` | `ecmwf-opendata`, free |
| NCMRWF NCUM | 2 (Indian model) | stub | Request from NCMRWF |
| Open-Meteo forecast | UI prototype | `pipelines/ingest_openmeteo.py` | Free, no key |
| CWC gauge levels | 4a | `pipelines/ingest_river_levels.py` | CWC FFS / India-WRIS / request |
| GloFAS discharge | 4a proxy | `ingest_river_levels.py glofas` | Open-Meteo Flood API, free |
| Copernicus DEM GLO-30 / FABDEM | 3 | `pipelines/gee/export_static_layers.py` | GEE / free |
| Sentinel-1 GRD | 3 labels | `pipelines/gee/s1_flood_mapping.py` | GEE |
| JRC Global Surface Water | 3 (permanent water mask) | `export_static_layers.py` | GEE |
| ESA WorldCover 10 m | 3 | `export_static_layers.py` | GEE |
| ERA5-Land soil moisture | 3 | `export_static_layers.py --only era5l` | GEE |
| WorldPop 100 m | 4b | `ml/impact/build_exposure.py` | worldpop.org download |
| OSM (hospitals, schools, roads, localities) | 4b, UI | `prepare_boundaries.py`, `build_exposure.py` | osmnx / Geofabrik |
| Boundaries | all | `pipelines/prepare_boundaries.py` | geoBoundaries API; verify with LGD |
| Guwahati waterlogging points | 3 validation | hand-curated `data/static/waterlogging_points.csv` | news, GMC/ASDMA notices |

## Latency (what "now" really means)

| Product | Typical latency | Consequence |
|---------|-----------------|-------------|
| IMERG Early | ~4 h | "Nowcast" from IMERG starts 4 h in the past; use it for training and hindcasts |
| IMERG Late / Final | ~14 h / ~3.5 months | training only |
| INSAT-3DR HEM (MOSDAC) | ~30–60 min | best live satellite option for Engine 1 |
| IMD radar | minutes | best for 0–2 h over Guwahati, if IMD shares it |
| GFS | ~4–5 h after init | run Engine 2 at 04:30/10:30/16:30/22:30 UTC |
| IMD daily grid | next day | antecedent rain lags by a day; fill the gap with IMERG |
| Sentinel-1 | 6–12 day revisit, hours to process | labels and post-event validation, **not** a live input |

In hindcasts, `ml/evaluation/hindcast.py` enforces these latencies. **Never feed a hindcast data that
wasn't available at the issue time.**

## Source notes and traps

### IMD gridded rainfall
- `imdlib.get_data('rain', 2000, 2024, fn_format='yearwise')` downloads `.grd` files, and `open_data(...).get_xarray()` reads them.
- Missing/outside-India is `-999`, masked by the script.
- **Day convention:** the rainfall day ends 03 UTC. Check whether a file's date labels the start or the end of
  that window with `check_day_alignment` (compare with IMERG summed over 03–03 UTC and shifted ±1 day).
  Set `IMD_DAY_LABEL` accordingly. Getting this wrong shifts every label by a day and wrecks Engine 2 quietly.
- Real-time grids: `imdlib.get_real_data(...)` for recent days.

### GPM IMERG
- V07 variable is `precipitation` (mm/h); files store `(time, lon, lat)`, so the script transposes them.
- Time uses a Julian calendar (cftime), which the script converts.
- For bulk history, Earth Engine (`NASA/GPM_L3/IMERG_V07`) is often faster than Earthdata downloads.

### NWP (Engine 2 training needs archived *forecasts*)
- GFS on AWS Open Data goes back to 2021; Herbie fetches it automatically.
- **GEFS Reforecast v12** (2000–2019, on AWS) is a consistent long training set if you want more years.
- ECMWF open data archive starts in 2023, so use it as a second live model and for recent validation.
- GFS APCP: each file has both a 6-h bucket and a since-init total. The script uses the `0-N hour acc`
  total and differences it. Check with `Herbie(...).inventory()` if a field comes back empty.

### Sentinel-1
- Change detection (`after − before < −3 dB` and `after < −18 dB`) is the standard quick method. Tune the
  thresholds on one event visually with `s1_flood_mapping.js` before exporting everything.
- Mask permanent water (JRC occurrence > 80 %), slopes > 5° and HAND > 20 m.
- **Urban blind spot:** buildings cause double-bounce, so street flooding in Guwahati is under-detected.
  That is why the hand-curated waterlogging list exists.
- Sentinel-1B failed in Dec 2021, so 2022–2024 has 12-day revisit. Sentinel-1C (launched Dec 2024) restores 6-day.

### DEM
- GLO-30 and SRTM are **surface** models that include roofs and trees. In Guwahati that biases HAND.
  **FABDEM** (forests and buildings removed, free for research) is a drop-in upgrade.
- CartoDEM (NRSC Bhuvan) is an Indian alternative; check its licence.

### Rivers
- CWC publishes current level, warning/danger levels and trend on the FFS portal. Put station codes and
  levels in `data/static/gauges.csv`.
- **The coordinates in `gauges.csv` are approximate town centres.** Replace them with CWC station coordinates.
- GloFAS (via Open-Meteo) snaps to the nearest model river cell. Sanity-check that each point picked
  the Brahmaputra main stem, not a tributary.

### Boundaries
- geoBoundaries may lag Assam's district changes. Cross-check the district list against the LGD directory
  and store LGD codes (`areas.lgd_code`), which CAP geocodes can use.
- Guwahati wards: GMC ward polygons are ideal. Until then, OSM place nodes plus nearest-assignment give usable locality names.

### Licences and ethics
- Cite every dataset on the About page (IMD, NASA GPM, ESA/Copernicus, JRC, WorldPop, OSM contributors, NOAA, ECMWF).
- ECMWF open data is CC-BY-4.0. OSM is ODbL. FABDEM is non-commercial.
- Scrape government portals only if their terms allow it, at low frequency, and prefer a formal data request.

## Waterlogging list (do this early — it's your urban ground truth)

`data/static/waterlogging_points.csv`: one row per place and event, with `source_url` and `verified_by`.
Aim for 40+ points across 2019–2025 from local news, GMC notices and ASDMA reports. Record `event_date`
so points from the hindcast year can be kept strictly for testing.
