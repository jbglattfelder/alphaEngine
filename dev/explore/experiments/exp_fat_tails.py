"""
exp_fat_tails.py — is the return distribution genuinely heavy-tailed?

Edit CSV / run.  Produces fat_tails.png (3 panels) + the numbers.

WHY THIS INSTRUMENT AND NOT "P(|r|>4sd)"
---------------------------------------
Three ways a naive tail number lies on this engine, all controlled for here:

1. ZERO-STEP INFLATION. 45-72% of ticks have no price change, and the fraction
   VARIES BY SEED. Zeros deflate sd, so the 4sd threshold moves and the
   exceedance fraction changes for reasons that have nothing to do with tails.
   -> the BM control is matched on zero-fraction AND nonzero-sd, not just length.
2. TREND. A trending price manufactures apparent tails. -> local rolling-median
   detrend; the residual sign-ACF must sit near 0.5 or the detrend is untrusted.
3. TICK GRANULARITY. A lattice at the tp band can look heavy at m=1 and vanish
   under aggregation. -> the tail is measured at m = 1, 5, 25, 125.

WHAT IT REPORTS
---------------
  panel 1  CCDF of |r|/sd, log-log: engine vs matched BM vs Gaussian.
           A straight line on log-log => power law; its slope is the tail index.
  panel 2  Hill estimator alpha_hat vs k (the top-k order statistics).
           A flat plateau is the index; no plateau means "heavy, but not a
           clean power law" -- report that honestly rather than a number.
  panel 3  tail survival under aggregation, engine and BM, as x-Gaussian.
           Real fat tails persist; tick artifacts collapse toward 1.

VALIDATION: run with CSV="" to self-test on pure BM. Every panel must show the
engine curve ON the BM curve (that is the null); anything else is the finding.
"""
import csv
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

CSV      = "price_feed.csv"   # feed with a p_int column.  Relative paths are
                              # resolved against THIS FILE, then the repo root,
                              # then the shell's cwd -- so it works whether the
                              # script lives in experiments/ or at the top level.
DETREND_W = 251               # rolling-median window (sweep 25..751 to check)
OUT      = "fat_tails.png"
SHOW     = False


# ---------- helpers ----------
def resolve(path):
    """Find the feed whether we were launched from the repo root or a subdir."""
    p = Path(path).expanduser()
    if p.is_absolute() and p.exists():
        return p
    here = Path(__file__).resolve().parent
    tried = [Path.cwd() / p, here / p, here.parent / p,
             here / Path(p).name, here.parent / Path(p).name]
    for c in tried:
        if c.exists():
            return c
    found = sorted({str(q) for d in (here, here.parent, Path.cwd())
                    for q in Path(d).glob("*.csv")})
    raise SystemExit(
        "could not find the feed.\n  looked in:\n    "
        + "\n    ".join(str(t) for t in tried)
        + ("\n  csv files I can see:\n    " + "\n    ".join(found) if found
           else "\n  no .csv files nearby -- run export_price.py or scaling_law.py first")
    )


def load(path):
    with open(resolve(path)) as f:
        rows = list(csv.DictReader(f))
    key = "p_int" if "p_int" in rows[0] else list(rows[0])[0]
    return np.array([float(r[key]) for r in rows])


def local_detrend(y, w):
    h = w // 2
    pad = np.pad(y, (h, w - h - 1), mode="edge")
    return y - np.median(swv(pad, w), axis=1)


def sign_acf1(r):
    nz = np.sign(r[np.abs(r) > 1e-12])
    return float(np.mean(nz[1:] == nz[:-1])) if len(nz) > 2 else np.nan


def matched_bm(r, rng):
    """BM increments matched on LENGTH, ZERO-FRACTION and NONZERO-SD."""
    zero = np.abs(r) <= 1e-12
    sd = r[~zero].std()
    out = rng.normal(0, sd, len(r))
    out[rng.permutation(len(r))[: zero.sum()]] = 0.0
    return out


def ccdf(x):
    x = np.sort(np.abs(x))[::-1]
    return x, np.arange(1, len(x) + 1) / len(x)


def hill(x, kmax=None):
    """Hill estimator of the tail index alpha over k = 20..kmax."""
    x = np.sort(np.abs(x))[::-1]
    x = x[x > 0]
    kmax = kmax or min(len(x) // 10, 4000)
    ks = np.unique(np.geomspace(20, max(21, kmax), 60).astype(int))
    a = [k / np.sum(np.log(x[:k] / x[k])) for k in ks if k < len(x)]
    return ks[: len(a)], np.array(a)


def tail_x_gauss(r, k=4.0):
    from math import erfc, sqrt
    r = r - r.mean()
    return float(np.mean(np.abs(r) > k * r.std())) / erfc(k / sqrt(2))


def agg(y, m):
    return y[m::m] - y[:-m:m]


# ---------- main ----------
def main(path=CSV):
    rng = np.random.default_rng(0)
    if path:
        p = load(path)
        y = np.log(p[np.isfinite(p) & (p > 0)])
        label = path
    else:                                   # BM self-test
        y = np.cumsum(rng.normal(0, 0.015, 150_000))
        y[rng.permutation(len(y))[: int(0.55 * len(y))]] = np.nan
        y = np.where(np.isnan(y), np.nan, y)
        s = np.copy(y)
        for i in range(1, len(s)):           # hold last price -> zero steps
            if np.isnan(s[i]):
                s[i] = s[i - 1]
        y = s
        label = "BM SELF-TEST"

    yd = local_detrend(y, DETREND_W)
    r = np.diff(yd)
    b = matched_bm(r, rng)

    zf = float(np.mean(np.abs(r) <= 1e-12))
    print(f"feed: {label}   {len(y):,} ticks")
    print(f"  zero-step fraction {zf:.1%}   nonzero sd {r[np.abs(r)>1e-12].std():.5f}")
    print(f"  residual sign-ACF  {sign_acf1(r):.3f}   (needs ~0.5: trend removed)")
    print(f"\n  P(|r|>k sd) as x-Gaussian, detrended:")
    print(f"    {'k':>3} {'engine':>10} {'matched BM':>12}")
    for k in (3, 4, 5):
        print(f"    {k:>3} {tail_x_gauss(r,k):>10.1f} {tail_x_gauss(b,k):>12.1f}")

    ks, al = hill(r)
    kb, ab = hill(b)
    lo, hi = int(len(al) * 0.35), int(len(al) * 0.8)
    print(f"\n  Hill index over the plateau: engine {np.median(al[lo:hi]):.2f}   "
          f"BM {np.median(ab[lo:hi]):.2f}   (BM has NO power-law tail; its "
          f"'index' rises with k)")

    print(f"\n  tail (x-Gaussian at 4sd) under aggregation:")
    print(f"    {'m':>5} {'engine':>10} {'matched BM':>12}")
    ms = (1, 5, 25, 125)
    eng_m, bm_m = [], []
    ybm = np.concatenate([[0.0], np.cumsum(b)])
    for m in ms:
        e_, b_ = tail_x_gauss(agg(yd, m)), tail_x_gauss(agg(ybm, m))
        eng_m.append(e_); bm_m.append(b_)
        print(f"    {m:>5} {e_:>10.1f} {b_:>12.1f}")

    _plot(r, b, ks, al, kb, ab, ms, eng_m, bm_m, label)


def _plot(r, b, ks, al, kb, ab, ms, eng_m, bm_m, label):
    import matplotlib
    if not SHOW:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from math import sqrt, erfc as _erfc
    erfc = np.vectorize(_erfc)          # no scipy dependency

    INK, ENG, BM, GAU = "#22262E", "#C0453A", "#2E9E8F", "#8A8F98"
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15.5, 5.0))
    fig.suptitle(f"Return tails  |  {label}  |  local detrend w={DETREND_W}",
                 fontsize=12, fontweight="bold")

    # --- 1. CCDF
    rs = r[np.abs(r) > 1e-12]; bs = b[np.abs(b) > 1e-12]
    for d, c, lb in ((rs, ENG, "engine"), (bs, BM, "matched BM")):
        x, f = ccdf(d / d.std())
        a1.loglog(x, f, "-", color=c, lw=1.9, label=lb)
    xg = np.geomspace(0.5, 12, 200)
    a1.loglog(xg, erfc(xg / sqrt(2)), ":", color=GAU, lw=1.6, label="Gaussian")
    a1.set_xlim(0.7, 15); a1.set_ylim(1e-5, 1.2)
    a1.set_xlabel("|r| / sd"); a1.set_ylabel("P(|R| > r)")
    a1.set_title("CCDF — straight line = power law", fontsize=10)
    a1.legend(fontsize=9); a1.grid(True, which="both", ls=":", alpha=.4)

    # --- 2. Hill
    a2.semilogx(ks, al, "-", color=ENG, lw=1.9, label="engine")
    a2.semilogx(kb, ab, "-", color=BM, lw=1.9, label="matched BM")
    a2.axhline(3.0, ls=":", color=GAU, lw=1.6, label="cubic law α=3")
    a2.set_ylim(0, 8); a2.set_xlabel("k  (top-k order statistics)")
    a2.set_ylabel(r"Hill $\hat\alpha$")
    a2.set_title("Hill index — flat plateau = the tail index", fontsize=10)
    a2.legend(fontsize=9); a2.grid(True, which="both", ls=":", alpha=.4)

    # --- 3. aggregation
    a3.semilogx(ms, eng_m, "o-", color=ENG, lw=1.9, ms=7, label="engine")
    a3.semilogx(ms, bm_m, "s-", color=BM, lw=1.9, ms=6, label="matched BM")
    a3.axhline(1.0, ls=":", color=GAU, lw=1.6, label="Gaussian")
    a3.set_yscale("log"); a3.set_xlabel("aggregation m (ticks)")
    a3.set_ylabel("P(|r|>4sd)  /  Gaussian")
    a3.set_title("survives aggregation? (artifact → 1)", fontsize=10)
    a3.legend(fontsize=9); a3.grid(True, which="both", ls=":", alpha=.4)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"\nwrote {OUT}")
    if SHOW:
        plt.show()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CSV)
