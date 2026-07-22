"""
exp_evolution.py — frequency dependence of the sizing-convention edge, and
whether imitation dynamics find the zero-transfer mix.

PREDICTIONS, STATED BEFORE RUNNING:
  P1 (sweep): the per-capita realized edge of live-converters, within each tribe,
      DECREASES as their frequency rises (minority advantage), crossing the
      resident convention's edge at some interior mix m*. Rationale: §3(f) showed
      pure populations of either convention bleed — whichever tilt dominates the
      book pays; a rare deviant free-rides on the majority's depth.
  P2 (sweep): the aggregate long->short transfer at mix 0.5 is far smaller than
      the pure arms' |1.3-2.1%| — the constructed-symmetry claim.
  P3 (evolve): starting from 0.5, the mix drifts toward m* per tribe and hovers
      (mutation keeps it off the boundary). If instead it runs to 0 or 1,
      majority advantage holds and the blend needs active rebalancing.

Usage:
  python3 exp_evolution.py sweep <mix> <seed> [<seed> ...]
  python3 exp_evolution.py evolve <seed> [T]
"""

import json
import math
import sys

import numpy as np

from config import Config
from simulation import Simulation
from agents import Side


def edge_by_conv(sim) -> dict:
    """Per-tribe, per-convention realized edge (pnl per EUR notional)."""
    conv = {a.id: a.conv_live for a in sim.pop.agents}
    side = {a.id: ("L" if a.side is Side.LONG else "S") for a in sim.pop.agents}
    acc = {}
    for r in sim.trade_log:
        key = (side[r["agent"]], conv[r["agent"]])
        p, n = acc.get(key, (0.0, 0.0))
        acc[key] = (p + r["pnl"], n + r["entry_q"])
    return {f"{k[0]}_{'live' if k[1] else 'ref'}": (v[0] / v[1] if v[1] else float("nan"))
            for k, v in acc.items()}


def run_sweep(mix: float, seed: int) -> None:
    sim = Simulation(Config(seed=seed, conv_mode="mixed", conv_mix=mix)).run()
    e = edge_by_conv(sim)
    tl = sim.trade_log
    real_L = sum(r["pnl"] for r in tl if r["agent"] < sim.cfg.n)
    notional = sum(r["entry_q"] for r in tl)
    out = {"mix": mix, "seed": seed, "p_final": sim.p_int,
           "transfer": real_L / notional if notional else float("nan"), **e}
    with open("evolution_sweep.jsonl", "a") as f:
        f.write(json.dumps(out) + "\n")
    print(f"mix={mix:.1f} seed={seed:2d} lnp={math.log(sim.p_int):+6.2f} "
          f"transfer={out['transfer']:+.4f}  "
          + "  ".join(f"{k}={v:+.4f}" for k, v in sorted(e.items())))


def run_evolve(seed: int, T: int) -> None:
    cfg = Config(seed=seed, T=T, conv_mode="mixed", evolve=True)
    sim = Simulation(cfg).run()
    with open(f"evolution_run_{seed}.json", "w") as f:
        json.dump({"seed": seed, "T": T, "epochs": sim.evolve_log,
                   "p_final": sim.p_int, "edges": edge_by_conv(sim)}, f)
    for ep in sim.evolve_log[::2]:
        print(f"  t={ep['tick']:6d}  mix L={ep['mix_long']:.2f} S={ep['mix_short']:.2f} "
              f"switches={ep['switches']}")
    print(f"seed {seed}: final mix L={sim.evolve_log[-1]['mix_long']:.2f} "
          f"S={sim.evolve_log[-1]['mix_short']:.2f}")


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        mix = float(sys.argv[2])
        for s in sys.argv[3:]:
            run_sweep(mix, int(s))
    else:
        run_evolve(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 40_000)
