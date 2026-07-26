"""
exp_exponent_scatter.py — the single-path exponent DISTRIBUTION of the
symmetric null vs the BM finite-sample band (HANDOFF-master §4.10).

WHY
---
Single-path DC exponents are path-conditional: measured E_N = -1.97 (seed 1),
-1.99 (seed 9, n=150), -1.665 (seed 41) against a matched-BM single-path band
of -1.897 +/- 0.037 — seed 41 sits ~6 sigma outside (overshoot ratio 1.90 is
~23 sigma outside). The symmetric null is an ensemble of REGIMES; the width of
its exponent distribution is the surviving stylized fact.

PREDICTIONS (registered)
------------------------
P1: over >=10 seeds, sd(E_N_engine) >= 5 x sd(E_N_BM) (0.037 at T=150k).
P2: the exponent pairs (E_N, <os>/d) correlate — shallow N with inflated os
    (one regime axis, not two independent wobbles).
P3: the regime selector correlates with the realized capital-draw asymmetry
    (per-seed tribe median ratio) — the Pareto draw does not self-average.

Usage: python3 experiments/exp_exponent_scatter.py <seed>   (engine row)
       python3 experiments/exp_exponent_scatter.py bm       (12-path BM band)
Appends exponent_scatter.jsonl. Engine rows at the frozen default config
(n=500, T=150_000 takes ~15 min/seed on one core — background them).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from dc_analysis import dc_log_events

N, T = 500, 150_000


def fit_pair(y: np.ndarray, sd: float):
    deltas = np.geomspace(8 * sd, 40 * sd, 14)
    Ns, oss = [], []
    for d in deltas:
        ev = dc_log_events(y, d)[1:]
        if len(ev) < 12:
            Ns.append(np.nan); oss.append(np.nan); continue
        Ns.append(len(ev))
        oss.append(np.mean([e.overshoot for e in ev]) / d)
    Ns = np.array(Ns, float); ok = ~np.isnan(Ns)
    E = float(np.polyfit(np.log(deltas[ok]), np.log(Ns[ok]), 1)[0])
    return E, float(np.nanmean(oss))


def engine_row(seed: int) -> dict:
    from config import Config
    from simulation import Simulation
    from analysis import Recorder
    from agents import Side
    cfg = Config(n=N, T=T, seed=seed, c=0.004, tp=0.01, sl=0.01)
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False).run()
    p = np.array(sim.recorder.series("p_int"))
    y = np.log(p)
    r = np.diff(y); r_nz = r[np.abs(r) > 1e-9]   # significance floor: float-dust prints are not moves
    sd = float(1.4826 * np.median(np.abs(r_nz - np.median(r_nz))))   # flash-robust (par 4.10)
    if sd == 0.0:
        sd = float(r_nz.std())
    E, osr = fit_pair(y, sd)
    k_l = np.median([a.K0 for a in sim.pop.agents if a.side is Side.LONG])
    k_s = np.median([a.K0 for a in sim.pop.agents if a.side is Side.SHORT])
    return {"kind": "engine", "seed": seed, "E_N": E, "os_ratio": osr,
            "sd": float(sd), "lnp": float(y[-1] - y[0]),
            "tribe_median_ratio": float(k_l / k_s)}


def bm_rows() -> list[dict]:
    rng = np.random.default_rng(0)
    out = []
    for k in range(12):
        r = rng.normal(0, 0.0148, T)
        r[rng.random(T) < 0.03] = 0.0
        y = np.concatenate([[0.0], np.cumsum(r)])
        E, osr = fit_pair(y, 0.0148)
        out.append({"kind": "bm", "path": k, "E_N": E, "os_ratio": osr})
    return out


if __name__ == "__main__":
    rows = bm_rows() if sys.argv[1] == "bm" else [engine_row(int(sys.argv[1]))]
    with open("exponent_scatter.jsonl", "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
            print(row)
