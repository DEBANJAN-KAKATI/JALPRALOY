# 09 · Validation and the hindcast demo

Validation is what separates a convincing early-warning system from a pretty map. IMD evaluators will ask *how
you know it works*. Answer with standard metrics, honest baselines and a replay of a real flood.

## Rules (non-negotiable)

1. **Split by time.** `HINDCAST_YEAR = 2022` is never used to train, tune, calibrate or choose thresholds.
   `VALIDATION_YEAR = 2024` is for tuning. Everything else is training data. (Both live in `ml/common/config.py`.)
2. **No future data.** A forecast issued at time T may only use data *available* at T, including product latency
   (IMERG Early ~4 h, GFS ~5 h, IMD daily next day). `ml/evaluation/hindcast.py` encodes these latencies.
3. **No label leakage through features.** S1 flood frequency must exclude the test year. No same-day observed rain as a feature for a forecast.
4. **Always show a baseline:** persistence (Engines 1, 4a), raw NWP (Engine 2), climatology (Brier skill), and HAND-only susceptibility (Engine 3).
5. **Freeze thresholds before looking at the test event.**

## Metrics cheat-sheet (`ml/evaluation/metrics.py`)

| Metric | Formula | Good | Used for |
|--------|---------|------|----------|
| POD (hit rate) | H / (H + M) | → 1 | all yes/no warnings |
| FAR | F / (H + F) | → 0 | all yes/no warnings |
| CSI (threat score) | H / (H + M + F) | → 1 | headline skill for rare events |
| Frequency bias | (H + F) / (H + M) | ≈ 1 | over- or under-warning |
| ETS | CSI corrected for chance | > 0 | comparing regions with different base rates |
| Brier score / BSS | mean (p − o)² / 1 − BS/BS_ref | BSS > 0 | probabilities |
| Reliability | observed frequency per probability bin | on the diagonal | calibration |
| FSS | fractions skill score | ≥ 0.5 + f₀/2 is "useful" | nowcast spatial skill |
| NSE | 1 − Σ(s−o)²/Σ(o−ō)² | → 1 | river levels |
| PR-AUC | area under precision–recall | ≫ base rate | flood classifier |

H = hits, M = misses, F = false alarms. Report the sample size (number of events) next to every score.

## Per-engine evaluation summary

| Engine | Test data | Main chart |
|--------|-----------|-----------|
| 1 Nowcast | ≥20 storms in 2022 | CSI@5 mm/h vs lead time: persistence vs extrapolation vs STEPS |
| 2 Heavy rain | all 2022 monsoon days | CSI/POD/FAR table per threshold × lead day vs raw GFS; reliability diagram |
| 3 Inundation | 2022 S1 windows + waterlogging points | map of predicted vs observed; PR curve; % of flooded cells in top-10 % |
| 4a River | 2022 flood season | hydrograph: observed vs forecast at 24/48/72 h; danger-level CSI |
| 4b Impact | 2022 | predicted affected localities vs reported ones (ASDMA daily reports) |

## The hindcast demo (Phase 6)

**Goal:** show the system warning 24–48 h *before* a real flood, using only information available then.

### Pick the event
Candidates: the June 2022 floods (widespread Assam flooding with severe Guwahati waterlogging), or a 2024 event if you
switch the hold-out year. Before building anything, collect the *record*: IMD warnings issued, observed rainfall, CWC
levels, S1 flood maps and news reports with timestamps. Put the verified onset time in `EVENTS` in `hindcast.py`.

### Run it
```bash
python -m ml.evaluation.hindcast --event guwahati-2022-06 --lead-hours 72 48 24 12 6
```
For each issue time the script records which data would have been available. Wire it to call
`pipelines/run_forecast.py --issue-time …` so each replay run is stored with `kind='hindcast'`.

### Tell the story (3 minutes)
1. **T−72 h:** Engine 2 shows Yellow over Kamrup Metro (P(heavy) rising). Susceptibility map is already known.
2. **T−48 h:** Orange; the most-affected list names the low-lying localities; the river forecast shows the Brahmaputra rising at Guwahati.
3. **T−24 h:** Red for specific hexagons; the CAP alert (status *Exercise*) is generated and a Telegram message is sent.
4. **T−6 h:** the nowcast shows the rain band moving in, with an ETA.
5. **T+0:** overlay what actually happened: S1 flood extent and waterlogging points on the predicted hexagons.
6. **Scorecard:** hits, misses and false alarms for the event, next to what raw GFS alone would have said.

Show at least one failure honestly (a miss or a false alarm) and explain it. Judges trust teams that do.

## Done when
- [ ] Every engine's scores CSV exists with baselines
- [ ] Hindcast replay produces a timeline of warnings for the event
- [ ] Overlay figure: predicted vs observed flooding
- [ ] Leakage checklist in `hindcast.py` ticked and reviewed by a second teammate
