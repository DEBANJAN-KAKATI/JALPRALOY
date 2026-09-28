# Engine 2 · Heavy-rainfall forecast (1–5 days)

> **Question:** what is the probability of IMD *heavy*, *very heavy* and *extremely heavy* rain at each place, day by day, for the next 5 days?
> **Output in the UI:** "Rain expected: 180 mm 🟠", rain-layer colours, the `+24h / +3 days / +5 days` steps.

Code: `ml/rainfall_forecast/` · Input scripts: `ingest_nwp.py`, `ingest_imd.py` · Owner: ML (rainfall)

---

## 1. Contract

**Input:** one NWP run aggregated to IMD rainfall days: `(init, lead_day=1..5, lat, lon)` with
`tp_mm, pwat, cape, rh850, rh700, u850, v850`.

**Output** (`rainfall_grid.parquet`, `rainfall_cells.parquet`):

| Column | Meaning |
|--------|---------|
| `p_heavy` | P(24 h rain ≥ 64.5 mm) |
| `p_very_heavy` | P(≥ 115.6 mm) |
| `p_extreme` | P(≥ 204.5 mm) |
| `rain_mm_expected` | expected 24 h amount (regression) |
| `color` | IMD colour from the decision matrix |

Guaranteed: `p_heavy ≥ p_very_heavy ≥ p_extreme` (`enforce_monotone`).

## 2. Why this design

Raw global models get the monsoon's large-scale pattern roughly right. Over Northeast India's hills
they are systematically biased: orographic rain on the southern slopes, the Brahmaputra valley and
the Barak valley each behave differently. A gradient-boosting model learns *"when GFS says X, with this
much moisture and this wind, at this place, IMD observed Y"*. That is statistical post-processing
(MOS). It is cheap and interpretable, and it reliably beats raw NWP.

Using IMD's own thresholds and colours means officials read the output without a legend.

| IMD category | 24 h rainfall |
|--------------|---------------|
| Heavy | 64.5–115.5 mm |
| Very heavy | 115.6–204.4 mm |
| Extremely heavy | ≥ 204.5 mm |

## 3. Build steps

**Step 1 — Target.** Download IMD daily grids for 2000–2025:
```bash
python -m pipelines.ingest_imd --start 2000 --end 2025
```
Then settle the **day-label convention** with `check_day_alignment` and set `IMD_DAY_LABEL`.

**Step 2 — Archived forecasts.** Training needs past *forecasts*, not analyses:
```bash
python -m pipelines.ingest_nwp gfs --season 2021      # repeat for 2022, 2023, 2024, 2025
```
Each season is ~180 runs × 21 steps. Start with one season to debug, and run the rest overnight.
Only a small Assam box is kept, so storage is modest. For more years, add GEFS Reforecast v12 (2000–2019).

**Step 3 — Training table.**
```bash
python -m ml.rainfall_forecast.build_training_table --model gfs
```
One row per `(init, lead_day, lat, lon)` in Assam plus a 1° buffer, monsoon months only.
Features (`features.py`, shared with prediction so they can't drift apart):
- NWP at the point, **plus 3×3 and 5×5 neighbourhood max and mean** of `tp_mm`, which tolerates displacement errors
- moisture and instability: `pwat`, `cape`, `rh850`, `rh700`, wind speed, `ivt_proxy = pwat × wind850`
- location: `lat, lon` (add `elev_mean` from the DEM on the 0.25° grid), `lead_day`
- season: `doy_sin`, `doy_cos`
- *(add)* antecedent observed rain up to the init time, and the ECMWF `tp` when available (a two-model feature)

**Step 4 — Train.**
```bash
python -m ml.rainfall_forecast.train_lgbm --model gfs
```
- One global LightGBM per threshold, not one per grid cell. Per-cell models see too few heavy days and overfit; location features recover the per-cell behaviour. Per-region models (valley vs hills) are a fair experiment.
- `scale_pos_weight` handles rarity, then **isotonic calibration** on the validation year restores honest probabilities.
- A Tweedie regressor predicts the amount in mm.
- Split: train = all years except `VALIDATION_YEAR` (2024) and `HINDCAST_YEAR` (2022). Early stopping, calibration and the decision threshold all come from 2024. 2022 is only scored at the end.

**Step 5 — Read the scores** (`ml/models/rainfall_forecast/gfs_scores.csv`), per lead day and threshold:
`AUC, BSS, CSI, POD, FAR` next to `csi_raw_nwp, pod_raw_nwp, far_raw_nwp`.

**Step 6 — Colours.** `ml/common/imd.py::rain_color`:

| Colour | Rule (tunable) |
|--------|----------------|
| 🔴 Red / Act | P(extreme) ≥ 0.4 **or** P(very heavy) ≥ 0.7 |
| 🟠 Orange / Prepare | P(very heavy) ≥ 0.4 **or** P(heavy) ≥ 0.7 |
| 🟡 Yellow / Watch | P(heavy) ≥ 0.3 |
| 🟢 Green / Low | otherwise |

This matrix is *our* convention. Show it to IMD Guwahati, adjust it, and write any change into the model card.

**Step 7 — Predict and serve.**
```bash
python -m ml.rainfall_forecast.predict --model gfs
```
Grid → H3 by nearest 0.25° point (`grid_to_h3`). Wire it into `run_forecast.run_rainfall`.

## 4. Verification

| Metric | Target behaviour |
|--------|------------------|
| **CSI, POD, FAR** at each IMD threshold, per lead day | beat raw NWP at every lead day; if not, fall back to raw NWP at that lead and say so |
| Brier Skill Score vs climatology | > 0 |
| Reliability diagram | points near the diagonal (use `reliability_curve`) |
| ROC AUC | shows discrimination, independent of the threshold |
| Case study: 2022 test year | map P(very heavy) at day-1/day-3 vs observed |

Present CSI/POD/FAR as IMD does (per threshold, per lead day), because evaluators know how to read that table.

## 5. Pitfalls

- **Day misalignment** (see step 1) is the number one silent bug. It turns a good model into a mediocre one.
- **Leakage through features:** anything observed *after* the init time (e.g. same-day IMD rain) must not be a feature.
- **Random splits** leak because neighbouring days and grid points are correlated. Split by year.
- **Rare events:** extremely heavy days are few, so the P(extreme) model is the least reliable. Report its sample size, and consider pooling with very heavy.
- **Resolution honesty:** 0.25° ≈ 25 km. This engine gives the *regional* hazard, and Engine 3 localises it.
- **Model changes:** GFS was upgraded over the years (v15 → v16). A bias learned on one version may shift. Retrain every season.

## 6. Upgrades (in value order)

1. Add ECMWF as a second input: disagreement between models is itself a useful uncertainty feature.
2. Use GEFS ensemble spread as a feature (more years via the reforecast).
3. Add NCUM, the Indian model, once available. It is also a good talking point with IMD.
4. Sub-daily (6-hourly) targets from IMERG, for the 6–24 h gap between Engines 1 and 2.
5. Spatial deep post-processing (a U-Net over the NWP fields) for heavy-rain placement.

## 7. Done when

- [ ] IMD day convention verified and documented
- [ ] ≥ 3 GFS seasons ingested; training table built
- [ ] Scores CSV shows skill vs raw NWP per lead day and threshold
- [ ] Reliability diagram for P(heavy) on 2024 and 2022
- [ ] `rainfall_cells.parquet` produced for the latest run
- [ ] Model card filled
