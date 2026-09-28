# 11 · Roadmap (7 weeks, team of six)

## Roles

| Person | Owns | Primary guides |
|--------|------|----------------|
| P1 Data engineering | ingestion scripts, scheduler, data lake, DB loading | 02, 01 |
| P2 ML — rainfall | Engines 1 and 2, verification | ENGINE_1, ENGINE_2, 09 |
| P3 ML — inundation | Engines 3 and 4, impact | ENGINE_3, ENGINE_4 |
| P4 Backend | FastAPI, PostGIS, fusion writer, alerts/CAP, Telegram | 07, 08 |
| P5 Frontend | React PWA, i18n, offline, hindcast mode | 10 |
| P6 GIS + domain + pitch | boundaries, HAND QA, S1 labels QA, waterlogging list, IMD/CWC liaison, presentation | 02, ENGINE_3, 09 |

## Phases

### Phase 0 · Setup (week 1)
- [ ] Everyone: `docs/00_SETUP.md` done-when list
- [ ] P6: IMD radar and CWC gauge data requests sent (day 1!)
- [ ] P1: boundaries + H3 grid (`prepare_boundaries`, `build_h3_grid --pilot`)
- [ ] P4/P5: demo stack running; P5 starts UI polish against the synthetic API

### Phase 1 · Data pipeline (weeks 1–2)
- [ ] P1: IMD 2000–2025; IMERG for 3 test storms; GFS 2021 season; GloFAS discharge 1995–2025
- [ ] P6: GEE static layers + S1 labels for the pilot, 2017–2025; waterlogging list ≥ 40 points
- [ ] P2: settle the IMD day convention (`check_day_alignment`)

### Phase 2 · Static susceptibility — **Milestone 1** (weeks 2–3)
- [ ] P3: terrain derivatives, zonal features, `train_susceptibility --res 9 --pilot`
- [ ] P6: QA HAND over Guwahati; check the ranking against local knowledge
- [ ] P5: show susceptibility as the `now` layer; P4 loads it into `cells.susceptibility`
- **Demo checkpoint:** "these localities of Guwahati are most flood-prone, validated on 2022"

### Phase 3 · Rainfall models (weeks 3–4)
- [ ] P2: pySTEPS extrapolation + STEPS; CSI-vs-lead chart
- [ ] P2: GFS 2021–2025 → training table → LightGBM → scores vs raw GFS
- [ ] P1: scheduler jobs for IMERG/NWP live

### Phase 4 · Integration and API (weeks 4–5)
- [ ] P3: dynamic flood model + scenario integration; river lag model (GloFAS or CWC); impact ranking
- [ ] P4: `run_fuse` writes runs/cell_forecasts/area_forecasts; `DatabaseProvider`; Redis cache
- [ ] Switch `DEMO_MODE=false` for the pilot

### Phase 5 · Interface, alerts, sync (weeks 5–6)
- [ ] P5: arrows, river layer, saved places, admin, hindcast mode, translations reviewed
- [ ] P4: alert logic (raise/downgrade/cancel), CAP validated, Telegram bot, web push
- [ ] P1: 30-min / 6-h / hourly jobs stable for 48 h without intervention

### Phase 6 · Validation and demo (week 7)
- [ ] P2/P3: all scores CSVs with baselines; model cards
- [ ] Everyone: hindcast replay of the chosen 2022 event end to end
- [ ] P6: pitch (problem → 4 engines → live UI → hindcast → scores → scale-up to all Assam and to IMD)
- [ ] Dry-run the demo offline (airplane mode) to prove the PWA works

## Scope guards
- Pilot first: Kamrup Metropolitan at res 9. Expand to all Assam at res 8 only after Phase 4 works.
- Every engine keeps a working baseline. Upgrades (ConvLSTM, LSTM routing) only happen if time is left.
- If CWC data doesn't arrive, ship with GloFAS discharge and say so.
- If radar data doesn't arrive, ship with IMERG/INSAT and say so.
