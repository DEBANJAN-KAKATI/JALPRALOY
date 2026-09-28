# Engine 4 · River flood propagation and impact ranking

> **Questions:** (a) which place *downstream* will flood next, and when? (b) who will be hurt most?
> **Output in the UI:** river-layer warnings ("Goalpara expected to cross danger level in ~48 h"), the **Most / Least affected** list, and the expected number of people affected.

Code: `ml/river_routing/`, `ml/impact/` · Inputs: `ingest_river_levels.py`, WorldPop, OSM · Owner: ML (inundation) + data engineering

---

## Part A — River routing (Engine 4a)

### A1. The physics we exploit
The Brahmaputra flows roughly east to west. A flood wave passing Dibrugarh reaches Neamatighat,
Tezpur, Guwahati, Goalpara and Dhubri in order, after travel times of hours to days.
Tributaries (Subansiri, Jia Bharali, Manas, Kopili, and others) add water between gauges. Upstream gauge
readings are therefore strong predictors of downstream levels, and the lag between gauges is the lead time you can offer.

### A2. Contract
**Output** `river.parquet`: `station, horizon_h (6/12/24/48/72), level_m, above_warning, above_danger, text`.

### A3. Data
1. **Best:** CWC hourly or 3-hourly levels for the six main-stem stations, 2010–2025, obtained through India-WRIS or a formal CWC request.
   Import each file with `python -m pipelines.ingest_river_levels import-csv file.csv --station Guwahati`.
   Fill `warning_level_m`, `danger_level_m`, `hfl_m` and the real coordinates in `data/static/gauges.csv`.
2. **Start today:** GloFAS discharge via Open-Meteo, daily, 1984 onward. First run
   `python -m pipelines.ingest_river_levels snap`. A town's own coordinate usually lands on a tributary
   (~6 m³/s at Guwahati), so `snap` picks the highest-flow GloFAS cell within ±0.15°, which is the main stem
   (~8,000 → 23,000 m³/s from Dibrugarh to Dhubri in late September). Then:
   `python -m pipelines.ingest_river_levels glofas --start 1995-01-01 --end 2025-12-31`.
   It is modelled discharge, not measured stage, but it lets you build and debug the whole pipeline now.
   Train with `--value discharge_m3s`.

### A4. Build steps
```bash
python -m ml.river_routing.train_lag_model                  # levels
python -m ml.river_routing.train_lag_model --value discharge_m3s   # GloFAS proxy
```
1. **Estimate travel times** (`travel_time_h`) from the cross-correlation of 24 h *changes*, not raw levels,
   because the shared seasonal cycle hides the lag. Print the lag matrix; it should grow downstream.
   The lags give your honest lead-time limits.
2. **Features** (`features.py`): the target's own level and 24 h change; each upstream station's level at lags 0–72 h
   and its 24 h change; season. **Add** sub-catchment rainfall (IMD/IMERG basin means, plus Engine 2 forecasts
   for the next days), because tributaries respond to rain the main-stem gauges haven't seen yet.
3. **Target:** the level *change* over horizon h. Persistence is then the natural zero, and the model learns departures from it.
4. **Model:** LightGBM per (station, horizon). A small LSTM over the last 72 h of all gauges is the upgrade.
   Compare the two on the same split.
5. **Split:** 2022 held out (the hindcast year). For more rigour, do leave-one-year-out over the flood seasons.

### A5. Verification
| Metric | Why |
|--------|-----|
| RMSE, NSE of level per horizon | standard hydrology skill (`nse` in `metrics.py`) |
| vs persistence RMSE / NSE | must beat "tomorrow = today" |
| CSI / POD / FAR of "above danger level" | the decision that matters |
| Timing error of peak | how early the peak is predicted and how far off its timing is |

### A6. From gauges to hexagons (fluvial hazard)
A river forecast at a gauge must become a flood probability per cell near the river:
- **HAND-based inundation (the approach used by NOAA's operational HAND-FIM).** Convert the forecast stage rise at
  the nearest gauge into a water height above the channel. Cells whose HAND is below that height, and that are
  hydraulically connected to the river, flood. Use an S-curve rather than a hard cut to get a probability.
- **Learned:** Engine 3's dynamic model already has `river_q_anom`. Give each cell the forecast anomaly of its
  nearest main-stem reach (TODO in `dataset.py`: per-cell reach mapping instead of Guwahati for all cells).
- Combine pluvial and fluvial with `combine_pluvial_fluvial(p_rain, p_river) = 1 − (1−a)(1−b)`.

**Guwahati-specific:** when the Brahmaputra is high, the Bharalu and other drains can't discharge (backwater), so
city waterlogging gets worse at the same rainfall. The `river_q_anom` feature lets the model learn this.
Mention it in the demo, because it shows domain understanding.

---

## Part B — Impact ranking (Engine 4b)

### B1. Formula
```
risk = hazard × exposure × vulnerability
```
| Component | Per-cell data | Source |
|-----------|--------------|--------|
| Hazard | `p_flood` (Engine 3, combined with river) | model |
| Exposure | population; hospitals ×3 + schools; buildings; road km | WorldPop, OSM, Google Open Buildings |
| Vulnerability | share of kutcha housing; distance to shelter | Census 2011 Houselisting; OSM / ASDMA relief camps |

**Primary ranking = expected affected population = Σ p_flood × population.** It is measured in people, so it can be
added up across locality, circle, district and state, and an official can act on it ("~12,000 people in X"). The
composite `risk_index` (0–1) is only for colour and tie-breaking. Its weights are judgement calls, so document them.

### B2. Build steps
```bash
python -m ml.impact.build_exposure --res 9 --pilot
```
1. Download WorldPop 2020 constrained 100 m for India → `data/raw/worldpop/ind_ppp_2020_constrained.tif`.
2. OSM counts per cell. For state scale, switch from Overpass (osmnx) to a Geofabrik extract read with `pyrosm`.
3. Vulnerability: join the Census 2011 HLO housing-condition tables to districts or villages (TODO).
   Until then, distance to shelter is the only vulnerability term, and the index uses 0.5 as a neutral value.
4. `ml/impact/risk.py`: `cell_risk` → `aggregate(cells, by="locality")` → `rank(agg)` gives the most- and least-affected lists.

### B3. Pitfalls
- **Population ≠ people at risk at night vs day.** WorldPop is residential. Note it as a limitation.
- **Double counting:** when rolling up, sum `expected_affected_pop`. Never sum probabilities.
- **"Least affected" must still be meaningful:** rank by population-weighted probability and exclude empty cells (no population).
- **Sensitive data:** don't store or show individual household data. Aggregate to cells or localities.

## Done when

- [ ] Travel-time matrix printed and sane (grows downstream)
- [ ] Per-station, per-horizon models beat persistence; danger-level CSI reported (or GloFAS proxy NSE until CWC data arrives)
- [ ] `river.parquet` with human-readable warning text
- [ ] Exposure table for the pilot; locality ranking by expected affected population
- [ ] Model card filled for 4a and 4b
