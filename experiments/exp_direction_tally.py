"""
exp_direction_tally.py — bias or instability? The per-arm sign tally with the
channel fingerprint (HANDOFF-master §4.9's registered open run).

THE QUESTION
------------
The CLOB price breaks direction and runs (§4.9). Tally so far, pooled across
band arms: 6 down / 1 up — suggestive of a residual down-bias, equally
consistent with pure instability at n=7. The swap-duality argument says an
exact covariant engine gives P(up)=1/2 at EVERY (tp, sl); a persistent bias can
only live where the swap map fails, and the surviving candidate is the book's
BTC denomination (sizes/dust/depth are BTC quantities — the original numeraire
weld). tp-vs-sl is NOT a candidate: (tp, sl) is swap-self-dual for any values,
and both halves of the "tp<sl down / tp>sl up" conjecture already have measured
counterexamples (up-run at sl=2tp; down-run at tp=2sl, seed 1).

THE DESIGN
----------
Arm: the canonical default — n=500, tp=sl=0.01, close_mode="home",
entry_mode="rest", hold_fires_close=True, c=0.004. T=20k (direction locks well
before; measured). Seeds 1..10, one run per invocation (chunk-friendly).
Each run records: sign of ln p_final, and the drift decomposition by
(direction, side, role) using exp_drift_decomp's bit-neutral wrapper.

PREDICTIONS — REGISTERED BEFORE THE RUNS
----------------------------------------
P1 (duality null): the tally is consistent with 50/50 — reject a fair coin only
    at p<0.05 two-sided (i.e. >=9/10 one way).
P2 (fingerprint, AS-RUN CORRECTION: a channel's net cannot flip sign with run
    direction — the sign is baked into the BUY/SELL tag; the well-posed test
    reads PAIRED channel sums, entries vs closes, per run direction). A PAIR
    whose net does not flip between up-runs and down-runs is the
    symmetry-breaking residual — prediction: if any, it involves the BTC-denominated book
    machinery, and the follow-up is the book-mirror (EUR-denominated book),
    with the registered prediction that the tally then inverts.
FALSIFIER of the bias hypothesis: >=9/10 same-direction AND a non-flipping
    channel found -> residual bias established, channel named.
FALSIFIER of the instability-only reading: same tally outcome; if instead the
    tally is 5/5-ish and all channels flip, §4.9 stands as written.

Usage: python3 experiments/exp_direction_tally.py <seed>   (appends tally.jsonl)
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
    acc = {}
    real_submit = sim._submit

    def wrapped(o, **kw):
        p0 = sim.book.last_price
        trades = real_submit(o, **kw)
        p1 = sim.book.last_price
        if p1 != p0 and p0 > 0 and p1 > 0:
            dln = float(np.log(p1) - np.log(p0))
            a = idmap.get(o.agent_id)
            role = ("entry" if not getattr(o, "is_close", False)
                    else ("sl" if (a is not None and getattr(a, "closing", False))
                          else "impatience"))
            key = f"{o.direction.name}|{'L' if o.pos_side is Side.LONG else 'S'}|{role}"
            e = acc.setdefault(key, [0.0, 0])
            e[0] += dln
            e[1] += 1
        return trades

    sim._submit = wrapped
    sim.run()
    lnp = float(np.log(sim.p_int / cfg.x_0))
    row = {"seed": seed, "lnp": lnp, "dir": "UP" if lnp > 0 else "DOWN",
           "channels": {k: [round(v[0], 3), v[1]] for k, v in acc.items()}}
    with open("tally.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    top = sorted(acc.items(), key=lambda kv: -abs(kv[0][0] if False else kv[1][0]))[:3]
    tops = "  ".join(f"{k}:{v[0]:+.1f}" for k, v in top)
    print(f"seed {seed:2d}: {row['dir']:4s} lnp={lnp:+6.2f} | top channels: {tops}")


if __name__ == "__main__":
    run(int(sys.argv[1]))
