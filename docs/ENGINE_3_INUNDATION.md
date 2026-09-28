# Engine 3 · Inundation susceptibility and prediction (the hyperlocal engine)

> **Question:** *which part* of Guwahati, or of any district, will be under water?
> **Output in the UI:** the coloured hexagons, the ranked locality list, and the "Why?" panel.

Code: `ml/inundation/` · Inputs: `pipelines/build_h3_grid.py`, `build_static_features.py`, `gee/*` · Owner: ML (inundation) + GIS

This engine turns coarse rain (25 km, 11 km) into 100 m – 1 km answers. Terrain decides where
water goes: the same 150 mm floods a low, paved area 2 m above the Bharalu and leaves a hillside dry.

---

## Part A — MILESTONE 1: static susceptibility map of Guwahati

No live data needed. It can be built in a few days, and it already answers "which parts of Guwahati are most prone".

### A1. Grid
```bash
python -m pipelines.prepare_boundaries --localities
python -m pipelines.build_h3_grid --pilot
```
This gives `cells_res8.parquet` (all Assam) and `cells_res9_pilot.parquet` (Kamrup Metro, with `locality`).

### A2. Static rasters from Earth Engine
```bash
python -m pipelines.gee.export_static_layers --pilot
```
Download the Drive outputs into `data/raw/gee/` and rename them to `dem_glo30.tif`, `landcover_fractions.tif`, `jrc_occurrence.tif`
(drop the `_pilot` suffix, or pass paths explicitly). For urban Guwahati, prefer **FABDEM** as `dem_glo30.tif`.

### A3. Terrain derivatives (WhiteboxTools)
```bash
python -m pipelines.build_static_features terrain
```
| Raster | How | Why it matters |
|--------|-----|----------------|
| `dem_breached` | least-cost depression breaching | hydrologically connected surface |
| `flow_acc` → `streams` | D8, threshold 1000 cells (~0.9 km²) | the drainage network |
| **`hand`** | elevation above nearest stream | **the single most useful feature** |
| `slope` | degrees | flat ground drains slowly |
| `twi` | ln(a / tan β) | where water accumulates |
| `dist_stream` | Euclidean distance | proximity to channels and drains |

Look at HAND over Guwahati before continuing. Low values should trace the Bharalu, Bahini and the
wetlands (Deepor Beel). Lower `STREAM_THRESHOLD_CELLS` if the city's drains are missing.
Add OSM `waterway=drain|canal|stream` lines as extra streams if the DEM can't resolve them.

### A4. Flood history labels from Sentinel-1
1. Eyeball one event in the Code Editor with `pipelines/gee/s1_flood_mapping.js` and tune `DIFF_DB` / `WATER_DB` if needed.
2. Upload the H3 grid as an Earth Engine table asset: write `cells_to_gdf(cells).to_file("h3_res9.shp")`
   (keep the `h3` column), zip it, then Code Editor → Assets → New → Shape files. Do the same for res 8.
3. Export labels per year (each is one Drive CSV):
   ```bash
   python -m pipelines.gee.s1_flood_mapping labels --year 2019 --cells-asset projects/<p>/assets/h3_res9
   ```
   Repeat for 2017–2025. Start with the pilot asset because state-wide exports take hours.
4. Export flood frequency from **training years only** (exclude `HINDCAST_YEAR`=2022):
   ```bash
   python -m pipelines.gee.s1_flood_mapping frequency --years 2017 2018 2019 2020 2021 2023 2024
   ```

### A5. Per-cell features
```bash
python -m pipelines.build_static_features zonal --res 9 --pilot
```
Output: `static_res9_pilot.parquet`, which has `hand_*`, `slope_*`, `twi_*`, `dist_stream_*`, `lc_*`, `jrc_occ_*`,
`s1_freq_*`, `is_permanent_water`.

### A6. Train and validate
```bash
python -m ml.inundation.train_susceptibility --res 9 --pilot
```
- Label: cell flooded (≥10 % of observed area) in any training-year window.
- Random Forest with balanced class weights and OOB score.
- **Validation:** do the cells that flooded in **2022** (held out) rank at the top? The script prints ROC-AUC,
  PR-AUC vs the base rate, CSI/POD/FAR, and "share of 2022 flooded cells inside the top-10 % most susceptible".
- Second check: overlay `waterlogging_points.csv`. What fraction fall in the top 20 % of cells?

### A7. The deliverable
- A map of susceptibility per res-9 hexagon, plus a table of **localities ranked by mean susceptibility**.
- A feature-importance chart. HAND, distance to drain and built-up share should dominate. If an odd feature leads, investigate before you present it.

**Done when:** the map exists, the held-out-year check is printed, and the waterlogging-point hit rate is known.

---

## Part B — Dynamic flood prediction

Now add *when*: P(cell floods | terrain, recent rain, forecast rain, river state, soil wetness).

### B1. Contract
**Output** `inundation_cells.parquet`: `h3, horizon (6h|24h|72h|120h), p_flood, drivers`.

### B2. Training table
```bash
python -m ml.inundation.dataset --res 8
```
One row per (cell, Sentinel-1 window) with:
- label `flooded` (flood fraction ≥ 0.1; permanent water and poorly observed cells dropped)
- static features (as in Part A)
- dynamic features at the window end: `rain_1d/3d/7d/15d/30d`, `rain_max1d_7d` (IMD), `river_q_anom`
  (Brahmaputra flow anomaly, GloFAS or CWC), `soil_moisture` (ERA5-Land, TODO)

Negatives are free: dry windows and dry cells in wet windows. Positives are rarer, so watch the class balance printed by the script.

### B3. Train
```bash
python -m ml.inundation.train_dynamic --res 8
```
- LightGBM with `scale_pos_weight`.
- **Leave-one-year-out CV** on the development years, then a single evaluation on 2022.
- Report PR-AUC (with the base rate), CSI/POD/FAR at the CSI-optimal threshold, and BSS.
- Optionally add a spatial-block check: hold out whole districts to see how the model transfers to unseen places.

### B4. From observed rain to forecast rain (the key idea)
The model is trained on *observed* rain. At forecast time rain is uncertain, so `predict.py`
integrates over Engine 2's categories:

```
P(flood) = (1 − p_h)·f(r_below) + (p_h − p_vh)·f(90 mm) + (p_vh − p_x)·f(160 mm) + p_x·f(250 mm)
```

Here `f` is the dynamic model with the scenario rain added on top of observed antecedent rain. The
chance of extreme rain then feeds through to local flood probability without pretending we know the exact amount.

- 6 h horizon: Engine 1's 6 h accumulation (`predict_nowcast`)
- 24 h / 72 h / 120 h: Engine 2's day-1 / cumulative day-1..3 / day-1..5 probabilities
- River-driven flooding: combine with Engine 4a via `combine_pluvial_fluvial` (see the Engine 4 guide)

### B5. The "why" panel
`explain.py` runs SHAP on the LightGBM model and keeps the top 3 **risk-increasing** contributions, rendered through
templates, e.g. *"low-lying: 2.8 m above nearest drainage · 140 mm rain in last 3 days · Brahmaputra flow +35 % vs normal"*.
Store them as `drivers` JSON per cell; the API serves them as is.

### B6. Urban waterlogging (Guwahati)
Sentinel-1 at 10 m misses most street flooding. Three things compensate:
1. The res-9 susceptibility model with built-up share and drain distance
2. A rule layer: cells with HAND < 3 m **and** built-up > 50 % **and** forecast rain ≥ very heavy → at least Orange
3. Validation against the waterlogging list, not S1

Say this openly in the presentation. It shows you understand the data's limits.

## Pitfalls

- **Permanent water isn't flood.** Drop JRC occurrence > 80 % cells, or the model learns "rivers are wet".
- **Frequency leakage:** `s1_freq_*` built with the test year gives it the answer. Rebuild it or use `--drop-s1-freq`.
- **Spatial autocorrelation:** random row splits inflate scores massively. Group by year (and optionally by region).
- **Acquisition timing:** a 12-day `min()` composite doesn't tell you the exact flood day. For better rain alignment, record S1 acquisition dates per window and compute rain up to that date.
- **Vegetated floods** (paddy, forest) are under-detected by VV. Adding VH or a flooded-vegetation rule is an upgrade.
- **Resolution mix:** res-8 labels can't train the res-9 model. `load_labels(res)` filters by resolution, so export labels separately for each asset.

## Done when

- [ ] Milestone 1 map + locality ranking + held-out-2022 check
- [ ] Dynamic model with LOYO CV and a single 2022 test score
- [ ] Scenario integration produces `inundation_cells.parquet` for 24 h from Engine 2 output
- [ ] SHAP drivers stored per cell; three sample sentences reviewed by a teammate for plain language
- [ ] Waterlogging-point hit rate reported
- [ ] Model card filled
