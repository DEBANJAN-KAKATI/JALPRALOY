# Engine 1 · Rainfall nowcasting (0–6 h)

> **Question:** where is it raining now, and where will that rain be in the next 6 hours?
> **Output in the UI:** arrows on the map; "heavy rain cell moving NE at 25 km/h, expected over Kamrup Metro in 2–3 h"; the `Now` and `+6h` timeline steps.

Code: `ml/nowcast/` · Input script: `pipelines/ingest_imerg.py` · Owner: ML (rainfall)

---

## 1. Contract

**Input:** the last 4 rain-rate frames (mm/h) on a regular lat/lon grid covering `NOWCAST_BBOX`
(85–100°E, 20–30.5°N). The box is much bigger than Assam because storms arrive from Bangladesh,
Meghalaya and the Bay of Bengal.

**Output** (`nowcast_<method>.nc` → `nowcast_cells.parquet`):

| Field | Meaning |
|-------|---------|
| `rain_mmh(lead, lat, lon)` | forecast rain rate at leads 30…360 min |
| `exc_prob(threshold, lead, lat, lon)` | P(rate > 1/5/10/20 mm/h), STEPS ensemble only |
| `u, v` | motion field (pixels per 30 min) |
| per cell: `rain_mm_6h`, `eta_min`, `p_rain_gt_10mmh` | what Engine 3 and the UI consume |

## 2. Why this design

Optical flow tracks rain cells and pushes them forward along their motion. It is physically
simple and hard to beat for the first hour or two. pySTEPS is the standard open-source
implementation. It adds a stochastic ensemble (STEPS) that gives probabilities and lets
small-scale rain die out realistically with lead time. Deep models (ConvLSTM/U-Net) can learn
growth and decay, but only after the baseline is solid and verified.

## 3. Data choices

| Source | Resolution | Latency | Use |
|--------|-----------|---------|-----|
| IMERG Early | 0.1°, 30 min | ~4 h | training, hindcasts, first prototype |
| IMERG Final | 0.1°, 30 min | ~3.5 mo | training |
| INSAT-3DR HEM (MOSDAC) | ~4 km, 30 min | ~30–60 min | **live** operation |
| IMD DWR Guwahati / Mohanbari | ~1 km, 10 min | minutes | best 0–2 h city nowcast, if IMD shares it |

Build and verify on IMERG first because it is free and easy to get. Then swap the input to INSAT/radar.
The code doesn't care about the source as long as it's a `(time, lat, lon)` mm/h array.

## 4. Build steps

**Step 1 — Get a storm.** Download IMERG for a known heavy-rain case, e.g. mid-June 2022:
```bash
python -m pipelines.ingest_imerg --start 2022-06-13 --end 2022-06-17 --run final
```
Plot a few frames in a notebook (`05_pysteps_case.ipynb`) and check that the rain sits where you expect.

**Step 2 — Deterministic extrapolation.**
```bash
python -m ml.nowcast.pysteps_baseline --issue-time 2022-06-14T12:00 --method extrapolation
```
The steps are: dB transform → Lucas–Kanade motion (`motion.get_method("LK")`) → semi-Lagrangian
extrapolation. Animate observed frames next to forecast frames to check them.

**Step 3 — Probabilistic STEPS.** `--method steps` produces a 20-member ensemble and exceedance
probabilities. Key parameters: `n_cascade_levels=6`, `kmperpixel=10`, `timestep=30`,
`precip_thr = 10·log10(0.1)`. Fix the `seed` for reproducibility.

**Step 4 — Cells, ETA, arrows.** `ml/nowcast/arrival.py`:
- `eta_for_cells`: minutes until the rate first exceeds 10 mm/h at each hexagon
- `motion_arrows`: subsampled vectors with speed (km/h) and bearing, only where it is raining
- `region_eta`: when ≥5 % of Kamrup Metro exceeds the threshold → the sentence in the banner

Check the sign of `v` against your latitude ordering. A storm moving north must produce a
bearing near 0°. Test this with a synthetic blob that you shift by one row.

**Step 5 — Verify (next section).** Don't move on until extrapolation beats persistence.

**Step 6 — Upgrade: ConvLSTM / U-Net** (`ml/nowcast/convlstm.py`, on a Colab GPU):
1. Build sequences from IMERG 2015–2021 (Jun–Sep), crop to a size divisible by 4, and apply the `log1p` transform.
2. Keep only samples with ≥5 % wet pixels, or the model learns "always dry".
3. Split **by year**: train 2015–2021 (excluding 2022), validate on 2024, test on 2022.
4. Use the intensity-weighted MSE (heavier rain weighs more) so heavy cores don't blur away.
5. Compare against pySTEPS on the same test cases. Adopt it only for lead times where it wins.
6. Optional: blend the two by averaging pySTEPS and the DL output with lead-dependent weights.

**Step 7 — Operational wiring.** Implement `run_nowcast` in `pipelines/run_forecast.py`: load frames,
respecting latency, run STEPS, write the `.nc` file and `nowcast_cells.parquet`.

## 5. Verification

Compute for every lead time (30…360 min) over many cases (≥20 monsoon storms, test year):

| Metric | Why |
|--------|-----|
| CSI / POD / FAR at 1, 5, 10 mm/h | categorical skill IMD recognises |
| FSS (fractions skill score) at 10–50 km scales | forgives small position errors; `pysteps.verification.spatialscores.fss` |
| CRPS / reliability of `exc_prob` | is "70 %" right 70 % of the time? |

**Baselines on the same plot:** Eulerian persistence (`persistence()` in the code) and extrapolation.
The chart "CSI vs lead time: persistence < extrapolation < STEPS (< ConvLSTM)" is a strong demo slide.

## 6. Pitfalls

- **Latency lies.** An IMERG-Early "nowcast" issued at 12:00 actually starts at ~08:00. Say so, and switch to INSAT/radar for live use.
- **Orography.** Rain over the Meghalaya plateau and the Himalayan foothills is locked to terrain and doesn't advect. Extrapolation will move it anyway. Expect lower skill there, and consider masking the motion field over high terrain.
- **Growth and decay.** Optical flow can't create new storms. Convective initiation in the afternoon is invisible to it, which is the main thing the DL upgrade can add.
- **Missing frames.** Fill with 0 only for isolated NaNs. Skip the run if a whole frame is missing.
- **Scale honesty.** 0.1° is about 11 km, so this engine cannot tell Anil Nagar from Zoo Road. Engine 3 does the local downscaling.

## 7. Done when

- [ ] Extrapolation and STEPS run for any issue time with one command
- [ ] CSI-vs-lead chart shows extrapolation beating persistence at every lead
- [ ] Per-cell ETA and motion arrows written for the pilot
- [ ] Model card filled (`docs/model_cards/TEMPLATE.md`)
- [ ] (Upgrade) ConvLSTM evaluated against STEPS on the 2022 test year
