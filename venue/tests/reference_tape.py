"""The engine's own tick tape for the GUI cross-check (venue/e2e/tape.spec.js).

Runs the BARE engine (simulation_mvp.Simulation, no venue wrapper, natively
in CPython) for n = 2 per side on both arms, and records:
  - sha256 of the tick tape: the price after every tick 0..T as IEEE-754
    float64 big-endian hex, concatenated (bit-exact, format-free)
  - every 1000th price (hex), to locate a divergence
  - the total printed volume (RCC)

    python venue/tests/reference_tape.py     # rewrites reference_tape_n2.json

test_venue.py::test_reference_tape_is_the_engines checks the committed file
against a fresh run, so the browser is always compared with the engine."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "py"))

from simulation_mvp import Simulation          # noqa: E402  the frozen engine
from venue_wrapper import make_config          # noqa: E402  the GUI's Config

CASES = [dict(arm="NNNN", n=2, seed=9, T=20_000), dict(arm="PFCF", n=2, seed=9, T=20_000)]
PATH = os.path.join(HERE, "reference_tape_n2.json")


def fhex(x: float) -> str:
    return struct.pack(">d", float(x)).hex()


def engine_tape(arm: str, n: int, seed: int, T: int) -> dict:
    cfg = make_config(n=n, K=1_000_000.0, tp=0.01, sl=0.01, c=0.004, q=8, seed=seed, arm=arm)
    sim = Simulation(cfg)
    prices = [cfg.x_0]
    for t in range(1, T + 1):
        if not sim.step(t):
            break
    prices += sim.rec_price
    hexes = [fhex(p) for p in prices]
    return dict(arm=arm, n=n, seed=seed, T=T, ticks=len(prices) - 1,
                sha256=hashlib.sha256("".join(hexes).encode()).hexdigest(),
                every_1000=hexes[::1000], final_price=prices[-1],
                volume=float(sum(sim.rec_matched_btc)), trades=len(sim.trades_log))


def build() -> dict:
    return {"engine": "simulation_mvp.py (tag v1.0-paper)", "K": 1_000_000.0,
            "tp": 0.01, "sl": 0.01, "c": 0.004, "q": 8,
            "cases": [engine_tape(**c) for c in CASES]}


if __name__ == "__main__":
    with open(PATH, "w") as f:
        json.dump(build(), f, indent=1)
        f.write("\n")
    print("wrote", PATH)
