"""
plots_from_tape.py — build the event-time figures from a saved tape,
in a separate lean process, so big runs never OOM in the plot step.

Produces, next to the tape:
    scaling_laws_event_<tag>.png     (with the dust-median mask)
    stylized_facts_event_<tag>.png

Usage:
    python helper/plots_from_tape.py eval/runs/tape_<tag>_events.npz

Memory: loads only the print series (~16 bytes/print); the GC is
disabled during the array work. A 40M-print tape needs ~1.5 GB peak,
where the in-run plot step needed the whole simulation besides.
"""

from __future__ import annotations

import gc
import os
import sys

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scaling_law_mvp import analyse_scaling  # noqa: E402


def _acf(x: np.ndarray, lag: int) -> float:
    a, b = x[:-lag], x[lag:]
    return float(((a - a.mean()) * (b - b.mean())).mean()
                 / (a.std() * b.std()))


def plot_scaling(p: np.ndarray, tag: str, out_dir: str) -> str:
    res = analyse_scaling(p, trunc_frac=0.125)
    D, NDC, OS, OSM = res["D"], res["NDC"], res["OS"], res["OSM"]
    xs = np.array([D.min(), D.max()])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle(f"Intrinsic-time scaling laws  |  {tag}  |  EVENT time "
                 f"({len(p):,} prints)  |  sd(r)={res['sd']:.3g}",
                 fontsize=10, fontweight="bold")
    a1.loglog(D, NDC, "o", ms=6, color="#2563EB", label="measured")
    a1.loglog(xs, (xs / res["C_N"]) ** res["E_N"], "-", color="#B45309",
              lw=1.6, label=f"fit: E = {res['E_N']:.3f}  (R²={res['R_N']:.3f})")
    a1.loglog(xs, NDC[0] * (xs / D[0]) ** -2.0, ":", color="#6B7280",
              lw=1.4, label="theory: E = -2 (BM)")
    a1.set_xlabel("directional-change threshold  δ")
    a1.set_ylabel("N(δ)   number of directional changes")
    a1.set_title("Law (0b): DC count  →  VOLATILITY", fontsize=10)
    a1.legend(fontsize=8)
    a1.grid(True, which="both", ls=":", alpha=0.4)
    a2.loglog(D, OS, "o", ms=6, color="#15803D",
              label=f"mean  (⟨ω⟩/δ={res['ratio']:.2f})")
    med_ok = OSM > 0.02 * D
    n_dust = int((~med_ok).sum())
    a2.loglog(D[med_ok], OSM[med_ok], "s", ms=5, color="#2563EB", mfc="none",
              label=f"median  (/δ={res['ratio_med']:.2f}, drift-robust)"
                    + (f"; {n_dust} pts ≈ 0 off-scale" if n_dust else ""))
    a2.loglog(xs, (xs / res["C_os"]) ** res["E_os"], "-", color="#B45309",
              lw=1.6,
              label=f"mean fit: E = {res['E_os']:.3f}  (R²={res['R_os']:.3f})")
    a2.loglog(xs, xs, ":", color="#6B7280", lw=1.4,
              label="theory: ⟨ω⟩ = δ  (BM/FX)")
    a2.set_xlabel("directional-change threshold  δ")
    a2.set_ylabel("⟨ω(δ)⟩   mean overshoot")
    a2.set_title(f"Law (9,os): overshoot  →  LIQUIDITY   "
                 f"(mean/δ={res['ratio']:.2f}  median/δ={res['ratio_med']:.2f})",
                 fontsize=9)
    a2.legend(fontsize=8)
    a2.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = os.path.join(out_dir, f"scaling_laws_event_{tag}.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_facts(p: np.ndarray, prints_per_tick: int, tag: str,
               out_dir: str) -> str:
    r = np.diff(np.log(p))
    r = r[np.isfinite(r)]
    n = len(r)
    lags_r = (1, 2, 3, 5, 10, 20)
    acf_r = [_acf(r, k) for k in lags_r]
    ab = np.abs(r)
    lags_abs = (1, 5, 10, 25, 50, 100, 250)
    acf_ab = [_acf(ab, k) for k in lags_abs]
    del ab
    ms = sorted({1, 5, 25, max(prints_per_tick, 2)})
    kurts = []
    for m in ms:
        x = r[:n - (n % m)].reshape(-1, m).sum(axis=1)
        x = x - x.mean()
        kurts.append(float((x**4).mean() / (x**2).mean() ** 2 - 3))
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(16, 4.4))
    fig.suptitle(f"Stylized facts (Cont 2001)  |  {tag}  [event time]  |  "
                 f"{n + 1:,} prints", fontsize=11)
    a1.plot(lags_r, acf_r, "o-", color="#2563EB")
    a1.axhline(0, color="#9CA3AF", ls=":", lw=0.8)
    a1.set_title("SF1 — ACF of returns (fact: ~0 beyond lag ~1)", fontsize=9)
    a1.set_xlabel("lag (prints)")
    a1.set_ylabel("ACF(r)")
    a2.semilogx(lags_abs, acf_ab, "o-", color="#B45309")
    a2.axhline(0, color="#9CA3AF", ls=":", lw=0.8)
    a2.set_title("SF2 — ACF of |returns| (fact: >0, slow decay)", fontsize=9)
    a2.set_xlabel("lag (prints, log)")
    a2.set_ylabel("ACF(|r|)")
    a3.semilogx(ms, kurts, "o-", color="#15803D")
    a3.axhline(0, color="#9CA3AF", ls="--", lw=0.8, label="Gaussian (0)")
    a3.set_title("SF3/SF4 — excess kurtosis vs aggregation "
                 "(fact: >>0, then falls)", fontsize=9)
    a3.set_xlabel("aggregation m (prints per return, log; last ≈ one tick)")
    a3.set_ylabel("excess kurtosis")
    a3.legend(fontsize=8)
    for ax in (a1, a2, a3):
        ax.grid(True, ls=":", alpha=0.35)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    out = os.path.join(out_dir, f"stylized_facts_event_{tag}.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def main(path: str) -> None:
    base = os.path.basename(path)
    if not base.endswith("_events.npz"):
        raise SystemExit("expected a *_events.npz tape")
    tag = base[len("tape_"):-len("_events.npz")]
    out_dir = os.path.dirname(os.path.abspath(path))
    gc.disable()
    ev = np.load(path)
    p = np.asarray(ev["p"], np.float64)
    t = np.asarray(ev["t"])
    p = p[np.isfinite(p) & (p > 0)]
    ppt = max(int(round(len(p) / max(int(t[-1]), 1))), 1)
    del ev, t
    print(f"{len(p):,} prints (~{ppt}/tick)")
    print("wrote", plot_scaling(p, tag, out_dir))
    print("wrote", plot_facts(p, ppt, tag, out_dir))


if __name__ == "__main__":
    main(sys.argv[1])
