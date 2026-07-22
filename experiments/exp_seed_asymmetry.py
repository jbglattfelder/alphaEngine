"""
exp_seed_asymmetry.py — WHAT is the seed of the fresh/stale asymmetry?

HYPOTHESIS (registered before running): the close-COMPLETION asymmetry.
Home-mode long close = self-funded SELL of held coins -> completes at once.
Home-mode short cover = budget-capped BUY -> can partial-fill and re-fire.
One structural difference predicts the whole chain:
  P-A: mean ticks-in-closing (short) > (long); short closes take >1 submit,
       long closes ~1.
  P-B: the entry count gap (~6% more long entries) is the demographic shadow
       of P-A (shorts spend less time flat).
  P-C: flips (position sign crossings during close) occur ONLY on shorts.
  P-D (stale sign): stale prints (tp_cross, flip) execute at levels BELOW the
       last print (frac_below >> 1/2), fresh prints do not — the down-drag is
       the geometry of which resting levels get eaten.
FALSIFIERS: long closes multi-submit at short-like rates (P-A dead); flips on
longs (P-C dead); stale frac_below ~ 1/2 (P-D dead).

Usage: python3 experiments/exp_seed_asymmetry.py <seed>   (n=500, T=20k, canonical arm)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from config import Config
from simulation import Simulation
from agents import Side

N, T = 500, 20_000
ARM = dict(f=0.5, c=0.004, tp=0.01, sl=0.01, close_mode="home",
           entry_mode="rest", hold_fires_close=True,
           x_accounting=True, log_thresholds=True, symmetric_solvency=True)


def run(seed: int) -> None:
    cfg = Config(n=N, T=T, seed=seed, **ARM)
    sim = Simulation(cfg, run_checks=False)
    idmap = {a.id: a for a in sim.pop.agents}
    real_submit = sim._submit

    stats = {"submits": {}, "below": {}, "flips_by_tribe": {"L": 0, "S": 0}}
    close_start, close_dur, close_subs = {}, {"L": [], "S": []}, {"L": [], "S": []}
    cur_subs = {}
    prev_b = {a.id: 0.0 for a in sim.pop.agents}

    def wrapped(o, **kw):
        a = idmap.get(o.agent_id)
        tribe = "L" if o.pos_side is Side.LONG else "S"
        if not getattr(o, "is_close", False):
            role = "entry"
        elif a is None or not getattr(a, "closing", False):
            role = "tp_cross"
        else:
            canonical = (o.direction.name == "BUY") == (o.pos_side is Side.SHORT)
            role = "close" if canonical else "flip"
        if role in ("close", "flip") and a is not None:
            cur_subs[a.id] = cur_subs.get(a.id, 0) + 1
        b_pre = a.pos.b if a is not None else 0.0
        p0 = sim.book.last_price
        trades = real_submit(o, **kw)
        p1 = sim.book.last_price
        if a is not None and b_pre != 0 and a.pos.b != 0 and (b_pre > 0) != (a.pos.b > 0):
            stats["flips_by_tribe"][ "L" if a.side is Side.LONG else "S"] += 1
        if p1 != p0 and p0 > 0:
            key = f"{role}"
            s_, b_ = stats["submits"].setdefault(key, [0, 0.0]), stats["below"].setdefault(key, [0, 0])
            s_[0] += 1; s_[1] += float(np.log(p1) - np.log(p0))
            b_[0] += 1; b_[1] += 1 if p1 < p0 else 0
        return trades

    sim._submit = wrapped

    _step = sim.step
    def step_tracking(t):
        for a in sim.pop.agents:
            if a.closing and a.id not in close_start:
                close_start[a.id] = t
                cur_subs[a.id] = 0
            elif not a.closing and a.id in close_start:
                tribe = "L" if a.side is Side.LONG else "S"
                close_dur[tribe].append(t - close_start.pop(a.id))
                close_subs[tribe].append(cur_subs.pop(a.id, 0))
        return _step(t)
    sim.step = step_tracking
    sim.run()

    out = {"seed": seed, "lnp": float(np.log(sim.p_int)),
           "close_dur_mean": {k: float(np.mean(v)) if v else None for k, v in close_dur.items()},
           "close_dur_n": {k: len(v) for k, v in close_dur.items()},
           "close_subs_mean": {k: float(np.mean(v)) if v else None for k, v in close_subs.items()},
           "flips_by_tribe": stats["flips_by_tribe"],
           "frac_print_below": {k: (v[1] / v[0] if v[0] else None)
                                for k, v in stats["below"].items()}}
    with open("seed_asym.jsonl", "a") as f:
        f.write(json.dumps(out) + "\n")
    print(f"seed {seed}: lnp={out['lnp']:+.2f}")
    print(f"  closing ticks  L={out['close_dur_mean']['L']:.1f} S={out['close_dur_mean']['S']:.1f}"
          f"   submits/close L={out['close_subs_mean']['L']:.2f} S={out['close_subs_mean']['S']:.2f}"
          f"   completed L={out['close_dur_n']['L']} S={out['close_dur_n']['S']}")
    print(f"  flips: L={out['flips_by_tribe']['L']} S={out['flips_by_tribe']['S']}")
    print("  frac printing BELOW last:",
          {k: round(v, 2) for k, v in out["frac_print_below"].items() if v is not None})


if __name__ == "__main__":
    run(int(sys.argv[1]))
