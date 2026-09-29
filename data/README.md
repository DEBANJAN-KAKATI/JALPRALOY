# data/ — the local data lake (git-ignored)

```
data/
├── raw/                       # exactly as downloaded; never edit by hand
│   ├── imd/                   # IMD 0.25° daily gridded rainfall (.grd from imdlib)
│   ├── imerg/                 # GPM IMERG half-hourly HDF5
│   ├── insat/                 # INSAT-3D/3DR HEM rainfall (MOSDAC)
│   ├── nwp/gfs/ nwp/ecmwf/    # GRIB2
│   ├── dem/                   # Copernicus GLO-30 / FABDEM tiles or GEE export
│   ├── gee/                   # GeoTIFF/CSV exports from pipelines/gee/
│   ├── river/                 # CWC / India-WRIS downloads, Open-Meteo JSON
│   └── worldpop/              # population rasters
├── processed/                 # analysis-ready, reproducible from raw/ by scripts
│   ├── grids/                 # imd_rain.nc, imerg.zarr, era5l_sm.nc
│   ├── nwp/                   # gfs_daily.zarr (init, lead_day, lat, lon)
│   ├── terrain/               # hand.tif, slope.tif, twi.tif, dist_stream.tif (UTM 46N)
│   ├── h3/                    # cells_res8.parquet, cells_res9_pilot.parquet
│   ├── features/              # static_res8.parquet, exposure_res8.parquet
│   ├── training/              # model training tables
│   ├── river/                 # levels.parquet (station, time, level_m, discharge_m3s)
│   └── forecasts/             # per-run engine outputs (run_id=YYYYmmddHHMM)
└── static/                    # boundaries and hand-curated lists
    ├── boundaries/            # assam_state.geojson, assam_districts.geojson, guwahati_localities.geojson
    ├── gauges.csv             # CWC stations + warning/danger levels (tracked in git)
    └── waterlogging_points.csv# verified Guwahati waterlogging points (tracked in git)
```

Rules:
1. Everything in `processed/` must be reproducible by a script in `pipelines/` or `ml/`.
2. Time is stored in **UTC**; the UI converts to IST.
3. Grids are stored as NetCDF/Zarr with dims named `time, lat, lon` (ascending lat).
4. Hexagons are identified by their H3 index string in a column named `h3`.
