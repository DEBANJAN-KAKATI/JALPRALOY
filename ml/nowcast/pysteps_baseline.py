"""Engine 1 baseline: optical-flow rainfall nowcasting with pySTEPS.

    python -m ml.nowcast.pysteps_baseline --issue-time 2022-06-14T12:00 --method steps

Pipeline: last N rain frames (mm/h) -> dB transform -> Lucas–Kanade motion field ->
extrapolate (deterministic) or STEPS (probabilistic ensemble) for 12 × 30 min = 6 h.

Outputs (data/processed/forecasts/<run>/nowcast_*.nc):
    rain_mmh   (lead, lat, lon)  deterministic or ensemble-mean rain rate
    exc_prob   (threshold, lead, lat, lon)  P(rain rate > thr), STEPS only
    u, v       (lat, lon)  motion in pixels per timestep
"""
from __future__ import annotations

import argparse
from datetime import datetime

import numpy as np
import xarray as xr

from ml.common.config import PROCESSED

IMERG = PROCESSED / "grids" / "imerg.zarr"
TIMESTEP_MIN = 30
N_LEADS = 12                 # 6 h
N_INPUT = 4                  # frames used for motion estimation
KM_PER_PIXEL = 10.0          # IMERG 0.1°
RAIN_THR_MMH = 0.1
THRESHOLDS_MMH = (1.0, 5.0, 10.0, 20.0)


def load_frames(issue: datetime, n: int = N_INPUT) -> xr.DataArray:
    """Last n frames at or before issue time. In a hindcast, also respect product
    latency: IMERG Early is ~4 h late, so at issue time T the newest usable frame is ~T-4h."""
    da = xr.open_zarr(IMERG)["rain_mmh"].sel(time=slice(None, np.datetime64(issue)))
    da = da.isel(time=slice(-n, None)).load()
    if da.sizes["time"] < n:
        raise ValueError(f"need {n} frames before {issue}, found {da.sizes['time']}")
    return da.fillna(0.0)


def run_nowcast(frames: xr.DataArray, method: str = "extrapolation", n_ens: int = 20, seed: int = 42) -> xr.Dataset:
    from pysteps import motion, nowcasts
    from pysteps.postprocessing import ensemblestats
    from pysteps.utils import transformation

    R = frames.values.astype(float)
    R_db, _ = transformation.dB_transform(R, threshold=RAIN_THR_MMH, zerovalue=-15.0)
    R_db[~np.isfinite(R_db)] = -15.0
    V = motion.get_method("LK")(R_db)                       # (2, ny, nx)

    coords = {"lead": np.arange(1, N_LEADS + 1) * TIMESTEP_MIN, "lat": frames.lat, "lon": frames.lon}
    if method == "extrapolation":
        R_f = nowcasts.get_method("extrapolation")(R[-1], V, N_LEADS)
        ds = xr.Dataset({"rain_mmh": (("lead", "lat", "lon"), np.nan_to_num(R_f))}, coords=coords)
    elif method == "steps":
        R_f_db = nowcasts.get_method("steps")(
            R_db[-3:], V, N_LEADS, n_ens_members=n_ens, n_cascade_levels=6,
            precip_thr=10 * np.log10(RAIN_THR_MMH), kmperpixel=KM_PER_PIXEL, timestep=TIMESTEP_MIN,
            noise_method="nonparametric", vel_pert_method="bps", mask_method="incremental", seed=seed)
        R_f = transformation.dB_transform(R_f_db, threshold=-10.0, inverse=True)[0]
        R_f = np.nan_to_num(R_f)                            # (ens, lead, ny, nx)
        exc = np.stack([ensemblestats.excprob(R_f, t) for t in THRESHOLDS_MMH])
        ds = xr.Dataset({
            "rain_mmh": (("lead", "lat", "lon"), R_f.mean(0)),
            "exc_prob": (("threshold", "lead", "lat", "lon"), exc),
        }, coords={**coords, "threshold": list(THRESHOLDS_MMH)})
    else:
        raise ValueError(method)
    ds["u"] = (("lat", "lon"), V[0])
    ds["v"] = (("lat", "lon"), V[1])
    ds.attrs.update(issue_time=str(frames.time.values[-1]), method=method, timestep_min=TIMESTEP_MIN)
    return ds


def persistence(frames: xr.DataArray) -> xr.Dataset:
    """Eulerian persistence: the last frame, unchanged. Your nowcast MUST beat this."""
    last = frames.isel(time=-1).values
    rain = np.repeat(last[None], N_LEADS, axis=0)
    return xr.Dataset({"rain_mmh": (("lead", "lat", "lon"), rain)},
                      coords={"lead": np.arange(1, N_LEADS + 1) * TIMESTEP_MIN, "lat": frames.lat, "lon": frames.lon})


def accumulate_mm(ds: xr.Dataset, hours: int) -> xr.DataArray:
    steps = hours * 60 // TIMESTEP_MIN
    return (ds["rain_mmh"].isel(lead=slice(0, steps)) * TIMESTEP_MIN / 60).sum("lead")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue-time", required=True)
    ap.add_argument("--method", choices=["extrapolation", "steps"], default="extrapolation")
    a = ap.parse_args()
    issue = datetime.fromisoformat(a.issue_time)
    ds = run_nowcast(load_frames(issue), a.method)
    out = PROCESSED / "forecasts" / issue.strftime("%Y%m%d%H%M") / f"nowcast_{a.method}.nc"
    out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out)
    print(ds, "\n->", out)
