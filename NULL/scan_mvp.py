"""
scan_mvp.py — parameter scan over the three interchangeable blocks.

Full 2^3 factorial over
    CAPITAL_DIST in {pareto, normal}
    BAND_DIST    in {fixed,  normal}
    CLOSING      in {clock,  normal}
times SEEDS, at fixed (N, T). One JSON line per finished run is appended to
scan_results.jsonl immediately, so partial progress survives interruption.

Arm code: three letters, one per block, default letter capitalised concept:
    P/N = capital Pareto / Normal
    F/N = bands   Fixed  / Normal
    C/N = closing Clock  / Normal
e.g. "PFC" = the frozen null, "NNN" = all three switched.
"""

from __future__ import annotations

import itertools
import json
import os
import time

import numpy as np

import numpy as _np

from simulation_mvp import Config, Simulation
from stylized_facts_mvp import compute_facts
from scaling_law_mvp import robust_tick_sd, analyse_scaling


class ScanSimulation(Simulation):
    """Simulation plus per-side wallet recording. Read-only additions in
    the record step — the dynamics (and bit-equality) are untouched."""

    def __init__(self, cfg, run_checks=True):
        super().__init__(cfg, run_checks=run_checks)
        self.rec_eur_long = []
        self.rec_btc_long = []
        self.rec_eur_short = []
        self.rec_btc_short = []

    def _step_record(self, t):
        """Standard recording, then each side's wallet totals — the direct
        witness of the wealth wall: the pinned side's pushing coin drains."""
        super()._step_record(t)
        el = bl = es = bs = 0.0
        for a in self.agents:
            if not a.alive:
                continue
            if a.is_long:
                el += a.eur
                bl += a.btc
            else:
                es += a.eur
                bs += a.btc
        self.rec_eur_long.append(el)
        self.rec_btc_long.append(bl)
        self.rec_eur_short.append(es)
        self.rec_btc_short.append(bs)


def lock_time(prices, x_0, wall=2.5):
    """When did the run get stuck? The lock time is the first tick after
    which |ln(p/x_0)| NEVER returns inside the wall threshold. Returns
    (t_lock, locked): t_lock = T for a run that never locks."""
    lnp = _np.abs(_np.log(_np.asarray(prices) / x_0))
    inside = _np.nonzero(lnp <= wall)[0]
    if len(inside) == 0:
        return 0, True                      # locked from the start
    t_lock = int(inside[-1]) + 1
    locked = t_lock < len(lnp)
    return (t_lock if locked else len(lnp)), locked


def tooth_stats(prices, x_0, t_lock, snap=0.25):
    """The sawtooth's rhythm and depth, measured in the locked segment.
    A snap is one tick whose |dln p| exceeds `snap` (a quarter e-fold).
    Returns (n_snaps, mean gap between snaps, mean snap size)."""
    lnp = _np.log(_np.asarray(prices)[t_lock:] / x_0)
    if len(lnp) < 2:
        return 0, float("nan"), float("nan")
    dl = _np.abs(_np.diff(lnp))
    idx = _np.nonzero(dl > snap)[0]
    if len(idx) < 2:
        return int(len(idx)), float("nan"), float("nan")
    gaps = _np.diff(idx)
    return int(len(idx)), float(_np.mean(gaps)), float(_np.mean(dl[idx]))

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- edit these ----------------
N = 400
T = 30_000
SEEDS = (9, 17, 23, 42)
OUT = os.path.join(HERE, "scan_results.jsonl")
# --------------------------------------------

ARMS = list(itertools.product(("pareto", "normal"),
                              ("fixed", "normal"),
                              ("clock", "normal")))


def arm_code(cap: str, band: str, close: str) -> str:
    """Three-letter arm code, e.g. PFC (the null), NNN (all switched)."""
    a = "P" if cap == "pareto" else "N"
    b = "F" if band == "fixed" else "N"
    c = "C" if close == "clock" else "N"
    return a + b + c


def run_one(cap: str, band: str, close: str, seed: int) -> dict:
    """One run -> one flat metrics dict (everything the plots need)."""
    cfg = Config(n=N, T=T, seed=seed, capital_dist=cap,
                 band_dist=band, closing=close)
    t0 = time.time()
    sim = ScanSimulation(cfg, run_checks=False).run()
    dt = time.time() - t0

    p = np.asarray(sim.rec_price)
    F = compute_facts(p)
    row = {
        "arm": arm_code(cap, band, close),
        "cap": cap, "band": band, "close": close, "seed": seed,
        "n": N, "T": T, "secs": round(dt, 1),
        "p_final": float(p[-1]),
        "ln_drift": float(np.log(p[-1] / cfg.x_0)),
        "sd_raw": F["sd"],
        "sd_rob": float(robust_tick_sd(p)),
        "zero_frac": F["zero_frac"],
        "acf_abs_L1": float(F["acf_abs"][0]),
        "acf_abs_L10": float(F["acf_abs"][2]),
        "acf_abs_L100": float(F["acf_abs"][5]),
        "kurt_m1": F["kurt"][1],
        "kurt_m125": F["kurt"][125],
        "alive_frac": (sim.rec_alive_long[-1] + sim.rec_alive_short[-1]) / (2 * N),
        "n_trades": len(sim.trades_log),
        # coarse price path for the panel figure (500 points is plenty)
        "path": [float(x) for x in p[:: max(1, len(p) // 500)]],
    }
    # phase metrics: when the run locked onto the wall, and the sawtooth
    t_lock, locked = lock_time(p, cfg.x_0)
    n_snaps, tooth_period, tooth_size = tooth_stats(p, cfg.x_0, t_lock)
    row["t_lock"] = t_lock
    row["locked"] = bool(locked)
    row["lock_frac"] = t_lock / len(p)          # fraction of run spent wandering
    row["n_snaps"] = n_snaps
    row["tooth_period"] = tooth_period
    row["tooth_size"] = tooth_size
    # the wealth wall, witnessed: the pinned side's pushing coin at the end,
    # as a fraction of its start (longs push with EUR, shorts with BTC)
    step = max(1, len(sim.rec_eur_long) // 500)
    row["eur_long_path"] = [float(x) for x in sim.rec_eur_long[::step]]
    row["btc_short_path"] = [float(x) for x in sim.rec_btc_short[::step]]
    row["eur_long_frac_end"] = float(sim.rec_eur_long[-1] / sim.rec_eur_long[0])         if sim.rec_eur_long[0] else float("nan")
    row["btc_short_frac_end"] = float(sim.rec_btc_short[-1] / sim.rec_btc_short[0])         if sim.rec_btc_short[0] else float("nan")
    # scaling laws can fail on a short/quiet feed -> record NaN, not a crash
    try:
        res = analyse_scaling(p)
        row["E_N"] = res["E_N"]
        row["os_ratio"] = res["ratio"]
        row["n_deltas_used"] = int(len(res["D"]))
    except SystemExit:
        row["E_N"] = float("nan")
        row["os_ratio"] = float("nan")
        row["n_deltas_used"] = 0
    return row


def main() -> None:
    todo = [(cap, band, close, seed)
            for (cap, band, close) in ARMS for seed in SEEDS]
    print(f"scan: {len(ARMS)} arms x {len(SEEDS)} seeds = {len(todo)} runs "
          f"at n={N}, T={T:,}")
    t0 = time.time()
    with open(OUT, "w") as f:
        for i, (cap, band, close, seed) in enumerate(todo, 1):
            row = run_one(cap, band, close, seed)
            f.write(json.dumps(row) + "\n")
            f.flush()
            done = time.time() - t0
            eta = done / i * (len(todo) - i)
            lock_txt = f"lock@{row['t_lock']:,}" if row["locked"] else "no lock"
            print(f"[{i:2d}/{len(todo)}] {row['arm']} seed={seed:2d}  "
                  f"{row['secs']:5.1f}s  ln_drift={row['ln_drift']:+.3f}  "
                  f"kurt={row['kurt_m1']:8.1f}  {lock_txt}  "
                  f"(eta {eta/60:.0f} min)")
    print(f"done in {(time.time() - t0)/60:.1f} min -> {OUT}")


if __name__ == "__main__":
    main()
