"""
scaling_law_mvp.py — MVP config -> price-feed CSV -> intrinsic-time scaling laws.

Edit the block below and press Run. It:
  1. runs the MVP engine and writes the price feed to CSV — or reuses the
     tagged CSV if it already exists (analysis is then instant),
  2. loads the feed back FROM the CSV (the analysis only ever sees the file,
     never the live engine — the same path a real market feed would take),
  3. dissects it into directional changes / overshoots and plots the two
     laws log-log:
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

Outputs land next to this file, tagged with the config designator:
    price_btc_eur_<tag>.csv   (the feed, shared with simulation_mvp.py)
    scaling_laws_<tag>.png
"""

from __future__ import annotations

import os

import numpy as np

from simulation_mvp import Config, Simulation, cfg_tag
from dc_analysis import measure, fit, load_csv

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- edit these ----------------
N = 150          # agents per side
T = 100_000      # ticks
SEED = 9
CAPITAL_DIST = "pareto"   # block 2a: "pareto" | "normal"
BAND_DIST = "fixed"       # block 2b: "fixed"  | "normal"
CLOSING = "clock"         # block 2c: "clock"  | "normal"

REUSE_CSV = True    # True: skip the run if the tagged feed CSV already exists

DELTA_LO_MULT = 8.0   # delta grid floor, in units of the feed's tick sd
DELTA_HI_MULT = 40.0  # ceiling; raise for longer feeds, lower if thresholds drop
N_DELTAS = 20
MIN_EVENTS = 12       # drop a threshold with fewer DC events (nothing to average)

SHOW = True           # pop the figure in the IDE (it saves either way)
# --------------------------------------------

CFG = Config(n=N, T=T, seed=SEED, capital_dist=CAPITAL_DIST,
             band_dist=BAND_DIST, closing=CLOSING)
TAG = cfg_tag(CFG)
CSV_PATH = os.path.join(HERE, f"price_btc_eur_{TAG}.csv")
OUT = os.path.join(HERE, f"scaling_laws_{TAG}.png")


def build_feed(path: str) -> None:
    """Run the MVP engine and write the tick,BTC/EUR feed to CSV."""
    print(CFG.summary())
    sim = Simulation(CFG).run()
    print(sim.summary())
    sim.write_price_csv(path)
    print(f"wrote {path} ({len(sim.rec_price):,} rows), p_final = {sim.p!r}")


def main() -> None:
    if REUSE_CSV and os.path.exists(CSV_PATH):
        print(f"reusing existing {CSV_PATH} (set REUSE_CSV=False to re-run)")
    else:
        build_feed(CSV_PATH)

    prices = load_csv(CSV_PATH, "BTC/EUR")
    if len(prices) != T:
        print(f"WARNING: feed has {len(prices):,} rows but T={T:,} — a stale CSV "
              f"under the same tag? Set REUSE_CSV=False to rebuild it.")
    prices = prices[np.isfinite(prices) & (prices > 0)]
    n_t = len(prices)
    r1 = np.diff(prices) / prices[:-1]
    r_fin = r1[np.isfinite(r1)]
    # SIGNIFICANCE FLOOR: dense markets print many essentially-unchanged
    # prices, producing float-dust returns ~1e-15 that are NONZERO and can
    # drive the MAD to machine epsilon -> the delta grid collapses and every
    # tick is a "DC event". A return below R_EPS is bookkeeping, not a move.
    R_EPS = 1e-9
    r_nz = r_fin[np.abs(r_fin) > R_EPS]
    # ROBUST scale: one flash event inflates np.std by orders of magnitude
    # and pushes the delta grid above the feed's typical volatility ("0
    # usable thresholds"). MAD tracks the TYPICAL tick; the flash stays
    # measurable as DC events instead of silently recalibrating the ruler.
    sd_raw = float(np.std(r_fin))
    if len(r_nz):
        sd = float(1.4826 * np.median(np.abs(r_nz - np.median(r_nz))))
    else:
        sd = sd_raw
    if sd == 0.0:
        sd = sd_raw
    if sd_raw > 3 * sd:
        print(f"NOTE: raw sd(r) = {sd_raw:.4g} is {sd_raw/sd:.1f}x the robust "
              f"(MAD) scale {sd:.4g} — flash/regime events present; the delta "
              f"grid uses the robust scale.")

    deltas = np.exp(np.linspace(np.log(DELTA_LO_MULT * sd),
                                np.log(DELTA_HI_MULT * sd), N_DELTAS))
    rows = []
    for d in deltas:
        m = measure(prices, float(d), n_t, MIN_EVENTS)
        if m is not None:
            rows.append(m)
    dropped = N_DELTAS - len(rows)
    if len(rows) < 3:
        raise SystemExit(f"only {len(rows)} usable thresholds — feed too short "
                         f"or DELTA_HI_MULT too high")

    D = np.array([r["delta"] for r in rows])
    NDC = np.array([r["N"] for r in rows], float)
    OS = np.array([r["os_mean"] for r in rows])
    OSM = np.array([r["os_median"] for r in rows])

    E_N, C_N, R_N = fit(D, NDC)
    E_os, C_os, R_os = fit(D, OS)
    ratio = float(np.mean(OS / D))
    ratio_med = float(np.mean(OSM / D))

    print(f"\nfeed {n_t:,} ticks | tick sd(r) = {sd:.4g} robust "
          f"(sd/tp = {sd / CFG.tp:.2f})")
    print(f"delta grid {D[0]*100:.2f}% .. {D[-1]*100:.2f}%  "
          f"({len(rows)} usable, {dropped} dropped for <{MIN_EVENTS} events)")
    print(f"  N(delta)       ~ delta^{E_N:+.3f}   (adj R2 {R_N:.4f})  [BM ~ -1.85, theory -2]")
    print(f"  <omega(delta)> ~ delta^{E_os:+.3f}  (adj R2 {R_os:.4f})  [BM ~ +1.00, theory +1]")
    mm = ratio / ratio_med if ratio_med else float("nan")
    print(f"  <omega>/delta      = {ratio:.3f}   (MEAN; theory/BM ~ 1.0)")
    print(f"  median-omega/delta = {ratio_med:.3f}   (MEDIAN; BM ~ 0.70 — overshoots are right-skewed even for BM)")
    print(f"  mean/median        = {mm:.2f}   (BM ~ 1.5. >> 1.5 => the price TRENDS: the mean law is drift-inflated)")

    _plot(D, NDC, OS, OSM, E_N, C_N, R_N, E_os, C_os, R_os, ratio, ratio_med, sd, n_t)


def _plot(D, NDC, OS, OSM, E_N, C_N, R_N, E_os, C_os, R_os,
          ratio, ratio_med, sd, n_t) -> None:
    """The two laws, log-log, with fits and the BM reference lines."""
    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle(f"Intrinsic-time scaling laws  |  {TAG}  |  T={T:,}, "
                 f"tp={CFG.tp} sl={CFG.sl}  |  tick sd(r)={sd:.3g}",
                 fontsize=11, fontweight="bold")
    xs = np.array([D.min(), D.max()])

    # LEFT: number of directional changes — the volatility component
    a1.loglog(D, NDC, "o", ms=6, color="#2563EB", label="measured")
    a1.loglog(xs, (xs / C_N) ** E_N, "-", color="#B45309", lw=1.6,
              label=f"fit: E = {E_N:.3f}  (R²={R_N:.3f})")
    a1.loglog(xs, NDC[0] * (xs / D[0]) ** -2.0, ":", color="#6B7280", lw=1.4,
              label="theory: E = -2 (BM)")
    a1.set_xlabel("directional-change threshold  δ")
    a1.set_ylabel("N(δ)   number of directional changes")
    a1.set_title("Law (0b): DC count  →  VOLATILITY", fontsize=10)
    a1.legend(fontsize=8)
    a1.grid(True, which="both", ls=":", alpha=0.4)

    # RIGHT: mean overshoot — the liquidity component
    a2.loglog(D, OS, "o", ms=6, color="#15803D", label=f"mean  (⟨ω⟩/δ={ratio:.2f})")
    a2.loglog(D, OSM, "s", ms=5, color="#2563EB", mfc="none",
              label=f"median  (/δ={ratio_med:.2f}, drift-robust)")
    a2.loglog(xs, (xs / C_os) ** E_os, "-", color="#B45309", lw=1.6,
              label=f"mean fit: E = {E_os:.3f}  (R²={R_os:.3f})")
    a2.loglog(xs, xs, ":", color="#6B7280", lw=1.4, label="theory: ⟨ω⟩ = δ  (BM/FX)")
    a2.set_xlabel("directional-change threshold  δ")
    a2.set_ylabel("⟨ω(δ)⟩   mean overshoot")
    a2.set_title(f"Law (9,os): overshoot  →  LIQUIDITY   "
                 f"(mean/δ={ratio:.2f}  median/δ={ratio_med:.2f})", fontsize=9)
    a2.legend(fontsize=8)
    a2.grid(True, which="both", ls=":", alpha=0.4)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"\nwrote {OUT}")
    if SHOW:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
