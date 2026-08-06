"""
scan_mvp.py — parameter scan over the three interchangeable blocks.

Full 2^3 factorial over
    CAPITAL_DIST in {pareto, normal}
    BAND_DIST    in {fixed,  normal}
    CLOSING      in {clock,  normal}
times SEEDS, at fixed (N, T). One JSON line per finished run is appended to
scan_results.jsonl immediately, so partial progress survives interruption.

Arm code: three letters, one per block, default letter capitalised concept:
    P/N = capital Pareto / Normal
    F/N = bands   Fixed  / Normal
    C/N = closing Clock  / Normal
e.g. "PFC" = the frozen null, "NNN" = all three switched.
"""

from __future__ import annotations

import itertools
import json
import os
import time

import numpy as np

from simulation_mvp import Config, Simulation
from stylized_facts_mvp import compute_facts
from scaling_law_mvp import robust_tick_sd, analyse_scaling

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- edit these ----------------
N = 400
T = 30_000
SEEDS = (9, 17, 23, 42)
OUT = os.path.join(HERE, "scan_results.jsonl")
# --------------------------------------------

ARMS = list(itertools.product(("pareto", "normal"),
                              ("fixed", "normal"),
                              ("clock", "normal")))


def arm_code(cap: str, band: str, close: str) -> str:
    """Three-letter arm code, e.g. PFC (the null), NNN (all switched)."""
    a = "P" if cap == "pareto" else "N"
    b = "F" if band == "fixed" else "N"
    c = "C" if close == "clock" else "N"
    return a + b + c


def run_one(cap: str, band: str, close: str, seed: int) -> dict:
    """One run -> one flat metrics dict (everything the plots need)."""
    cfg = Config(n=N, T=T, seed=seed, capital_dist=cap,
                 band_dist=band, closing=close)
    t0 = time.time()
    sim = Simulation(cfg, run_checks=False).run()
    dt = time.time() - t0

    p = np.asarray(sim.rec_price)
    F = compute_facts(p)
    row = {
        "arm": arm_code(cap, band, close),
        "cap": cap, "band": band, "close": close, "seed": seed,
        "n": N, "T": T, "secs": round(dt, 1),
        "p_final": float(p[-1]),
        "ln_drift": float(np.log(p[-1] / cfg.x_0)),
        "sd_raw": F["sd"],
        "sd_rob": float(robust_tick_sd(p)),
        "zero_frac": F["zero_frac"],
        "acf_abs_L1": float(F["acf_abs"][0]),
        "acf_abs_L10": float(F["acf_abs"][2]),
        "acf_abs_L100": float(F["acf_abs"][5]),
        "kurt_m1": F["kurt"][1],
        "kurt_m125": F["kurt"][125],
        "alive_frac": (sim.rec_alive_long[-1] + sim.rec_alive_short[-1]) / (2 * N),
        "n_trades": len(sim.trades_log),
        # coarse price path for the panel figure (500 points is plenty)
        "path": [float(x) for x in p[:: max(1, len(p) // 500)]],
    }
    # scaling laws can fail on a short/quiet feed -> record NaN, not a crash
    try:
        res = analyse_scaling(p)
        row["E_N"] = res["E_N"]
        row["os_ratio"] = res["ratio"]
        row["n_deltas_used"] = int(len(res["D"]))
    except SystemExit:
        row["E_N"] = float("nan")
        row["os_ratio"] = float("nan")
        row["n_deltas_used"] = 0
    return row


def main() -> None:
    todo = [(cap, band, close, seed)
            for (cap, band, close) in ARMS for seed in SEEDS]
    print(f"scan: {len(ARMS)} arms x {len(SEEDS)} seeds = {len(todo)} runs "
          f"at n={N}, T={T:,}")
    t0 = time.time()
    with open(OUT, "w") as f:
        for i, (cap, band, close, seed) in enumerate(todo, 1):
            row = run_one(cap, band, close, seed)
            f.write(json.dumps(row) + "\n")
            f.flush()
            done = time.time() - t0
            eta = done / i * (len(todo) - i)
            print(f"[{i:2d}/{len(todo)}] {row['arm']} seed={seed:2d}  "
                  f"{row['secs']:5.1f}s  ln_drift={row['ln_drift']:+.3f}  "
                  f"kurt={row['kurt_m1']:8.1f}  (eta {eta/60:.0f} min)")
    print(f"done in {(time.time() - t0)/60:.1f} min -> {OUT}")


if __name__ == "__main__":
    main()
