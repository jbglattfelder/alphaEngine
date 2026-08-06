"""
verify_mvp.py — prove the MVP rebuild IS the frozen null.

Runs the LEGACY engine (config.py / simulation.py / book_coin.py, shipped
defaults) and the MVP engine (simulation_mvp.py) on the same two
configurations:

    default        : n=150, T=100_000, seed=9   (the run_single.py block)
    default, n=2   : n=2,   T=100_000, seed=9   (the mechanism naked)

and asserts, for every recorded tick, BIT-EQUALITY of:

    price, crossed flag, matched BTC volume, book depth counts (both
    sides), alive counts (both sides), and side PnL.

Bit-equal series => bit-equal dashboards: every pixel of the legacy
dashboard is a function of these series (plus the final agent state, which
the PnL equality pins). A side-by-side price figure is written for the
eyeball check: verify_default.png, verify_n2.png.
"""

from __future__ import annotations

import time

import numpy as np

from config import Config as LegacyConfig
from simulation import Simulation as LegacySimulation
import simulation_mvp as mvp


def run_legacy(n: int, T: int, seed: int):
    """One legacy run at the shipped run_single defaults."""
    cfg = LegacyConfig(n=n, T=T, seed=seed, f=0.5, c=0.004, tp=0.01, sl=0.01,
                       close_mode="home", sl_mode="market",
                       x_accounting=True, log_thresholds=True,
                       symmetric_solvency=True, entry_mode="rest",
                       hold_fires_close=True, book_mode="coin",
                       exit_promise="own_coin")
    t0 = time.time()
    sim = LegacySimulation(cfg, run_checks=True).run()
    dt = time.time() - t0
    h = sim.recorder.history
    series = {
        "price": np.asarray(h["p_int"]),
        "crossed": np.asarray(h["crossed"]),
        "matched_btc": np.asarray(h["matched_btc"]),
        "book_bids": np.asarray(h["book_bids"]),
        "book_asks": np.asarray(h["book_asks"]),
        "alive_long": np.asarray(h["alive_long"]),
        "alive_short": np.asarray(h["alive_short"]),
        "pnl_long": np.asarray(h["pnl_long"]),
        "pnl_short": np.asarray(h["pnl_short"]),
    }
    return series, dt


def run_mvp(n: int, T: int, seed: int):
    """One MVP run at its defaults (which ARE the frozen null)."""
    cfg = mvp.Config(n=n, T=T, seed=seed)
    t0 = time.time()
    sim = mvp.Simulation(cfg, run_checks=True).run()
    dt = time.time() - t0
    series = {
        "price": np.asarray(sim.rec_price),
        "crossed": np.asarray(sim.rec_crossed),
        "matched_btc": np.asarray(sim.rec_matched_btc),
        "book_bids": np.asarray(sim.rec_book_bids),
        "book_asks": np.asarray(sim.rec_book_asks),
        "alive_long": np.asarray(sim.rec_alive_long),
        "alive_short": np.asarray(sim.rec_alive_short),
        "pnl_long": np.asarray(sim.rec_pnl_long),
        "pnl_short": np.asarray(sim.rec_pnl_short),
    }
    return series, dt


def compare(name: str, legacy: dict, new: dict) -> bool:
    """Assert bit-equality series by series; report per-series verdicts."""
    all_ok = True
    print(f"\n[{name}] series comparison (bit-exact):")
    for key in legacy:
        a = legacy[key]
        b = new[key]
        same_len = len(a) == len(b)
        equal = same_len and np.array_equal(a, b)
        status = "OK " if equal else "FAIL"
        print(f"  [{status}] {key:12s} len {len(a)}/{len(b)}", end="")
        if equal:
            print()
        else:
            all_ok = False
            if same_len:
                d = np.nonzero(a != b)[0]
                i = int(d[0])
                print(f"  first diff at index {i}: legacy={a[i]!r} mvp={b[i]!r}")
            else:
                print("  (length mismatch)")
    return all_ok


def side_by_side(name: str, legacy: dict, new: dict, path: str) -> None:
    """The eyeball check: legacy price vs MVP price, one figure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    ax1.plot(legacy["price"], color="#2563EB", lw=0.6)
    ax1.set_title(f"{name} — LEGACY engine price")
    ax1.set_xlabel("tick")
    ax1.set_ylabel("BTC/EUR (EUR per BTC)")
    ax2.plot(new["price"], color="#15803D", lw=0.6)
    ax2.set_title(f"{name} — MVP engine price")
    ax2.set_xlabel("tick")
    diff = float(np.max(np.abs(legacy["price"] - new["price"])))
    fig.suptitle(f"max |Δprice| over the run = {diff!r}", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    T = 100_000
    SEED = 9
    verdicts = []
    for label, n, png in (("default n=150", 150, "verify_default.png"),
                          ("default n=2", 2, "verify_n2.png")):
        legacy, dt_l = run_legacy(n, T, SEED)
        new, dt_m = run_mvp(n, T, SEED)
        print(f"\n=== {label} ===  legacy {dt_l:.1f}s | mvp {dt_m:.1f}s")
        ok = compare(label, legacy, new)
        side_by_side(label, legacy, new, png)
        verdicts.append((label, ok))
    print("\n" + "=" * 50)
    for label, ok in verdicts:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if all(ok for _, ok in verdicts):
        print("MVP == frozen null, to the bit. Dashboards unchanged by construction.")
    else:
        raise SystemExit("divergence found — MVP is NOT the frozen null")
