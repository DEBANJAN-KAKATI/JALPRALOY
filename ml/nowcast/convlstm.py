"""Engine 1 upgrade: a ConvLSTM encoder–forecaster trained on IMERG sequences.

Train on Colab/Kaggle GPU:
    python -m ml.nowcast.convlstm --epochs 30 --train-years 2015-2021 --val-year 2024

Input: 4 past frames (t-90..t, 30-min) of rain in mm/h, cropped to NOWCAST_BBOX.
Output: 12 future frames (6 h).
Beat pySTEPS AND persistence on CSI@{1,5,10} mm/h and FSS before you swap it in.

Deep nowcasts blur heavy cores (MSE rewards hedging). Counter it with the
intensity-weighted loss below; consider adding a U-Net baseline (often as good and
simpler) and, later, a GAN or diffusion refinement.
"""
from __future__ import annotations

import argparse

import numpy as np

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pip install torch (see environment.yml note)") from exc


class ConvLSTMCell(nn.Module):
    def __init__(self, in_ch: int, hid_ch: int, k: int = 3):
        super().__init__()
        self.hid_ch = hid_ch
        self.conv = nn.Conv2d(in_ch + hid_ch, 4 * hid_ch, k, padding=k // 2)

    def forward(self, x, state):
        h, c = state
        i, f, o, g = torch.chunk(self.conv(torch.cat([x, h], 1)), 4, dim=1)
        c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
        h = torch.sigmoid(o) * torch.tanh(c)
        return h, c


class Nowcaster(nn.Module):
    """Downsample ×4 -> 2-layer ConvLSTM over inputs -> roll forward -> upsample."""

    def __init__(self, hid: int = 64, n_out: int = 12):
        super().__init__()
        self.n_out = n_out
        self.enc = nn.Sequential(nn.Conv2d(1, 32, 3, 2, 1), nn.ReLU(), nn.Conv2d(32, hid, 3, 2, 1), nn.ReLU())
        self.l1 = ConvLSTMCell(hid, hid)
        self.l2 = ConvLSTMCell(hid, hid)
        self.dec = nn.Sequential(nn.ConvTranspose2d(hid, 32, 4, 2, 1), nn.ReLU(),
                                 nn.ConvTranspose2d(32, 1, 4, 2, 1))

    def forward(self, x):  # x: (B, T_in, H, W), H and W divisible by 4
        b, t, hgt, wid = x.shape
        z0 = self.enc(x[:, :1])
        s1 = s2 = (torch.zeros_like(z0), torch.zeros_like(z0))
        for k in range(t):
            z = self.enc(x[:, k:k + 1])
            s1 = self.l1(z, s1)
            s2 = self.l2(s1[0], s2)
        outs, z = [], s2[0]
        for _ in range(self.n_out):
            s1 = self.l1(z, s1)
            s2 = self.l2(s1[0], s2)
            z = s2[0]
            outs.append(torch.relu(self.dec(z)))
        return torch.cat(outs, 1)  # (B, n_out, H, W) in transformed units


def transform(mm_h):   # compress the heavy tail for training
    return np.log1p(mm_h)


def inverse(x):
    return np.expm1(x)


def weighted_mse(pred, target):
    """Balanced MSE (after Shi et al. 2017): heavy rain pixels weigh more."""
    mm = torch.expm1(target)
    w = torch.ones_like(mm)
    for thr, weight in ((2, 2.0), (5, 5.0), (10, 10.0), (30, 30.0)):
        w = torch.where(mm >= thr, torch.full_like(w, weight), w)
    return torch.mean(w * (pred - target) ** 2)


class SequenceDataset(torch.utils.data.Dataset):
    """Sliding windows over the IMERG zarr. Keep only samples with meaningful rain
    (e.g. >5 % pixels > 1 mm/h) or the model learns to predict "dry"."""

    def __init__(self, array: np.ndarray, n_in: int = 4, n_out: int = 12, min_wet: float = 0.05):
        self.x = transform(array.astype(np.float32))
        self.n_in, self.n_out = n_in, n_out
        span = n_in + n_out
        wet = (array > 1.0).mean(axis=(1, 2))
        self.starts = [i for i in range(len(array) - span) if wet[i + n_in - 1] >= min_wet]

    def __len__(self):
        return len(self.starts)

    def __getitem__(self, i):
        s = self.starts[i]
        seq = self.x[s:s + self.n_in + self.n_out]
        return torch.from_numpy(seq[:self.n_in]), torch.from_numpy(seq[self.n_in:])


def train(model, train_dl, val_dl, epochs: int, lr: float = 1e-3, device: str = "cuda"):
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    best = float("inf")
    for ep in range(epochs):
        model.train()
        for xb, yb in train_dl:
            xb, yb = xb.to(device), yb.to(device)
            loss = weighted_mse(model(xb), yb)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            val = np.mean([weighted_mse(model(x.to(device)), y.to(device)).item() for x, y in val_dl])
        print(f"epoch {ep}: val {val:.4f}")
        if val < best:
            best = val
            torch.save(model.state_dict(), "convlstm_best.pt")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    a = ap.parse_args()
    # TODO: load imerg.zarr -> crop to a size divisible by 4 -> split by YEAR -> DataLoaders -> train()
    raise SystemExit("Wire up data loading (see docs/ENGINE_1_NOWCAST.md, step 6)")
