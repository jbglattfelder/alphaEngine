"""
exp_side_asymmetry.py — is the long-over-short PnL divergence the arithmetic
TP/SL barrier asymmetry?

OBSERVATION (seed 42, committed defaults): pnl_long -> +1235 EUR, pnl_short the
mirror, accruing steadily over a run in which the price FELL 12x.

HYPOTHESIS: with arithmetic bands, TP/SL at +/-10% are asymmetric in log space
(ln 1.1 = 0.0953 up vs |ln 0.9| = 0.1054 down). For an ~driftless log price the
nearer barrier is hit first with probability 0.1054/0.2007 = 0.525, so every
LONG round trip has expectation +0.525*10% - 0.475*10% = +0.50% of deployed
notional, and every SHORT round trip is the exact mirror. This is a bookkeeping
convention (percentage arithmetic), not market behaviour — the same class as
the 100 -> 110 -> 99 gauge artifact in HANDOFF §3(a).

PREDICTIONS, STATED BEFORE RUNNING (HANDOFF §5 protocol):
  P1. Arithmetic arm: pnl_long > 0 in nearly all seeds (sign test).
  P2. Arithmetic arm: pnl_long is NOT explained by the price move —
      correlation of pnl_long with ln(p_final/x_0) is weak/indeterminate.
  P3. Log arm (log_thresholds=True, bands x̄*e^{+/-0.1}): the systematic edge
      VANISHES — mean pnl_long consistent with 0, sign split ~50/50.
  P4. Magnitude (arithmetic arm): pnl_long ≈ 0.0050 x (total matched EUR)/2
      per run, order of magnitude. (/2: each round trip's notional appears in
      matched volume twice, entry leg + exit leg; approximate because exits
      fill at prices != entry.)

If instead pnl_long anti-correlates with the price move and survives the log
arm, the mechanism is elsewhere (candidate: side-asymmetric SL slippage from
asymmetric TP depth density).

Committed defaults otherwise: c=0.001, T=20000, tp=sl=0.10, clock_beta=1.
"""

import json
import math
import time

from config import Config
from simulation import Simulation

SEEDS = list(range(1, 21))
OUT = "exp_side_asymmetry.jsonl"


def run_one(seed: int, log_thresholds: bool) -> dict:
    cfg = Config(seed=seed, log_thresholds=log_thresholds)
    sim = Simulation(cfg).run()          # run_checks=True by default now
    pnl_l, pnl_s = sim._pnl_by_side(sim.p_int)
    matched_eur = float(sum(sim.recorder.series("matched_eur")))
    return {
        "seed": seed,
        "log_thresholds": log_thresholds,
        "pnl_long": pnl_l,
        "pnl_short": pnl_s,
        "p_final": sim.p_int,
        "log_price_move": math.log(sim.p_int / cfg.x_0),
        "matched_eur_total": matched_eur,
        "pred_edge_P4": 0.0050 * matched_eur / 2.0,
    }


if __name__ == "__main__":
    t0 = time.time()
    with open(OUT, "w") as f:
        for log_arm in (False, True):
            for seed in SEEDS:
                r = run_one(seed, log_arm)
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(f"[{time.time()-t0:6.0f}s] seed={seed:2d} "
                      f"log={log_arm} pnl_long={r['pnl_long']:+9.1f} "
                      f"lnp={r['log_price_move']:+6.2f} "
                      f"pred={r['pred_edge_P4']:7.1f}")
    print(f"done in {time.time()-t0:.0f}s -> {OUT}")
