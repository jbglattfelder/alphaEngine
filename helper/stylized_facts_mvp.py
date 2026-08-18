"""
stylized_facts_mvp.py — the Cont (2001) stylized-facts scorecard for an
MVP run.

Called from simulation_mvp.py's run block exactly like the dashboard:

    from stylized_facts_mvp import plot_stylized_facts
    plot_stylized_facts(sim, save_path=..., show=SHOW)

Facts tested on the run's emergent price:
  SF1 absence of linear autocorrelation : ACF(r) ~ 0 beyond lag ~1
  SF2 volatility clustering             : ACF(|r|) > 0, slow decay
  SF3 heavy tails                       : excess kurtosis >> 0 at tick scale
  SF4 aggregational gaussianity         : kurtosis falls under aggregation
  SF5 activity                          : fraction of zero-return ticks

Prints the scorecard and writes a three-panel figure.

Standalone use: running this file analyses the default config's tagged
price CSV if it exists (instant), else runs the default config first.
"""

from __future__ import annotations

import os

import numpy as np

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


def compute_facts(prices: np.ndarray) -> dict:
    """All five stylized-fact measurements for one price series."""
    prices = np.asarray(prices, float)
    prices = prices[np.isfinite(prices) & (prices > 0)]
    r = np.diff(np.log(prices))
    out = {"n_ticks": len(prices)}
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


def report_facts(F: dict, tag: str) -> None:
    """Print the scorecard with the reference behaviour next to each fact."""
    ar, aa, k = F["acf_r"], F["acf_abs"], F["kurt"]
    print(f"\n=== stylized facts — {tag} ===")
    print(f"  tick sd(r)           : {F['sd']:.4g}")
    print(f"  SF5 zero-return %    : {100 * F['zero_frac']:.1f}%   "
          f"(ticks where no trade moved the price)")
    print(f"  SF1 ACF(r)           : L1={ar[0]:+.3f}  L5={ar[3]:+.3f}  "
          f"L20={ar[5]:+.3f}   [fact: ~0 beyond lag ~1]")
    print(f"  SF2 ACF(|r|)         : L1={aa[0]:+.3f}  L10={aa[2]:+.3f}  "
          f"L100={aa[5]:+.3f}  L250={aa[6]:+.3f}   [fact: >0, slow decay]")
    print(f"  SF3 kurtosis (m=1)   : {k[1]:.1f}   [fact: >> 0 (Gaussian = 0)]")
    print(f"  SF4 kurtosis m=1->125: {k[1]:.1f} -> {k[5]:.1f} -> "
          f"{k[25]:.1f} -> {k[125]:.1f}   [fact: falls under aggregation]")


def plot_stylized_facts(sim, save_path: str = None, show: bool = False,
                        time_base: str = "tick") -> str:
    """The run-block entry point (mirrors plot_dashboard's shape): measure
    the five facts on the finished simulation's price series, print the
    scorecard, save the three-panel figure, and pop it when show=True.

    time_base="tick"  : the recorded per-tick series (last print per tick).
    time_base="event" : the trade tape, one price per print (wicks kept).
    In event time, lags count PRINTS and SF5's zero-returns are consecutive
    prints at the same level (several makers at one price)."""
    import matplotlib.pyplot as plt
    from simulation_mvp import cfg_tag

    tag = cfg_tag(sim.cfg)
    if time_base == "event":
        if not getattr(sim, "trades_log", None):
            raise SystemExit("time_base='event' needs sim.trades_log "
                             "(a finished Simulation, not a CSV shim)")
        from scaling_law_mvp import event_prices
        prices = event_prices(sim)
        tag = tag + " [event time]"
        if save_path is None:
            save_path = f"stylized_facts_event_{cfg_tag(sim.cfg)}.png"
    else:
        prices = np.asarray(sim.rec_price)
        if save_path is None:
            save_path = f"stylized_facts_{tag}.png"
    F = compute_facts(prices)
    report_facts(F, tag)

    BLUE, ORANGE, GREY = "#2563EB", "#C2680A", "#9CA3AF"
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.4))
    fig.suptitle(f"Stylized facts (Cont 2001)  |  {tag}  |  "
                 f"{F['n_ticks']:,} ticks", fontsize=11, fontweight="bold")

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
    fig.savefig(save_path, dpi=140, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()          # pops the IDE window; returns when it is closed
    else:
        plt.close(fig)
    return save_path


if __name__ == "__main__":
    # standalone convenience: analyse the DEFAULT config. Reuses its tagged
    # price CSV when present (instant), else runs the engine first.
    from dc_analysis import load_csv
    from simulation_mvp import Config, Simulation, cfg_tag
    from scaling_law_mvp import _FeedShim

    HERE = os.path.dirname(os.path.abspath(__file__))
    cfg = Config()
    tag = cfg_tag(cfg)
    csv_path = os.path.join(HERE, f"price_btc_eur_{tag}.csv")
    out_png = os.path.join(HERE, f"stylized_facts_{tag}.png")
    if os.path.exists(csv_path):
        print(f"reusing {csv_path}")
        prices = load_csv(csv_path, "BTC/EUR")
        if len(prices) != cfg.T:
            print(f"WARNING: feed has {len(prices):,} rows but T={cfg.T:,} — "
                  f"stale CSV under the same tag? Delete it to rebuild.")
        plot_stylized_facts(_FeedShim(cfg, prices), save_path=out_png, show=True)
    else:
        sim = Simulation(cfg).run()
        print(sim.summary())
        sim.write_price_csv(csv_path)
        plot_stylized_facts(sim, save_path=out_png, show=True)
