"""
scaling_law_mvp.py — intrinsic-time scaling laws for an MVP run.

Called from simulation_mvp.py's run block exactly like the dashboard:

    from scaling_law_mvp import plot_scaling_laws
    plot_scaling_laws(sim, save_path=..., show=SHOW)

It dissects the run's emergent price into directional changes / overshoots
and plots the two laws log-log:
    LEFT   N(delta) vs delta        — DC count       -> VOLATILITY proxy
    RIGHT  <omega(delta)> vs delta  — mean overshoot -> LIQUIDITY proxy

Algorithm and definitions live in dc_analysis.py (Glattfelder-Dupuis-Olsen
2011, arXiv:0809.1040 alg. 2; Glattfelder-Golub 2022, arXiv:2204.02682).
Reference behaviour, verified there on Brownian motion:
    N(delta) ~ delta^-2       (BM measured -1.85 at a clean delta floor)
    <omega(delta)> ~= delta   (BM measured ratio 1.003)

DELTA FLOOR: thresholds are set relative to the feed's OWN tick volatility,
not in absolute %, because this engine's per-tick sd is ~0.85*tp (the TP/SL
band sets the tick volatility). Below ~8x tick-sd a single tick jumps the
threshold and biases <omega> upward.

Standalone use: running this file analyses the default config's tagged
price CSV if it exists (instant), else runs the default config first.
"""

from __future__ import annotations

import os

from typing import Optional

import numpy as np

from dc_analysis import measure, fit

# delta-grid defaults (overridable per call)
DELTA_LO_MULT = 8.0   # grid floor, in units of the feed's robust tick sd
DELTA_HI_MULT = 40.0  # ceiling; raise for longer feeds, lower if thresholds drop
N_DELTAS = 20
MIN_EVENTS = 12       # drop a threshold with fewer DC events (nothing to average)


def robust_tick_sd(prices: np.ndarray) -> float:
    """The feed's typical per-tick volatility, MAD-robust.

    Two hard-won guards: (1) SIGNIFICANCE FLOOR — dense markets print many
    essentially-unchanged prices whose float-dust returns (~1e-15) are
    NONZERO and can drive the MAD to machine epsilon, collapsing the delta
    grid; anything below 1e-9 is bookkeeping, not a move. (2) ROBUST SCALE —
    one flash event inflates np.std by orders of magnitude and pushes the
    grid above the feed's typical volatility ("0 usable thresholds"); the
    MAD tracks the TYPICAL tick and leaves the flash measurable as DC
    events instead of silently recalibrating the ruler."""
    r1 = np.diff(prices) / prices[:-1]
    r_fin = r1[np.isfinite(r1)]
    r_nz = r_fin[np.abs(r_fin) > 1e-9]
    sd_raw = float(np.std(r_fin))
    if len(r_nz):
        sd = float(1.4826 * np.median(np.abs(r_nz - np.median(r_nz))))
        med_abs = float(np.median(np.abs(r_nz)))
        if sd < 0.25 * med_abs:
            # LATTICE DEGENERACY guard: a tiny-n market bounces between a
            # few book levels, so the nonzero returns are near-IDENTICAL
            # floats and their MAD collapses to machine epsilon — a broken
            # ruler. The typical |move| itself is the honest scale then.
            print(f"NOTE: MAD scale {sd:.3g} is degenerate (identical "
                  f"lattice returns); using median |r| = {med_abs:.4g} "
                  f"as the tick scale instead.")
            sd = med_abs
    else:
        sd = sd_raw
    if sd == 0.0:
        sd = sd_raw
    if sd_raw > 3 * sd:
        print(f"NOTE: raw sd(r) = {sd_raw:.4g} is {sd_raw / sd:.1f}x the robust "
              f"(MAD) scale {sd:.4g} — flash/regime events present; the delta "
              f"grid uses the robust scale.")
    return sd


def analyse_scaling(prices: np.ndarray,
                    delta_lo_mult: float = DELTA_LO_MULT,
                    delta_hi_mult: float = DELTA_HI_MULT,
                    n_deltas: int = N_DELTAS,
                    min_events: int = MIN_EVENTS) -> dict:
    """Measure the two laws on a price series. Returns everything the plot
    and the report need: the usable delta grid, DC counts, overshoot means
    and medians, the log-log fits, and the overshoot/delta ratios."""
    prices = np.asarray(prices, float)
    prices = prices[np.isfinite(prices) & (prices > 0)]
    n_t = len(prices)
    sd = robust_tick_sd(prices)

    deltas = np.exp(np.linspace(np.log(delta_lo_mult * sd),
                                np.log(delta_hi_mult * sd), n_deltas))
    rows = []
    for d in deltas:
        m = measure(prices, float(d), n_t, min_events)
        if m is not None:
            rows.append(m)
    if len(rows) < 3:
        # count RAW DC events at the grid floor so the error names the true
        # cause: a near-monotone path (e.g. an n=2 TP-ladder ratchet, or the
        # locked sawtooth's long ramps) has no reversals at these scales —
        # that is a property of the feed, not a bug in the grid
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # a bare probe (min_events=1) may
            probe = measure(prices, float(deltas[0]), n_t, 1)  # average nothing
        n_floor = probe["N"] if probe else 0
        raise RuntimeError(
            f"only {len(rows)} usable thresholds (need 3): {n_t:,} ticks, "
            f"robust sd {sd:.4g}, grid {deltas[0]*100:.2f}%–"
            f"{deltas[-1]*100:.2f}%, DC events at the grid floor: {n_floor} "
            f"(each threshold needs >= {min_events}). The path has too few "
            f"reversals at these scales — near-monotone feeds (tiny n, "
            f"locked sawtooth ramps) have no intrinsic-time structure here. "
            f"Lower delta_lo_mult, lengthen T, or skip this analysis.")

    D = np.array([r["delta"] for r in rows])
    NDC = np.array([r["N"] for r in rows], float)
    OS = np.array([r["os_mean"] for r in rows])
    OSM = np.array([r["os_median"] for r in rows])
    E_N, C_N, R_N = fit(D, NDC)
    E_os, C_os, R_os = fit(D, OS)

    return {
        "n_ticks": n_t, "sd": sd, "dropped": n_deltas - len(rows),
        "min_events": min_events,
        "D": D, "NDC": NDC, "OS": OS, "OSM": OSM,
        "E_N": E_N, "C_N": C_N, "R_N": R_N,
        "E_os": E_os, "C_os": C_os, "R_os": R_os,
        "ratio": float(np.mean(OS / D)),
        "ratio_med": float(np.mean(OSM / D)),
    }


def report_scaling(res: dict, tp: float) -> None:
    """Print the measured exponents next to the BM/theory references."""
    D = res["D"]
    print(f"\nfeed {res['n_ticks']:,} ticks | tick sd(r) = {res['sd']:.4g} "
          f"robust (sd/tp = {res['sd'] / tp:.2f})")
    print(f"delta grid {D[0] * 100:.2f}% .. {D[-1] * 100:.2f}%  "
          f"({len(D)} usable, {res['dropped']} dropped for "
          f"<{res['min_events']} events)")
    print(f"  N(delta)       ~ delta^{res['E_N']:+.3f}   "
          f"(adj R2 {res['R_N']:.4f})  [BM ~ -1.85, theory -2]")
    print(f"  <omega(delta)> ~ delta^{res['E_os']:+.3f}  "
          f"(adj R2 {res['R_os']:.4f})  [BM ~ +1.00, theory +1]")
    ratio, ratio_med = res["ratio"], res["ratio_med"]
    mm = ratio / ratio_med if ratio_med else float("nan")
    print(f"  <omega>/delta      = {ratio:.3f}   (MEAN; theory/BM ~ 1.0)")
    print(f"  median-omega/delta = {ratio_med:.3f}   (MEDIAN; BM ~ 0.70 — "
          f"overshoots are right-skewed even for BM)")
    print(f"  mean/median        = {mm:.2f}   (BM ~ 1.5. >> 1.5 => the price "
          f"TRENDS: the mean law is drift-inflated)")


def event_prices(sim) -> np.ndarray:
    """The event-time tape: one price per PRINT, in execution order — the
    finest resolution the model has. The tick series is this tape sampled
    at each tick's last print (intra-tick wicks censored)."""
    prices = []
    for row in sim.trades_log:
        prices.append(row[5])          # (tick, id, agent, side, size, PRICE)
    return np.asarray(prices, float)


def plot_scaling_laws(sim, save_path: Optional[str] = None, show: bool = False,
                      time_base: str = "tick") -> Optional[str]:
    """The run-block entry point (mirrors plot_dashboard's shape): analyse
    the finished simulation's price series, print the report, save the
    two-law figure, and pop it when show=True.

    time_base="tick"  : the recorded per-tick series (last print per tick).
    time_base="event" : the trade tape, one price per print — intrinsic-time
    analysis on the model's true event clock, intra-tick wicks included."""
    import matplotlib.pyplot as plt
    from simulation_mvp import cfg_tag

    cfg = sim.cfg
    tag = cfg_tag(cfg)
    if time_base == "event":
        if not getattr(sim, "trades_log", None):
            raise SystemExit("time_base='event' needs sim.trades_log "
                             "(a finished Simulation, not a CSV shim)")
        prices = event_prices(sim)
        base_txt = f"EVENT time ({len(prices):,} prints)"
        if save_path is None:
            save_path = f"scaling_laws_event_{tag}.png"
    else:
        prices = np.asarray(sim.rec_price)
        base_txt = f"tick time ({len(prices):,} ticks)"
        if save_path is None:
            save_path = f"scaling_laws_{tag}.png"
    print(f"\n[scaling laws — {base_txt}]")
    try:
        res = analyse_scaling(prices)
    except RuntimeError as err:
        # a feed without DC structure is a legitimate outcome, not a crash:
        # report why, skip the figure, let the rest of the run block proceed
        print(f"[scaling laws — SKIPPED] {err}")
        return None
    report_scaling(res, cfg.tp)

    D, NDC, OS, OSM = res["D"], res["NDC"], res["OS"], res["OSM"]
    xs = np.array([D.min(), D.max()])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle(f"Intrinsic-time scaling laws  |  {tag}  |  {base_txt}  |  "
                 f"tp={cfg.tp} sl={cfg.sl}  |  sd(r)={res['sd']:.3g}",
                 fontsize=11, fontweight="bold")

    # LEFT: number of directional changes — the volatility component
    a1.loglog(D, NDC, "o", ms=6, color="#2563EB", label="measured")
    a1.loglog(xs, (xs / res["C_N"]) ** res["E_N"], "-", color="#B45309",
              lw=1.6, label=f"fit: E = {res['E_N']:.3f}  (R²={res['R_N']:.3f})")
    a1.loglog(xs, NDC[0] * (xs / D[0]) ** -2.0, ":", color="#6B7280", lw=1.4,
              label="theory: E = -2 (BM)")
    a1.set_xlabel("directional-change threshold  δ")
    a1.set_ylabel("N(δ)   number of directional changes")
    a1.set_title("Law (0b): DC count  →  VOLATILITY", fontsize=10)
    a1.legend(fontsize=8)
    a1.grid(True, which="both", ls=":", alpha=0.4)

    # RIGHT: mean overshoot — the liquidity component
    a2.loglog(D, OS, "o", ms=6, color="#15803D",
              label=f"mean  (⟨ω⟩/δ={res['ratio']:.2f})")
    a2.loglog(D, OSM, "s", ms=5, color="#2563EB", mfc="none",
              label=f"median  (/δ={res['ratio_med']:.2f}, drift-robust)")
    a2.loglog(xs, (xs / res["C_os"]) ** res["E_os"], "-", color="#B45309",
              lw=1.6, label=f"mean fit: E = {res['E_os']:.3f}  "
                            f"(R²={res['R_os']:.3f})")
    a2.loglog(xs, xs, ":", color="#6B7280", lw=1.4,
              label="theory: ⟨ω⟩ = δ  (BM/FX)")
    a2.set_xlabel("directional-change threshold  δ")
    a2.set_ylabel("⟨ω(δ)⟩   mean overshoot")
    a2.set_title(f"Law (9,os): overshoot  →  LIQUIDITY   "
                 f"(mean/δ={res['ratio']:.2f}  median/δ={res['ratio_med']:.2f})",
                 fontsize=9)
    a2.legend(fontsize=8)
    a2.grid(True, which="both", ls=":", alpha=0.4)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(save_path, dpi=140, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()          # pops the IDE window; returns when it is closed
    else:
        plt.close(fig)
    return save_path


class _FeedShim:
    """A minimal stand-in for a Simulation when analysing a saved CSV:
    just the two attributes plot_scaling_laws reads."""

    def __init__(self, cfg, prices) -> None:
        self.cfg = cfg
        self.rec_price = list(prices)


if __name__ == "__main__":
    # standalone convenience: analyse the DEFAULT config. Reuses its tagged
    # price CSV when present (instant), else runs the engine first.
    from dc_analysis import load_csv
    from simulation_mvp import Config, Simulation, cfg_tag

    HERE = os.path.dirname(os.path.abspath(__file__))
    cfg = Config()
    tag = cfg_tag(cfg)
    csv_path = os.path.join(HERE, f"price_btc_eur_{tag}.csv")
    out_png = os.path.join(HERE, f"scaling_laws_{tag}.png")
    if os.path.exists(csv_path):
        print(f"reusing {csv_path}")
        prices = load_csv(csv_path, "BTC/EUR")
        if len(prices) != cfg.T:
            print(f"WARNING: feed has {len(prices):,} rows but T={cfg.T:,} — "
                  f"stale CSV under the same tag? Delete it to rebuild.")
        plot_scaling_laws(_FeedShim(cfg, prices), save_path=out_png, show=True)
    else:
        sim = Simulation(cfg).run()
        print(sim.summary())
        sim.write_price_csv(csv_path)
        plot_scaling_laws(sim, save_path=out_png, show=True)
