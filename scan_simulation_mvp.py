"""
scan_simulation_mvp.py — parameter scans of the null model.

One scan = many runs at fixed (N, T) x SEEDS, one JSON line per finished
run appended immediately to its results file in eval/runs/ (partial
progress survives interruption). The SCAN selector below chooses the
family:

  "blocks"  The classic 2^4 factorial over the four knobs
                capital_dist in {pareto, normal}
                band_dist    in {fixed,  normal}
                closing      in {clock,  normal}
                size_dist    in {fixed,  normal}
            Arm code = four letters in that order, P/N, F/N, C/N, F/N:
            "PFCF" = the frozen default, "NFNN" = the demo world of the
            __main__ run block, "NNNN" = everything heterogeneous.
            -> scan_results.jsonl

  "bands"   NFNN with asymmetric exit bands: two (tp, sl) pairs each for
            sl > tp, sl = tp, and tp > sl. Does the tilt of the exit
            rules tilt the market?           -> scan_results_bands.jsonl

  "peaky"   Each knob's "normal" arm run at cv = 0.3 and at cv = 0.01
            (a spike: the distribution degenerates to its mean), against
            the PFCF reference. For bands / closing / size the peaky arm
            should statistically reproduce the fixed / clock sibling —
            a continuity check of the block design. Capital has no
            sibling: its peaky arm is the all-agents-equal world (near-
            identical wallets, hence near-identical clocks). Values
            converge to the configuration defaults: capital_dist -> K/(2n),
            band_dist -> 0.01, closing -> d_i/c, size_dist -> 8
                                             -> scan_results_peaky.jsonl

  "qsweep"  NFNN with the order fraction q in {2, 4, 8, 16, 32}: from
            half-the-wealth bites to slivers. -> scan_results_qsweep.jsonl

Every row carries the standard measurements (drift, lock time, tooth
census, wall witnesses, stylized facts, DC scaling); family rows add
"label" and the varied parameters as "x_<name>" fields. Non-blocks scans
print a per-label verdict table at the end. plot_scan.py reads the
blocks results; family results are small enough to read from the table.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "helper"))
OUT = os.path.join(HERE, "eval", "scans")
os.makedirs(OUT, exist_ok=True)

from simulation_mvp import Config, Simulation
from stylized_facts_mvp import compute_facts
from scaling_law_mvp import robust_tick_sd, analyse_scaling


class ScanSimulation(Simulation):
    """Simulation plus per-side wallet recording. Read-only additions in
    the record step — the dynamics (and bit-equality) are untouched."""

    def __init__(self, cfg, run_checks=True):
        try:
            super().__init__(cfg, run_checks=run_checks)  # type: ignore[call-arg]
        except TypeError:      # engine without the toggle: always-checked
            super().__init__(cfg)
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
    lnp = np.abs(np.log(np.asarray(prices) / x_0))
    inside = np.nonzero(lnp <= wall)[0]
    if len(inside) == 0:
        return 0, True                      # locked from the start
    t_lock = int(inside[-1]) + 1
    locked = t_lock < len(lnp)
    return (t_lock if locked else len(lnp)), locked


def wall_metrics(prices, x_0, t_lock, eur_long, btc_short, wall=2.5):
    """The wall, witnessed (dark corners 2 and 6).

    wall_side    : +1 pinned high, -1 pinned low, 0 not locked. To push the
                   price UP you spend EUR (the longs' ammo); DOWN costs BTC
                   (the shorts' ammo) — so the pinned-against pusher is the
                   side whose coin should be empty at the wall.
    ammo_at_lock : that loser side's pushing coin at t_lock, as a fraction
                   of its start. The wall story predicts ~0.
    n_reentries  : how often the path came BACK inside the wall band after
                   first leaving it — 0 means the wall absorbed on first
                   contact; large values mean the wall is metastable."""
    lnp = np.log(np.asarray(prices) / x_0)
    outside = np.abs(lnp) > wall
    if t_lock >= len(lnp) or not outside.any():
        return 0, float("nan"), 0
    side = 1 if float(np.mean(lnp[t_lock:])) > 0 else -1
    if side > 0:
        ammo = eur_long[t_lock - 1] / eur_long[0] if eur_long[0] else float("nan")
    else:
        ammo = btc_short[t_lock - 1] / btc_short[0] if btc_short[0] else float("nan")
    first_out = int(np.argmax(outside))
    later = outside[first_out:]
    reentries = 0
    for i in range(1, len(later)):
        if later[i - 1] and not later[i]:
            reentries += 1
    return side, float(ammo), int(reentries)


def zigzag(lnp, delta=0.5):
    """Directional-change pivots of a log-price path: a pivot is confirmed
    when the path has reversed by >= delta from its running extreme. Returns
    (pivot_indices, swing_sizes) where swing k is |extreme_k - extreme_k+1|.
    Snap-shape agnostic: a crash spread over many ticks is one swing."""
    piv_i = []
    swings = []
    hi = lo = lnp[0]
    hi_i = lo_i = 0
    mode = 0                       # +1 tracking a top, -1 a bottom, 0 unset
    for i in range(1, len(lnp)):
        x = lnp[i]
        if x > hi:
            hi = x
            hi_i = i
        if x < lo:
            lo = x
            lo_i = i
        if mode >= 0 and hi - x >= delta:     # top confirmed, now falling
            piv_i.append(hi_i)
            if len(piv_i) > 1:
                swings.append(abs(lnp[piv_i[-1]] - lnp[piv_i[-2]]))
            mode = -1
            lo = x
            lo_i = i
        elif mode <= 0 and x - lo >= delta:   # bottom confirmed, now rising
            piv_i.append(lo_i)
            if len(piv_i) > 1:
                swings.append(abs(lnp[piv_i[-1]] - lnp[piv_i[-2]]))
            mode = +1
            hi = x
            hi_i = i
    return piv_i, swings


def tooth_stats(prices, x_0, t_lock, delta=0.5):
    """The sawtooth's rhythm and depth, measured in the locked segment with
    the DC zig-zag (delta in e-folds). A tooth = one full cycle (two
    pivots). Returns (n_teeth, mean tooth period in ticks, mean swing).
    Replaces the old one-tick snap counter, which missed cascades spread
    over several ticks (exp4: 3/15 measurable)."""
    lnp = np.log(np.asarray(prices)[t_lock:] / x_0)
    if len(lnp) < 2:
        return 0, float("nan"), float("nan")
    piv, swings = zigzag(lnp, delta)
    n_teeth = max(0, (len(piv) - 1) // 2)
    if len(piv) < 3:
        return n_teeth, float("nan"), float("nan")
    gaps = np.diff(np.asarray(piv, dtype=float))
    return (n_teeth, float(2.0 * np.mean(gaps)),
            float(np.mean(np.asarray(swings, dtype=float))))


# ---------------- edit these ----------------
# ── scan settings (shared by every family) ──────────────────────────────────
N = 500
T = 50_000
SEEDS = (9, 17, 42, 201, 202)
                        # wealth multiset (capital_mirror) — dice 1 neutralized,
                        # direction becomes fair-coin across seeds. False: the
                        # realistic null (independent deals; direction is
                        # deal-determined in Pareto arms). Rows/tags record it.
BAND_SEEDS = (None,)   # extra runs per arm that re-roll ONLY the per-agent
                       # band draw (band_dist="normal" arms; None = the global
                       # seed). Isolates "band luck" from the capital/clock/
                       # size draws. Fixed-band arms ignore it — leave (None,)
                       # unless sweeping, e.g. (None, 1, 2, 3).
# ── which scan family to run ─────────────────────────────────────────────────
SCAN = "peaky"   # "blocks" — all 16 knob combinations (the classic scan)
                  # "bands"  — NFNN with asymmetric exit bands: sl>tp, sl=tp, tp>sl
                  # "peaky"  — each knob's "normal" arm with cv -> 0.01: the
                  #            degenerate N should reproduce its fixed/clock
                  #            sibling. (Capital has no fixed sibling: its
                  #            peaky-N is the all-agents-equal world.)
                  # "qsweep" — NFNN with the order fraction q varied

RESULTS = os.path.join(OUT, "scan_results.jsonl" if SCAN == "blocks"
                       else f"scan_results_{SCAN}.jsonl")

# the non-blocks families: (label, four knobs, extra Config kwargs)
NFNN = ("normal", "fixed", "normal", "normal")
PFCF = ("pareto", "fixed", "clock", "fixed")
FAMILIES: dict = {
    "bands": [
        (f"tp{tp:g}_sl{sl:g}", NFNN, dict(tp=tp, sl=sl))
        for tp, sl in ((0.005, 0.010), (0.010, 0.020),      # sl > tp
                       (0.010, 0.010), (0.020, 0.020),      # sl = tp
                       (0.010, 0.005), (0.020, 0.010))      # tp > sl
    ],
    "peaky": [
        ("ref_PFCF",      PFCF, {}),
        ("cap_N_cv.3",    ("normal", "fixed", "clock", "fixed"), {}),
        ("cap_N_cv.01",   ("normal", "fixed", "clock", "fixed"), dict(capital_cv=0.01)),
        ("band_N_cv.3",   ("pareto", "normal", "clock", "fixed"), {}),
        ("band_N_cv.01",  ("pareto", "normal", "clock", "fixed"), dict(band_cv=0.01)),
        ("close_N_cv.3",  ("pareto", "fixed", "normal", "fixed"), {}),
        ("close_N_cv.01", ("pareto", "fixed", "normal", "fixed"), dict(close_cv=0.01)),
        ("size_N_cv.3",   ("pareto", "fixed", "clock", "normal"), {}),
        ("size_N_cv.01",  ("pareto", "fixed", "clock", "normal"), dict(size_cv=0.01)),
    ],
    "qsweep": [
        (f"q{q}", NFNN, dict(q=q)) for q in (2, 4, 8, 16, 32)
    ],
}
# --------------------------------------------

ARMS = list(itertools.product(("pareto", "normal"),
                              ("fixed", "normal"),
                              ("clock", "normal"),
                              ("fixed", "normal")))


def arm_code(cap: str, band: str, close: str, size: str) -> str:
    """Four-letter arm code, e.g. PFCF (legacy null), NFNF (current
    default), NNNN (all switched)."""
    a = "P" if cap == "pareto" else "N"
    b = "F" if band == "fixed" else "N"
    c = "C" if close == "clock" else "N"
    d = "F" if size == "fixed" else "N"
    return a + b + c + d


def run_one(cap: str, band: str, close: str, size: str, seed: int,
            band_seed=None, **cfg_kwargs) -> dict:
    """One run -> one flat metrics dict (everything the plots need).
    Extra keyword arguments go straight into Config (e.g. step6_order=...,
    size_cv=..., c=..., q=...) and are recorded in the row, so experiment
    drivers can sweep any parameter without touching this file."""
    cfg = Config(n=N, T=T, seed=seed, capital_dist=cap,
                 band_dist=band, closing=close, size_dist=size,
                 band_seed=band_seed,
                 save_csv=False, print_log=False, **cfg_kwargs)
    t0 = time.time()
    sim = ScanSimulation(cfg, run_checks=False).run()
    dt = time.time() - t0

    p = np.asarray(sim.rec_price)
    F = compute_facts(p)
    row = {
        "arm": arm_code(cap, band, close, size),
        "cap": cap, "band": band, "close": close, "size": size, "seed": seed,
        "band_seed": band_seed,
        **cfg_kwargs,
        "n": N, "T": T, "x_0": cfg.x_0, "secs": round(dt, 1),
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
    wall_side, ammo_at_lock, n_reentries = wall_metrics(
        p, cfg.x_0, t_lock, sim.rec_eur_long, sim.rec_btc_short)
    row["wall_side"] = wall_side
    row["ammo_at_lock"] = ammo_at_lock
    row["n_reentries"] = n_reentries
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
    # a feed without DC structure (short, quiet, or locked) -> NaN, not a crash
    try:
        res = analyse_scaling(p)
        row["E_N"] = res["E_N"]
        row["os_ratio"] = res["ratio"]
        row["n_deltas_used"] = int(len(res["D"]))
    except (RuntimeError, SystemExit):
        row["E_N"] = float("nan")
        row["os_ratio"] = float("nan")
        row["n_deltas_used"] = 0
    return row


def main() -> None:
    if SCAN == "blocks":
        todo = [(None, (cap, band, close, size), {}, seed, bs)
                for (cap, band, close, size) in ARMS
                for bs in BAND_SEEDS
                for seed in SEEDS]
    else:
        todo = [(label, knobs, extra, seed, None)
                for (label, knobs, extra) in FAMILIES[SCAN]
                for seed in SEEDS]
    print(f"scan[{SCAN}]: {len(todo)} runs at n={N}, T={T:,}")
    t0 = time.time()
    with open(RESULTS, "w") as f:
        for i, (label, knobs, extra, seed, bs) in enumerate(todo, 1):
            cap, band, close, size = knobs
            row = run_one(cap, band, close, size, seed, band_seed=bs, **extra)
            if label is not None:
                row["label"] = label
                row.update({f"x_{k}": v for k, v in extra.items()})
            f.write(json.dumps(row) + "\n")
            f.flush()
            done = time.time() - t0
            eta = done / i * (len(todo) - i)
            lock_txt = f"lock@{row['t_lock']:,}" if row["locked"] else "no lock"
            if bs is not None:
                lock_txt += f"  bseed={bs}"
            name = label if label is not None else row["arm"]
            print(f"[{i:2d}/{len(todo)}] {name:>14} seed={seed:2d}  "
                  f"{row['secs']:5.1f}s  ln_drift={row['ln_drift']:+.3f}  "
                  f"kurt={row['kurt_m1']:8.1f}  {lock_txt}  "
                  f"(eta {eta/60:.0f} min)")
    print(f"done in {(time.time() - t0)/60:.1f} min -> {RESULTS}")
    if SCAN != "blocks":
        _family_summary()


def _family_summary() -> None:
    """Per-label means over seeds — the family's verdict table."""
    rows = [json.loads(l) for l in open(RESULTS)]
    labels = list(dict.fromkeys(r["label"] for r in rows))
    print(f"\n  {SCAN} summary (mean over {len(SEEDS)} seeds):")
    print(f"  {'label':>14} {'|drift|':>8} {'lock%':>6} {'t_lock':>9} "
          f"{'teeth':>6} {'period':>9} {'kurt':>9} {'E_N':>6}")
    for lb in labels:
        g = [r for r in rows if r["label"] == lb]
        def m(k):
            v = [r[k] for r in g if r.get(k) is not None
                 and np.isfinite(r.get(k, float("nan")))]
            return float(np.mean(v)) if v else float("nan")
        lockpct = 100.0 * sum(r["locked"] for r in g) / len(g)
        print(f"  {lb:>14} {m('abs_drift') if 'abs_drift' in g[0] else abs(m('ln_drift')):>8.2f} "
              f"{lockpct:>5.0f}% {m('t_lock'):>9,.0f} {m('n_snaps'):>6.1f} "
              f"{m('tooth_period'):>9,.0f} {m('kurt_m1'):>9.1f} {m('E_N'):>6.2f}")


if __name__ == "__main__":
    main()
