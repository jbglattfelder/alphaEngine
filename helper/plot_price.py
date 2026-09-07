#!/usr/bin/env python3
"""Price-curve figure from a tick tape — no simulation, no sim state needed.

Usage:
    python helper/plot_price.py tape_<tag>.npy [more tapes ...]

One PNG per tape (price_<tag>.png, next to the tape): the price curve in
EUR per BTC on top, the same curve in log units below (so up- and
down-excursions read symmetrically), with start/min/max/final annotated.
Accepts any number of tapes and overlays nothing — one figure each.
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_one(path: str) -> str:
    p = np.load(path)
    if p.ndim != 1 or not np.issubdtype(p.dtype, np.floating):
        raise SystemExit(f"{path}: not a tick tape (expected a 1-D float array; "
                         f"got {p.dtype}, shape {p.shape}). Events/book tapes "
                         f"are .npz — this tool reads the plain .npy price tape.")
    x0 = float(p[0])
    lnp = np.log(p / x0)
    t = np.arange(len(p))

    fig, (ax, axl) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                  height_ratios=(3, 2))
    tag = os.path.basename(path).removeprefix("tape_").removesuffix(".npy")
    fig.suptitle(f"Emergent price — {tag}", fontsize=11, fontweight="bold")

    ax.plot(t, p, lw=0.6, color="#1f77b4")
    ax.axhline(x0, color="gray", ls=":", lw=0.8)
    ax.set_ylabel("price (EUR per BTC)")
    ax.grid(True, ls=":", alpha=0.3)

    imin, imax = int(p.argmin()), int(p.argmax())
    for i, label, va in ((imin, f"min {p[imin]:.2f}", "top"),
                         (imax, f"max {p[imax]:.2f}", "bottom")):
        ax.annotate(f"{label} @ {i:,}", (i, p[i]), fontsize=8,
                    textcoords="offset points",
                    xytext=(4, -10 if va == "top" else 10), color="#444444")
    ax.set_title(f"start {x0:.2f}   final {p[-1]:.2f}   "
                 f"ln(final/start) = {lnp[-1]:+.3f}", fontsize=9)

    axl.plot(t, lnp, lw=0.6, color="#9467bd")
    axl.axhline(0.0, color="gray", ls=":", lw=0.8)
    axl.set_ylabel("ln(p / x0)")
    axl.set_xlabel("tick")
    axl.grid(True, ls=":", alpha=0.3)

    out = os.path.join(os.path.dirname(path) or ".", f"price_{tag}.png")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    for path in argv:
        print("wrote", plot_one(path))


if __name__ == "__main__":
    main(sys.argv[1:])
