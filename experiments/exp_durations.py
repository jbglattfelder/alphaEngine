"""
exp_durations.py — the TIME laws: are DC durations structurally thin-tailed?

THE QUESTION
------------
HANDOFF-v4 measured the price-SHAPE laws (N(δ), ⟨ω⟩) but none of the temporal
scaling laws. The engine's clock is quasi-deterministic (firing periods d/c,
narrow position lifetimes); real FX inter-event times are heavy-tailed. If a
threshold-clock population cannot generate scale-free waiting, that is a third
entry in §0's "structurally unreachable" column, alongside fat tails (§2.5) and
the overshoot law (§2.4) — and a constraint on level 1: any added actor must
also break the clock's regularity or the temporal laws stay dead.

PREDICTIONS — STATED BEFORE THE RUN
-----------------------------------
P1: engine total-move durations (DCEvent.n_ticks_tm) are THINNER-tailed than
    Brownian-motion durations at matched delta-in-sd units and feed length:
    P(tau > 5*median) engine < BM, at every delta tested.
P2: the engine duration CV (sd/mean) < BM's.
FALSIFIER: engine tail >= BM tail at any delta -> the clock does NOT regularise
    waiting times; retract the "structurally unreachable" framing for time laws.

Gauge: log (dc_log_events), per HANDOFF-v4 §3 gotcha 3. delta grid in multiples
of tick-sd with the >=8x floor (gotcha 2). BM control: same length, sigma matched
to the engine feed's nonzero-step sd, simulated at the same zero-step density so
the tick clock is comparable.

Usage: python3 exp_durations.py            (runs engine + BM, prints the table)
"""
import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder
from dc_analysis import dc_log_events


def duration_stats(y: np.ndarray, delta: float):
    ev = dc_log_events(y, delta)[1:]          # drop the init artifact
    if len(ev) < 12:
        return None
    tau = np.array([e.n_ticks_tm for e in ev], float)
    med = float(np.median(tau))
    return {
        "n_events": len(ev),
        "median": med,
        "cv": float(tau.std() / tau.mean()),
        "p_tail": float((tau > 5 * med).mean()),
        "max_over_med": float(tau.max() / med),
    }


def main() -> None:
    # engine feed: home arm, the v4 workhorse config
    cfg = Config(n=150, c=0.004, T=32_000, seed=1, close_mode="home",
                 sl_mode="market", tp=0.01, sl=0.01)
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False).run()
    p = np.array(sim.recorder.series("p_int"))
    y = np.log(p)
    r = np.diff(y)
    nz = r[r != 0]
    sd, zero_frac = nz.std(), (r == 0).mean()
    print(f"engine: {len(p)} ticks, sd(nonzero)={sd:.5f}, zero-frac={zero_frac:.2f}, "
          f"lnp={y[-1]-y[0]:+.2f}")

    # BM control: matched sigma on trading ticks, matched zero-step density,
    # same length — the clock structure is the only thing that differs.
    rng = np.random.default_rng(0)
    steps = rng.normal(0.0, sd, size=len(r))
    mask = rng.random(len(r)) < zero_frac
    steps[mask] = 0.0
    y_bm = np.concatenate([[0.0], np.cumsum(steps)])

    print(f"\n{'delta/sd':>8} {'arm':>6} {'events':>7} {'median':>7} {'CV':>6} "
          f"{'P(t>5med)':>10} {'max/med':>8}")
    for k in (8, 16, 32):
        delta = k * sd
        for name, feed in (("engine", y), ("BM", y_bm)):
            s = duration_stats(feed, delta)
            if s is None:
                print(f"{k:>8} {name:>6}   too few events")
                continue
            print(f"{k:>8} {name:>6} {s['n_events']:>7} {s['median']:>7.0f} "
                  f"{s['cv']:>6.2f} {s['p_tail']:>10.3f} {s['max_over_med']:>8.1f}")


if __name__ == "__main__":
    main()
