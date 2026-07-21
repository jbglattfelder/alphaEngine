"""
test_benchmarks.py — the paranoia harness. Exact-outcome regression benchmarks.

WHAT THIS IS
------------
A frozen set of bit-exact outcomes covering every engine path (home baseline,
quantity treatment, sl_mode arms, convention mixing + evolution, TP clustering,
scale invariance, and one REFERENCE.md row), validated in about a minute. The
model is chaotic and bit-reproducible across machines (HANDOFF §3b/§8), so the
correct comparison is EXACT equality: any deviation, however small, means the
dynamics changed. There is no tolerance because there is nothing to tolerate.

USAGE
-----
    python3 test_benchmarks.py            # validate against benchmarks.json
    python3 test_benchmarks.py --update   # re-freeze after an INTENTIONAL change
    pytest test_benchmarks.py             # same checks, pytest-style

RULES
-----
- A red result after a "refactor" means the refactor changed the model. Find out
  why before touching this file.
- --update is a DECISION, not a fix. Every re-freeze must be named in the commit
  message with the change that justifies it (the REFERENCE.md re-baseline of
  2026-07-15 is the template).
- Keep the suite fast. A benchmark nobody runs protects nobody.
"""
import json
import math
import os
import sys

BENCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmarks.json")


def _sig(cfg_kwargs: dict, extra: dict | None = None) -> dict:
    """Run one config; return the exact-outcome signature."""
    from config import Config
    from simulation import Simulation
    from agents import Side

    sim = Simulation(Config(**cfg_kwargs), run_checks=True).run()
    rp = sim.p_int ** 0.5
    L = sum(a.eur / rp + a.btc * rp for a in sim.pop.agents if a.side is Side.LONG)
    S = sum(a.eur / rp + a.btc * rp for a in sim.pop.agents if a.side is Side.SHORT)
    out = {
        "p_final": repr(float(sim.p_int)),
        "x_share": repr(float(L / (L + S))),
        "n_round_trips": len(sim.trade_log),
        "stranded": sum(1 for a in sim.pop.agents if abs(a.pos.b) > 1e-9 and a.closing),
    }
    if extra:
        out.update(extra)
    return out


# name -> config kwargs. Small T: these guard DYNAMICS, not statistics.
CASES = {
    "home_default_n150":      dict(n=150, T=4000, seed=42, c=0.004),
    "quantity_treatment":     dict(n=150, T=4000, seed=42, c=0.004, close_mode="quantity"),
    "sl_limit_arm":           dict(n=150, T=2000, seed=7, c=0.004,
                                   close_mode="quantity", sl_mode="limit"),
    "sl_wait_arm":            dict(n=150, T=2000, seed=7, c=0.004,
                                   close_mode="quantity", sl_mode="wait"),
    "conv_mixed_evolve":      dict(n=60, T=1500, seed=3, c=0.02,
                                   conv_mode="mixed", evolve=True, evolve_every=400),
    "tp_hierarchy":           dict(n=150, T=2000, seed=1, c=0.004, tp_sig_hier=True,
                                   tp=0.01, sl=0.01),
    "entry_rest_v5":          dict(n=150, T=2000, seed=1, c=0.004, entry_mode="rest"),
    "rest_impatience":        dict(n=150, T=2000, seed=1, c=0.004, entry_mode="rest",
                                   hold_fires_close=True),
    "reference_row_f05_s1":   dict(f=0.5, c=0.004, T=6000, seed=1, x_accounting=True,
                                   log_thresholds=True, symmetric_solvency=True),
}


def scale_invariance_check() -> dict:
    """p/x_0 bit-identity across powers of two — the strongest invariant (§3e)."""
    import numpy as np
    from config import Config
    from simulation import Simulation
    from analysis import Recorder

    def traj(x0):
        sim = Simulation(Config(n=60, T=2000, seed=5, c=0.004, x_0=x0),
                         recorder=Recorder(), run_checks=False).run()
        return np.array(sim.recorder.series("p_int")) / x0

    ref = traj(1.0)
    return {"identical_2pm6": bool(np.array_equal(ref, traj(2.0 ** -6))),
            "identical_2p4": bool(np.array_equal(ref, traj(2.0 ** 4)))}


def compute_all() -> dict:
    res = {name: _sig(kw) for name, kw in CASES.items()}
    res["scale_invariance"] = scale_invariance_check()
    return res


def validate() -> int:
    with open(BENCH) as f:
        frozen = json.load(f)
    got = compute_all()
    fails = []
    for name, want in frozen.items():
        have = got.get(name)
        if have != want:
            fails.append((name, want, have))
    for name, want, have in fails:
        print(f"[FAIL] {name}")
        for k in want:
            if want[k] != (have or {}).get(k):
                print(f"       {k}: expected {want[k]!r}  got {(have or {}).get(k)!r}")
    ok = len(frozen) - len(fails)
    print(f"\n{ok}/{len(frozen)} benchmarks bit-exact"
          + ("" if not fails else "  — THE DYNAMICS CHANGED. Intentional? --update and say so in the commit."))
    return 1 if fails else 0


# pytest hooks
def test_benchmarks():
    assert validate() == 0


if __name__ == "__main__":
    if "--update" in sys.argv:
        res = compute_all()
        with open(BENCH, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
        print(f"re-froze {len(res)} benchmarks -> {BENCH}")
        print("Name the justifying change in the commit message.")
    else:
        sys.exit(validate())
