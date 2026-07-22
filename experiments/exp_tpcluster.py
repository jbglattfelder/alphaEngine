"""
exp_tpcluster.py — cluster the TAKE-PROFITS (HANDOFF-v4 §6.1, the corrected
Osler experiment; last shot at a stylized fact at level 0).

MECHANISM UNDER TEST
--------------------
All passive depth is TP limits (§1). Snapping TPs to k significant figures
piles the depth onto discrete levels; the space between levels is EMPTY, and a
gap is what a jump is. Osler (2003): TPs cluster AT round numbers (barriers),
stops just beyond (breakouts). Stops are already clustered (§2.8) and firing
them together produced no jumps — the missing ingredient was gaps in the DEPTH.

PREDICTIONS — STATED BEFORE THE RUN
-----------------------------------
P1: with a coarse uniform grid (k=2, and especially k=1 where grid spacing >>
    tp), the multi-band step fraction `>2·tp` becomes NONZERO for the first
    time (baseline 0.0–0.2% across every knob tried all session).
P2: P(|r| > 4·sd) > 0 for the first time in at least the coarsest arm —
    compact support (§2.5) breaks.
P3 (second-order, qualitative): the single-k arms add one characteristic scale;
    the HIERARCHY arm (per-agent roundness, coarse-heavy) produces tails while
    damaging scale structure less. Read ⟨ω⟩/δ at 3 δ values as the gauge.
FALSIFIER: `>2·tp` ~ 0 in ALL arms → compact support survives clustered depth →
    a second confirmed instance of §0 ("fat tails are unreachable at level 0"),
    and the level-1 actor inherits the whole burden.
CONFOUND GAUGE (report, do not hide): realized mean and median |ln(tp_limit/x̄)|
    per arm. The entry-side guard inflates the effective tp distance when grid
    spacing > tp (k=1 regime); any tail found there must survive the k=2 arm
    (spacing ~ tp) to count.

Arms: off | k=3 | k=2 | k=1 | hier.  n=150, c=0.004, T=16k, home, tp=sl=0.01.
Usage: python3 exp_tpcluster.py <arm> <seed>      (appends tpcluster.jsonl)
"""
import json
import math
import sys

import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder
from dc_analysis import dc_log_events


def run(arm: str, seed: int) -> None:
    kw = {}
    if arm == "hier":
        kw["tp_sig_hier"] = True
    elif arm != "off":
        kw["tp_sig"] = int(arm[1:])
    cfg = Config(n=150, c=0.004, T=16_000, seed=seed, close_mode="home",
                 sl_mode="market", tp=0.01, sl=0.01, **kw)
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False)

    # confound gauge: sample realized TP distances as they rest
    tp_dists = []
    _orig = type(sim.pop.agents[0]).tp_price
    def tp_price_logged(agent, c):
        v = _orig(agent, c)
        x = agent.pos.avg_price
        if v > 0 and x > 0:
            tp_dists.append(abs(math.log(v / x)))
        return v
    type(sim.pop.agents[0]).tp_price = tp_price_logged
    try:
        sim.run()
    finally:
        type(sim.pop.agents[0]).tp_price = _orig

    p = np.array(sim.recorder.series("p_int"))
    y = np.log(p)
    r = np.diff(y)
    nz = r[r != 0]
    sd = nz.std()
    band = cfg.tp
    os_ratio = {}
    for kmult in (8, 16, 32):
        ev = dc_log_events(y, kmult * sd)[1:]
        os_ratio[kmult] = (float(np.mean([e.overshoot for e in ev]) / (kmult * sd))
                           if len(ev) >= 12 else float("nan"))
    row = {
        "arm": arm, "seed": seed, "lnp": float(y[-1] - y[0]),
        "n_steps": int(len(nz)), "sd": float(sd),
        "gt2tp": float((np.abs(nz) > 2 * band).mean()),
        "max_over_tp": float(np.abs(nz).max() / band),
        "p_gt3sd": float((np.abs(nz) > 3 * sd).mean()),
        "p_gt4sd": float((np.abs(nz) > 4 * sd).mean()),
        "p_gt5sd": float((np.abs(nz) > 5 * sd).mean()),
        "tp_dist_mean": float(np.mean(tp_dists)),
        "tp_dist_med": float(np.median(tp_dists)),
        "os8": os_ratio[8], "os16": os_ratio[16], "os32": os_ratio[32],
    }
    with open("tpcluster.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"{arm:>4} s{seed}: >2tp={100*row['gt2tp']:5.2f}%  max/tp={row['max_over_tp']:4.1f}  "
          f"P>3sd={row['p_gt3sd']:.4f} P>4sd={row['p_gt4sd']:.4f} P>5sd={row['p_gt5sd']:.4f}  "
          f"tp_eff={row['tp_dist_mean']:.4f}  os(8/16/32)={row['os8']:.2f}/{row['os16']:.2f}/{row['os32']:.2f}  "
          f"lnp={row['lnp']:+.2f}")


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]))
