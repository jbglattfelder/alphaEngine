"""
exp_clustering.py — is there volatility clustering, and WHERE does it live?

Edit CSV / run.  Writes clustering.png + the numbers.

THE TRAP THIS INSTRUMENT EXISTS TO AVOID
----------------------------------------
40-72% of ticks on this engine have NO price change, and the fraction varies by
seed. So ACF(|r|) computed over all steps mixes two different phenomena:

  * VOLATILITY clustering — big moves follow big moves (magnitudes cluster)
  * ACTIVITY  clustering — trades bunch in time (the ZEROS cluster)

Measured separately on the frozen default they behave completely differently:
magnitude clustering is strong but SHORT-range (dead by lag ~5-20), while the
long memory (still 0.3 at lag 500) is entirely ACTIVITY. Reporting only
"ACF(|r|) all steps" reads as long-memory volatility clustering and is wrong.

Under subordination the two are the same object seen from opposite sides — a
clustered trade-arrival clock IS clustered volatility — but they are different
CLAIMS and the docs must say which one is measured.

CONTROLS (both required)
------------------------
  shuffled   same marginal distribution, time order destroyed -> isolates
             dependence from the heavy marginal. Must sit inside the noise band.
  matched BM Gaussian increments matched on LENGTH, ZERO-FRACTION and
             NONZERO-SD -> the zero structure alone must not produce clustering.

NOISE BAND: +-2/sqrt(N). An ACF value inside it is nothing. The script prints
the band and marks every lag that fails it, because at long lags on a short feed
the estimate is worthless — the sibling failure to counting 1 exceedance and
calling it a tail (see exp_fat_tails.py).
"""
import csv
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

CSV       = "price_feed.csv"
DETREND_W = 251
LAGS      = np.unique(np.geomspace(1, 1000, 40).astype(int))
OUT       = "clustering.png"
SHOW      = False


def resolve(path):
    p = Path(path).expanduser()
    if p.is_absolute() and p.exists():
        return p
    here = Path(__file__).resolve().parent
    for c in (Path.cwd() / p, here / p, here.parent / p,
              here / p.name, here.parent / p.name):
        if c.exists():
            return c
    raise SystemExit(f"feed not found: {path}")


def load(path):
    with open(resolve(path)) as f:
        rows = list(csv.DictReader(f))
    key = "p_int" if "p_int" in rows[0] else list(rows[0])[0]
    return np.array([float(r[key]) for r in rows])


def local_detrend(y, w):
    h = w // 2
    return y - np.median(swv(np.pad(y, (h, w - h - 1), mode="edge"), w), axis=1)


def acf(x, lags):
    x = np.asarray(x, float) - np.mean(x)
    d = np.dot(x, x)
    return np.array([np.dot(x[:-L], x[L:]) / d for L in lags])


def decay_exponent(lags, a, band):
    """Fit ACF ~ lag^-beta over the lags where the ACF clears the noise band."""
    m = (a > band) & (lags >= 2)
    if m.sum() < 4:
        return np.nan, 0
    b, _ = np.polyfit(np.log(lags[m]), np.log(a[m]), 1)
    return -b, int(m.sum())


def main(path=CSV):
    rng = np.random.default_rng(0)
    p = load(path)
    y = np.log(p[np.isfinite(p) & (p > 0)])
    yd = local_detrend(y, DETREND_W)
    r = np.diff(yd)
    N = len(r)
    band = 2.0 / np.sqrt(N)

    zero = np.abs(r) <= 1e-12
    mags = np.abs(r[~zero])
    zind = zero.astype(float)

    bm = rng.normal(0, r[~zero].std(), N)
    bm[rng.permutation(N)[: zero.sum()]] = 0.0

    series = {
        "|r| all steps":      np.abs(r),
        "|r| NONZERO only":   mags,          # volatility clustering proper
        "zero-ind (activity)": zind,          # activity clustering
        "matched BM |r|":     np.abs(bm),
    }

    print(f"feed {path}   {N:,} steps   zero-fraction {zero.mean():.1%}")
    print(f"noise band ±2/√N = ±{band:.4f}   (anything inside it is NOTHING)\n")
    show = [1, 2, 5, 10, 20, 50, 100, 250, 500, 1000]
    print(f"{'series':>21} " + "".join(f"{('L'+str(l)):>8}" for l in show))
    res = {}
    for nm, v in series.items():
        a = acf(v, LAGS)
        res[nm] = a
        sub = [a[list(LAGS).index(min(LAGS, key=lambda z: abs(z - l)))] for l in show]
        print(f"{nm:>21} " + "".join(
            (f"{x:>8.3f}" if abs(x) > band else f"{'·':>8}") for x in sub))
        sh = acf(rng.permutation(v), LAGS)
        res[nm + " [shuffled]"] = sh
    print(f"\n(· = inside the noise band)")

    print(f"\n{'series':>21} {'ACF decay β':>12} {'lags used':>10}   ACF~lag^-β")
    for nm in ("|r| NONZERO only", "zero-ind (activity)", "|r| all steps"):
        b, k = decay_exponent(LAGS, res[nm], band)
        print(f"{nm:>21} {b:>12.2f} {k:>10}")

    print("\nREAD:")
    print("  |r| NONZERO only  -> VOLATILITY clustering (the real claim)")
    print("  zero-ind          -> ACTIVITY clustering (trades bunch in time)")
    print("  matched BM        -> must be flat; if not, the zero structure is doing it")
    print("  β ≈ 0.2-0.4 in real markets (slow power-law decay = long memory)")

    _plot(LAGS, res, band, path)


def _plot(lags, res, band, label):
    import matplotlib
    if not SHOW:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    C = {"|r| NONZERO only": "#C0453A", "zero-ind (activity)": "#E8A33D",
         "|r| all steps": "#22262E", "matched BM |r|": "#2E9E8F"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5.2))
    fig.suptitle(f"Clustering  |  {label}  |  detrend w={DETREND_W}",
                 fontsize=12, fontweight="bold")

    for nm, c in C.items():
        a1.plot(lags, res[nm], "-", color=c, lw=1.9, label=nm)
    a1.axhspan(-band, band, color="#8A8F98", alpha=.18, label="noise band ±2/√N")
    a1.axhline(0, color="#8A8F98", lw=.8)
    a1.set_xscale("log"); a1.set_xlabel("lag"); a1.set_ylabel("ACF")
    a1.set_title("where does the memory live?", fontsize=10)
    a1.legend(fontsize=8); a1.grid(True, which="both", ls=":", alpha=.4)

    for nm, c in C.items():
        v = np.clip(res[nm], 1e-4, None)
        a2.loglog(lags, v, "-", color=c, lw=1.9, label=nm)
        sh = res.get(nm + " [shuffled]")
        if sh is not None:
            a2.loglog(lags, np.clip(np.abs(sh), 1e-4, None), ":", color=c, lw=1.0,
                      alpha=.7)
    a2.axhline(band, color="#8A8F98", ls="--", lw=1.2, label="noise band")
    a2.set_xlabel("lag"); a2.set_ylabel("ACF (log)")
    a2.set_title("power-law decay? (dotted = shuffled control)", fontsize=10)
    a2.legend(fontsize=8); a2.grid(True, which="both", ls=":", alpha=.4)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"\nwrote {OUT}")
    if SHOW:
        plt.show()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CSV)
