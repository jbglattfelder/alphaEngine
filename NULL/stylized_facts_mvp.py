"""
stylized_facts_mvp.py — the Cont (2001) stylized-facts scorecard for one
MVP run.

Edit the block below and press Run. It reuses the tagged price-feed CSV if
present (else runs the MVP engine and writes it), then tests the feed
against the classic facts:

  SF1 absence of linear autocorrelation : ACF(r) ~ 0 beyond lag ~1
  SF2 volatility clustering             : ACF(|r|) > 0, slow decay
  SF3 heavy tails                       : excess kurtosis >> 0 at tick scale
  SF4 aggregational gaussianity         : kurtosis falls under aggregation
  SF5 activity                          : fraction of zero-return ticks

Prints the scorecard and writes a three-panel figure, both named with the
config designator:
    price_btc_eur_<tag>.csv   (the feed, shared with simulation_mvp.py)
    stylized_facts_<tag>.png
"""

from __future__ import annotations

import os

import numpy as np

from simulation_mvp import Config, Simulation, cfg_tag
from dc_analysis import load_csv

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- edit these ----------------
N = 150          # agents per side
T = 100_000      # ticks
SEED = 9
CAPITAL_DIST = "pareto"   # block 2a: "pareto" | "normal"
BAND_DIST = "fixed"       # block 2b: "fixed"  | "normal"
CLOSING = "clock"         # block 2c: "clock"  | "normal"

REUSE_CSV = True    # True: skip the run if the tagged feed CSV already exists
SHOW = True         # pop the figure in the IDE (it saves either way)
# --------------------------------------------

CFG = Config(n=N, T=T, seed=SEED, capital_dist=CAPITAL_DIST,
             band_dist=BAND_DIST, closing=CLOSING)
TAG = cfg_tag(CFG)
CSV_PATH = os.path.join(HERE, f"price_btc_eur_{TAG}.csv")
OUT = os.path.join(HERE, f"stylized_facts_{TAG}.png")

LAGS_R = [1, 2, 3, 5, 10, 20]              # linear-ACF probe lags   (SF1)
LAGS_ABS = [1, 5, 10, 25, 50, 100, 250]    # |r|-ACF probe lags      (SF2)
AGG_M = [1, 5, 25, 125]                    # aggregation scales      (SF3/SF4)


def acf(x: np.ndarray, lags: list[int]) -> np.ndarray:
    """Sample autocorrelation of x at the given lags (biased normalisation
    by the lag-0 variance — the standard convention for ACF plots)."""
    x = x - x.mean()
    v = float((x * x).mean())
    if v == 0:
        return np.zeros(len(lags))
    out = []
    for L in lags:
        out.append(float((x[:-L] * x[L:]).mean()) / v)
    return np.array(out)


def excess_kurtosis(x: np.ndarray) -> float:
    """Excess kurtosis (Gaussian = 0). NaN for a degenerate series."""
    s = x.std()
    if s <= 0:
        return float("nan")
    return float(((x - x.mean()) ** 4).mean() / s ** 4 - 3.0)


def facts(prices: np.ndarray) -> dict:
    """All five stylized-fact measurements for one price series."""
    r = np.diff(np.log(prices))
    out = {}
    out["zero_frac"] = float((r == 0).mean())          # SF5
    out["sd"] = float(r.std())
    out["acf_r"] = acf(r, LAGS_R)                      # SF1
    out["acf_abs"] = acf(np.abs(r), LAGS_ABS)          # SF2
    out["kurt"] = {}                                   # SF3 + SF4
    for m in AGG_M:
        n = (len(r) // m) * m
        rm = r[:n].reshape(-1, m).sum(axis=1)
        out["kurt"][m] = excess_kurtosis(rm)
    return out


def report(F: dict) -> None:
    """Print the scorecard with the reference behaviour next to each fact."""
    ar, aa, k = F["acf_r"], F["acf_abs"], F["kurt"]
    print(f"\n=== stylized facts — {TAG} ===")
    print(f"  tick sd(r)          : {F['sd']:.4g}")
    print(f"  SF5 zero-return %   : {100 * F['zero_frac']:.1f}%   "
          f"(ticks where no trade moved the price)")
    print(f"  SF1 ACF(r)          : L1={ar[0]:+.3f}  L5={ar[3]:+.3f}  "
          f"L20={ar[5]:+.3f}   [fact: ~0 beyond lag ~1]")
    print(f"  SF2 ACF(|r|)        : L1={aa[0]:+.3f}  L10={aa[2]:+.3f}  "
          f"L100={aa[5]:+.3f}  L250={aa[6]:+.3f}   [fact: >0, slow decay]")
    print(f"  SF3 kurtosis (m=1)  : {k[1]:.1f}   [fact: >> 0 (Gaussian = 0)]")
    print(f"  SF4 kurtosis m=1->125: {k[1]:.1f} -> {k[5]:.1f} -> {k[25]:.1f} "
          f"-> {k[125]:.1f}   [fact: falls under aggregation]")


def plot(prices: np.ndarray, F: dict) -> None:
    """Three panels: ACF(r), ACF(|r|), kurtosis vs aggregation scale."""
    import matplotlib.pyplot as plt

    BLUE, ORANGE, GREY = "#2563EB", "#C2680A", "#9CA3AF"
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.4))
    fig.suptitle(f"Stylized facts (Cont 2001)  |  {TAG}  |  "
                 f"{len(prices):,} ticks", fontsize=11, fontweight="bold")

    # SF1 — linear ACF of returns: dies at lag 1 (no free lunch)
    a1.axhline(0, color=GREY, lw=0.8, ls=":")
    a1.plot(LAGS_R, F["acf_r"], "o-", color=BLUE)
    a1.set_title("SF1 — ACF of returns (fact: ~0 beyond lag ~1)", fontsize=9)
    a1.set_xlabel("lag (ticks)")
    a1.set_ylabel("ACF(r)")
    a1.grid(True, ls=":", alpha=0.4)

    # SF2 — ACF of |returns|: positive and slow to decay (clustering)
    a2.axhline(0, color=GREY, lw=0.8, ls=":")
    a2.semilogx(LAGS_ABS, F["acf_abs"], "o-", color=ORANGE)
    a2.set_title("SF2 — ACF of |returns| (fact: >0, slow decay)", fontsize=9)
    a2.set_xlabel("lag (ticks, log)")
    a2.set_ylabel("ACF(|r|)")
    a2.grid(True, which="both", ls=":", alpha=0.4)

    # SF3/SF4 — excess kurtosis vs aggregation: fat at tick scale, falls
    ms = list(F["kurt"].keys())
    ks = [F["kurt"][m] for m in ms]
    a3.axhline(0, color=GREY, lw=0.8, ls=":", label="Gaussian (0)")
    a3.semilogx(ms, ks, "o-", color="#15803D")
    a3.set_title("SF3/SF4 — excess kurtosis vs aggregation "
                 "(fact: >>0, then falls)", fontsize=9)
    a3.set_xlabel("aggregation m (ticks per return, log)")
    a3.set_ylabel("excess kurtosis")
    a3.legend(fontsize=8)
    a3.grid(True, which="both", ls=":", alpha=0.4)

    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"\nwrote {OUT}")
    if SHOW:
        plt.show()
    else:
        plt.close(fig)


def main() -> None:
    if REUSE_CSV and os.path.exists(CSV_PATH):
        print(f"reusing existing {CSV_PATH} (set REUSE_CSV=False to re-run)")
    else:
        print(CFG.summary())
        sim = Simulation(CFG).run()
        print(sim.summary())
        sim.write_price_csv(CSV_PATH)
        print(f"wrote {CSV_PATH} ({len(sim.rec_price):,} rows)")

    prices = load_csv(CSV_PATH, "BTC/EUR")
    if len(prices) != T:
        print(f"WARNING: feed has {len(prices):,} rows but T={T:,} — a stale CSV "
              f"under the same tag? Set REUSE_CSV=False to rebuild it.")
    prices = prices[np.isfinite(prices) & (prices > 0)]
    F = facts(prices)
    report(F)
    plot(prices, F)


if __name__ == "__main__":
    main()
