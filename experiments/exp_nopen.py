"""
exp_nopen.py — is OPEN INVENTORY (not population) the control variable?

THE QUESTION
------------
Threads 4/5 of HANDOFF-v4 §6 are both phrased in n: the tick-scale momentum
q(1)=0.70 at n=150 dies by n=500; TP fills ratchet at n=2 and revert at n=150.
But §2.8's density gate showed only 35/1000 agents hold a position at any moment
— and the resting TP count IS the book's entire depth (§1: the only passive
orders are TPs). The mechanistically meaningful variable should therefore be the
number of simultaneously open positions, n_open ≈ n · c · τ_pos, not n itself.
n and c should be interchangeable through it.

PREDICTIONS — STATED BEFORE THE RUN
-----------------------------------
P1 (collapse): q(m=1) is a decreasing function of mean n_open, and points from
    DIFFERENT n at similar n_open coincide (within seed noise). In particular
    (n=150, high c) lands on the (n=500, low c) curve.
P2 (crossover): the q(1)=0.5 crossing sits at a common n_open* regardless of
    how (n, c) produced it.
FALSIFIER: if runs at matched n_open but different n give systematically
    different q(1) — i.e. n retains an effect at fixed inventory — the collapse
    fails and n acts through a second channel (candidate: entry-flow imbalance
    scales with n independently of depth). Report it as such.

Config: home arm, tp=sl=0.01, log thresholds, seed as given. q measured on
NONZERO log-steps (the handoff §2.2 convention). n_open sampled every 25 ticks.

Usage: python3 exp_nopen.py <n> <c> <T> <seed>     (appends to nopen.jsonl)
"""
import json
import sys

import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder


def q_at_scale(steps: np.ndarray, m: int) -> float:
    """Continuation probability of the sign sequence coarse-grained by summing m steps."""
    if m > 1:
        k = (len(steps) // m) * m
        steps = steps[:k].reshape(-1, m).sum(axis=1)
    s = np.sign(steps)
    s = s[s != 0]
    if len(s) < 20:
        return float("nan")
    return float((s[1:] == s[:-1]).mean())


def main(n: int, c: float, T: int, seed: int) -> None:
    cfg = Config(n=n, c=c, T=T, seed=seed, close_mode="home", sl_mode="market",
                 tp=0.01, sl=0.01)
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False)

    open_samples = []
    _step = sim.step
    def step_and_sample(t):
        ok = _step(t)
        if t % 25 == 0:
            open_samples.append(sum(1 for a in sim.pop.agents if abs(a.pos.b) > 1e-9))
        return ok
    sim.step = step_and_sample
    sim.run()

    p = np.array(sim.recorder.series("p_int"))
    r = np.diff(np.log(p))
    steps = r[r != 0]
    row = {
        "n": n, "c": c, "T": T, "seed": seed,
        "n_open_mean": float(np.mean(open_samples)),
        "n_open_sd": float(np.std(open_samples)),
        "n_steps": int(len(steps)),
        "lnp": float(np.log(sim.p_int / cfg.x_0)),
        **{f"q_m{m}": q_at_scale(r, m) for m in (1, 2, 4, 8, 16, 32)},
    }
    with open("nopen.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"n={n:4d} c={c:<6} T={T} seed={seed}: n_open={row['n_open_mean']:6.1f} "
          f"q1={row['q_m1']:.3f} q2={row['q_m2']:.3f} q8={row['q_m8']:.3f} "
          f"steps={row['n_steps']} lnp={row['lnp']:+.2f}")


if __name__ == "__main__":
    main(int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
