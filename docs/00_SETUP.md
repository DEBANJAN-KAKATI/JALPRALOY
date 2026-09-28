# 00 · Setup

Goal: every team member can run the demo stack and the ML environment on day 1.

## 1. Tools

| Tool | Why | Notes |
|------|-----|-------|
| Git | version control | `git init` in the repo root, then push to a private GitHub repo |
| **Miniforge** (conda) | geospatial Python stack | https://github.com/conda-forge/miniforge |
| Node.js 20+ | frontend | already installed (v24) |
| Docker Desktop (WSL2 backend) | PostGIS + Redis | optional for the demo; required for the full stack |
| VS Code + Python, Jupyter, ESLint extensions | editing | |

**Why not the system Python?** This machine has Python 3.14. GDAL, pySTEPS, LightGBM, WhiteboxTools
and friends lag new Python releases, so use the conda env pinned to **Python 3.11**.

> The repo path contains spaces (`D:\New folder\...`). Most tools cope when paths are quoted.
> If a native tool (WhiteboxTools, GDAL CLI) fails on a path, move the repo to e.g. `D:\jalproloi`.

## 2. Python environments

There are two, on purpose:

```bash
# ML + pipelines (heavy): the whole team
conda env create -f environment.yml
conda activate jalproloi
pip install -e .           # makes `ml` and `pipelines` importable anywhere
pytest                     # ml/tests should pass
```

```bash
# Backend only (light): the backend developer, and the Docker image
cd backend
python -m venv .venv && .venv\Scripts\activate      # or use the conda env
pip install -r requirements.txt
pytest                     # backend/tests should pass
```

PyTorch (Engine 1 upgrade only): `pip install torch --index-url https://download.pytorch.org/whl/cpu`
locally, or train on Colab/Kaggle GPUs.

## 3. Accounts (start these on day 1 — some take days)

| Account | Used for | How | Gotcha |
|---------|----------|-----|--------|
| **Google Earth Engine** | Sentinel-1 flood maps, DEM, WorldCover, JRC water, ERA5-Land | https://earthengine.google.com → register a *noncommercial* Cloud project; `earthengine authenticate`; set `GEE_PROJECT` in `.env` | You need a Google Cloud project ID, not just a login |
| **NASA Earthdata** | GPM IMERG, SMAP | https://urs.earthdata.nasa.gov; set `EARTHDATA_USERNAME/PASSWORD` | In your profile → *Applications → Authorized Apps*, approve **"NASA GESDISC DATA ARCHIVE"** or IMERG downloads return 401 |
| **ISRO MOSDAC** | INSAT-3D/3DR rainfall (HEM) | https://www.mosdac.gov.in → sign up | Manual approval; can take several days |
| **Copernicus CDS** | ERA5 / ERA5-Land (if not via GEE) | https://cds.climate.copernicus.eu; `CDSAPI_KEY` | Accept each dataset's licence on its web page once |
| **IMD data request** | Doppler radar volumes (Guwahati, Mohanbari), station data | Formal letter/email via your SIH nodal contact | IMD is the problem owner — ask early and politely |
| **CWC / India-WRIS** | River gauge history | https://indiawris.gov.in; CWC FFS portal | Formal request is better than scraping |
| Telegram BotFather | alert channel | `/newbot` in Telegram → `TELEGRAM_BOT_TOKEN` | |

Copy `.env.example` to `.env` and fill in what you have. Never commit `.env`.

## 4. Run the demo stack

```bash
docker compose up -d db redis        # PostGIS on 5432, Redis on 6379
```

```bash
cd backend && uvicorn app.main:app --reload     # http://localhost:8000/docs
```

```bash
cd frontend && npm install && npm run dev        # http://localhost:5173
```

`DEMO_MODE=true` serves **synthetic** data labelled `synthetic-demo`; the UI shows a yellow notice.
Or run everything with `docker compose up`.

> Windows note: if `npm install` fails with *"'node' is not recognized"* inside Git Bash, run it
> from PowerShell or cmd instead (a dependency's install script calls `node` via cmd.exe).

## 5. First data smoke test (30 min)

```bash
python -m pipelines.prepare_boundaries --localities
python -m pipelines.build_h3_grid --pilot
python -m pipelines.ingest_openmeteo              # real forecast for Guwahati, no key
python -m pipelines.ingest_river_levels glofas     # GloFAS discharge at the 6 gauges
```

## Done when

- [ ] `pytest` passes in both environments
- [ ] http://localhost:5173 shows the hex map over Guwahati
- [ ] `data/processed/h3/cells_res9_pilot.parquet` exists
- [ ] GEE, Earthdata (with GES DISC approved), MOSDAC and CDS accounts requested
- [ ] IMD and CWC data-request emails sent
