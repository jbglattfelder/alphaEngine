"""
scaling_law.py — one config -> price-feed CSV -> intrinsic-time scaling-law dashboard.

Edit the block below and press Run. It:
  1. runs the config and writes the price feed to CSV (or reuses an existing CSV),
  2. loads the feed back FROM the CSV (so the analysis only ever sees the file,
     never the live engine — same path a real market feed would take),
  3. dissects it into directional changes / overshoots and plots the two laws
     log-log:
        LEFT   N(delta)  vs delta   -- the DC count      -> VOLATILITY proxy
        RIGHT  <omega(delta)> vs delta -- mean overshoot -> LIQUIDITY proxy

Algorithm and definitions live in dc_analysis.py (Glattfelder-Dupuis-Olsen 2011,
arXiv:0809.1040 alg. 2; Glattfelder-Golub 2022, arXiv:2204.02682). Reference
behaviour, verified there on Brownian motion:
    N(delta) ~ delta^-2      (BM measured -1.85 at a clean delta floor)
    <omega(delta)> ~= delta  (BM measured ratio 1.003)

DELTA FLOOR: thresholds are set relative to the feed's OWN tick volatility, not
in absolute %, because this engine's per-tick sd is ~0.85*tp (the TP/SL band sets
the tick volatility), i.e. ~1e-2 where FX ticks are ~1e-4. Below ~8x tick-sd a
single tick jumps the threshold and biases <omega> upward -- see the measured
bias table in dc_analysis.analyse().
"""
import csv
import os

import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder
from dc_analysis import measure, fit, load_csv

# ---------------- edit these ----------------
N, T, SEED = 500, 100_000, 1
C, TP, SL = 0.004, 0.01, 0.02
F = 0.5
CLOSE_MODE = "quantity"     # NOT passed by earlier versions of this file: feeds built with
SL_MODE    = "market"   # them silently used the config.py default ("quantity") -- a
                        # DIFFERENT MODEL. Always state the mechanism explicitly.

CSV_PATH = "price_feed.csv"
REUSE_CSV = True        # True: skip the run if CSV_PATH already exists (analysis is instant)
RUN_CHECKS = False      # per-tick conservation asserts; False is faster on long runs

DELTA_LO_MULT = 8.0     # delta grid floor, in units of the feed's tick sd (see note above)
DELTA_HI_MULT = 40.0    # ceiling; raise for longer feeds, lower if thresholds get dropped
N_DELTAS = 20
MIN_EVENTS = 12         # drop a threshold with fewer DC events than this (nothing to average)

OUT = "scaling_laws.png"
SHOW = True
# --------------------------------------------


def build_feed(path: str) -> None:
    """Run the config and write tick,p_int to CSV."""
    cfg = Config(n=N, T=T, seed=SEED, f=F, c=C, tp=TP, sl=SL,
                 close_mode=CLOSE_MODE, sl_mode=SL_MODE)
    print(cfg.summary())
    sim = Simulation(cfg, recorder=Recorder(), run_checks=RUN_CHECKS).run()
    tick = sim.recorder.series("tick")
    p = sim.recorder.series("p_int")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "p_int"])
        for i in range(len(p)):
            w.writerow([tick[i], repr(float(p[i]))])   # repr = full precision
    cfg.save(path.replace(".csv", "_config.json"))
    print(f"wrote {path} ({len(p):,} rows), p_final = {sim.p_int!r}")


def main() -> None:
    if not (REUSE_CSV and os.path.exists(CSV_PATH)):
        build_feed(CSV_PATH)
    else:
        print(f"reusing existing {CSV_PATH} (set REUSE_CSV=False to re-run)")

    prices = load_csv(CSV_PATH, "p_int")
    prices = prices[np.isfinite(prices) & (prices > 0)]
    n_t = len(prices)
    r1 = np.diff(prices) / prices[:-1]
    sd = float(np.std(r1[np.isfinite(r1)]))

    deltas = np.exp(np.linspace(np.log(DELTA_LO_MULT * sd),
                                np.log(DELTA_HI_MULT * sd), N_DELTAS))
    rows = [m for d in deltas if (m := measure(prices, float(d), n_t, MIN_EVENTS)) is not None]
    dropped = N_DELTAS - len(rows)
    if len(rows) < 3:
        raise SystemExit(f"only {len(rows)} usable thresholds — feed too short "
                         f"or DELTA_HI_MULT too high")

    D = np.array([r["delta"] for r in rows])
    NDC = np.array([r["N"] for r in rows], float)
    OS = np.array([r["os_mean"] for r in rows])

    E_N, C_N, R_N = fit(D, NDC)
    E_os, C_os, R_os = fit(D, OS)
    ratio = float(np.mean(OS / D))

    print(f"\nfeed {n_t:,} ticks | tick sd(r) = {sd:.4g} (sd/tp = {sd/TP:.2f})")
    print(f"delta grid {D[0]*100:.2f}% .. {D[-1]*100:.2f}%  "
          f"({len(rows)} usable, {dropped} dropped for <{MIN_EVENTS} events)")
    print(f"  N(delta)      ~ delta^{E_N:+.3f}   (adj R2 {R_N:.4f})   [BM ~ -1.85, theory -2]")
    print(f"  <omega(delta)>~ delta^{E_os:+.3f}  (adj R2 {R_os:.4f})  [BM ~ +1.00, theory +1]")
    print(f"  <omega>/delta = {ratio:.3f}                            [BM ~ 1.00]")
    print(f"     {'<1: overshoots die early -> anti-persistent / MORE liquid than BM' if ratio < 0.95 else ''}"
          f"{'>1: overshoots run -> trending / LESS liquid than BM' if ratio > 1.05 else ''}")

    _plot(D, NDC, OS, E_N, C_N, R_N, E_os, C_os, R_os, ratio, sd, n_t)


def _plot(D, NDC, OS, E_N, C_N, R_N, E_os, C_os, R_os, ratio, sd, n_t) -> None:
    # the engine line: every figure names its arm (the 4x silent-default lesson)
    ENGINE = (f"close={CLOSE_MODE} entry={globals().get('ENTRY_MODE','ioc')} "
              f"impatience={globals().get('HOLD_FIRES_CLOSE', False)}")

    import matplotlib
    if not SHOW:
        matplotlib.use("Agg")
    # the engine line: every figure names its arm (the 4x silent-default lesson)
    ENGINE = (f"close={CLOSE_MODE} entry={globals().get('ENTRY_MODE','ioc')} "
              f"impatience={globals().get('HOLD_FIRES_CLOSE', False)}")

    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle(f"Intrinsic-time scaling laws  |  n={N}, T={T:,}, seed={SEED}, c={C}, "
                 f"tp={TP} sl={SL}  |  {ENGINE}  |  tick sd(r)={sd:.3g}",
                 fontsize=11, fontweight="bold")
    xs = np.array([D.min(), D.max()])

    # LEFT: number of directional changes -- the volatility component
    a1.loglog(D, NDC, "o", ms=6, color="#2563EB", label="measured")
    a1.loglog(xs, (xs / C_N) ** E_N, "-", color="#B45309", lw=1.6,
              label=f"fit: E = {E_N:.3f}  (R²={R_N:.3f})")
    a1.loglog(xs, NDC[0] * (xs / D[0]) ** -2.0, ":", color="#6B7280", lw=1.4,
              label="theory: E = -2 (BM)")
    a1.set_xlabel("directional-change threshold  δ")
    a1.set_ylabel("N(δ)   number of directional changes")
    a1.set_title("Law (0b): DC count  →  VOLATILITY", fontsize=10)
    a1.legend(fontsize=8); a1.grid(True, which="both", ls=":", alpha=0.4)

    # RIGHT: mean overshoot -- the liquidity component
    a2.loglog(D, OS, "o", ms=6, color="#15803D", label="measured")
    a2.loglog(xs, (xs / C_os) ** E_os, "-", color="#B45309", lw=1.6,
              label=f"fit: E = {E_os:.3f}  (R²={R_os:.3f})")
    a2.loglog(xs, xs, ":", color="#6B7280", lw=1.4, label="theory: ⟨ω⟩ = δ  (BM/FX)")
    a2.set_xlabel("directional-change threshold  δ")
    a2.set_ylabel("⟨ω(δ)⟩   mean overshoot")
    a2.set_title(f"Law (9,os): mean overshoot  →  LIQUIDITY   "
                 f"(⟨ω⟩/δ = {ratio:.2f})", fontsize=10)
    a2.legend(fontsize=8); a2.grid(True, which="both", ls=":", alpha=0.4)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"\nwrote {OUT}")
    if SHOW:
        plt.show()


if __name__ == "__main__":
    main()
