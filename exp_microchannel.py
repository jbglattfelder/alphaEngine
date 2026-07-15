"""
exp_microchannel.py — isolate the §3(f) stop-transfer micro-channel.

PREDICTIONS, STATED BEFORE RUNNING:

  A (depth/sizing channel; arm=frozen): frozen_sizing=True removes every /p from
    order sizing (both tribes open f*K0/q/x_0). If the 1/p package in sizing and
    TP depth is the channel, the stop-rate asymmetry (baseline L/S TP-rates
    ~0.55/0.75) COLLAPSES toward equality and pnl_long ~ 0.

  B (cascades; from baseline logs): a long stop is a market sell that moves the
    last price down within the tick; the SL check next tick can fire a batch. If
    cascades matter, same-side same-tick SL multiplicity will exceed a Poisson
    null at the same per-tick rate.

  C (local drift; from baseline logs): if the price path alone (its per-tick
    drift+vol, no microstructure) explains the stop rates, then bootstrap paths
    built from the run's own per-tick log-returns must reproduce P(TP first)
    ~0.55 for the long band [x0.9, x1.1] and ~0.75 for the short band — from the
    SAME return pool, so any asymmetry it produces comes from drift, not depth.

  D (fill exponent; from baseline logs): first-ever entry notional vs K0 should
    scale as K0^gamma with gamma ~ 0.55-0.65 at c=0.001 (interpolating HANDOFF's
    c-sweep: 0.0005->0.52, 0.008->0.81). This is the committed-instrument replay
    of the retired monkeypatch measurement (hand-validation priority #2).

Usage: python3 exp_microchannel.py {baseline|frozen} seed [seed ...]
Writes microchannel_{arm}_{seed}.json artifacts (trade log + p series).
"""

import json
import math
import sys

from config import Config
from simulation import Simulation


def run(arm: str, seed: int) -> None:
    cfg = Config(seed=seed, frozen_sizing=(arm == "frozen"),
                 invariant_sizing=(arm == "invariant"))   # p^(-1/2), both tribes
    sim = Simulation(cfg).run()
    pl, ps = sim._pnl_by_side(sim.p_int)
    out = {
        "arm": arm, "seed": seed, "p_final": sim.p_int,
        "pnl_long": pl,
        "p_int": [float(x) for x in sim.recorder.series("p_int")],
        "trade_log": sim.trade_log,
    }
    with open(f"microchannel_{arm}_{seed}.json", "w") as f:
        json.dump(out, f)
    tl = sim.trade_log
    def rate(side):
        n_tp = sum(1 for r in tl if r["side"] == side and r["exit"] == "TP")
        n = sum(1 for r in tl if r["side"] == side)
        return n_tp / n if n else float("nan")
    print(f"{arm:8s} seed={seed:2d} lnp={math.log(sim.p_int):+6.2f} "
          f"pnl_long={pl:+9.1f} L-TP={rate('L'):.3f} S-TP={rate('S'):.3f} "
          f"n={len(tl)}")


if __name__ == "__main__":
    arm = sys.argv[1]
    for s in sys.argv[2:]:
        run(arm, int(s))
