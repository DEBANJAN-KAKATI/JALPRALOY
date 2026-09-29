# Notebooks

Exploration only. Anything worth keeping moves into a module under `ml/` or `pipelines/`.
Prefix with a number and your initials so the team can find things.

Suggested set:

| Notebook | Purpose |
|----------|---------|
| `01_imd_rainfall_eda.ipynb` | Climatology of heavy-rain days over Assam; check the IMD day-label alignment |
| `02_s1_flood_labels_qc.ipynb` | Map S1 labels for 2022 against news reports and the waterlogging list |
| `03_susceptibility_map.ipynb` | Milestone 1 figure: Guwahati susceptibility by locality |
| `04_nwp_bias.ipynb` | GFS vs IMD scatter and bias by lead day, valley vs hills |
| `05_pysteps_case.ipynb` | Motion field and nowcast animation for one storm |
| `06_river_lags.ipynb` | Cross-correlation lags Dibrugarh → Guwahati → Dhubri |
| `07_hindcast_story.ipynb` | Figures for the demo: warnings at −72/−48/−24 h vs what happened |

Run with the `jalproloi` conda env: `jupyter lab` from the repo root.
