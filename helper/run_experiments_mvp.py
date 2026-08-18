"""
run_experiments_mvp.py — TEMPORARY driver for the queued experiments.

Runs the open experiments from EVALUATION.md's addenda, each into its own
parameter-named JSONL (so nothing ever overwrites anything), and prints a
grouped comparison per experiment. Delete this file when the questions are
answered.

    exp1_step6ab   : is the tamer re-scan null real? PFCF, shuffled vs
                     array step-6 order, same seeds.           (A/B, gates
                     interpretation of everything else — run first)
    exp2_bandseed  : does Pareto+bands really pin down? PNCF, fresh band
                     luck only, same world otherwise.
    exp3_sizecv    : can big bites recreate the whale book? NFCN with
                     size_cv swept up to near-all-in orders.
    exp4_tooth     : does the tooth period follow the clock? PFCF locked
                     runs with c and q varied one at a time.
    exp5_promise   : does the exit promise pick the direction? PNCF with
                     the own-coin promise vs the exact buy-back, across
                     fresh band draws.        (verdict: 8/8 down vs 8/8
                     up-and-seized — own_coin vindicated, see EVALUATION)
    exp6_cleanmarket: which clean-market switch changes the book's
                     structure? legacy vs stp / ccr / nxg alone vs all
                     three, measuring standing depth, the stop-vs-timer
                     close mix, and drift.

Each experiment writes  results_<name>_n<N>_T<T>.jsonl  next to this file.
Plot any of them afterwards with:

    python scan_plots_mvp.py results_<name>_n<N>_T<T>.jsonl

(figures are named by (n, T) only — keep experiments at distinct (n, T),
or rename the pngs between plot runs).

Edit the blocks below; sizes are set for a laptop, with the single-core
estimate printed before each experiment starts.
"""

from __future__ import annotations

import json
import os
import time

import numpy as np

import scan_mvp as S
from scan_plots_mvp import load_rows, print_table

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- edit these ----------------
RUN = ("exp4_tooth",)   # the fat tooth run, clean arm — the last open experiment   # recommended next: the fat tooth run with the DC
                        # detector (exp1/2/3/5 verdicts are in EVALUATION.md)

EXP1 = dict(N=400, T=30_000, SEEDS=(9, 17, 23, 42))       # the A/B
EXP2 = dict(N=500, T=100_000, SEEDS=(9,),                 # the band sweep
            BAND_SEEDS=(None, 1, 2, 3, 4, 5, 6, 7))
EXP3 = dict(N=400, T=30_000, SEEDS=(9, 17),               # the bite sweep
            SIZE_CVS=(0.1, 0.2, 0.3, 0.5))
EXP4 = dict(N=400, T=150_000, SEEDS=(9, 17, 23, 42),          # the tooth clock
            C_VALUES=(0.002, 0.004, 0.008),   # vary c at q=8; 0.004 = the
                                              # saturation midpoint
            Q_VALUES=(16,))                   # q=4 needs T~250k to grow teeth
                                              # — run it as a separate job
EXP6 = dict(N=150, T=10_000, SEEDS=(9, 17, 23, 42))
EXP5 = dict(N=500, T=60_000, SEEDS=(9,),                  # the promise ablation
            BAND_SEEDS=(None, 1, 2, 3),
            PROMISES=("own_coin", "exact"))
# --------------------------------------------

SECS_PER_UNIT = 60.0 / (400 * 30_000)   # measured: ~60 s at n=400, T=30k


def _open_out(name: str, n: int, T: int):
    """One JSONL per experiment, parameter-named — never overwrites another."""
    path = os.path.join(HERE, f"results_{name}_n{n}_T{T}.jsonl")
    return path, open(path, "w")


def _estimate(n_runs: int, n: int, T: int) -> str:
    """Single-core wall-clock estimate for a batch."""
    mins = n_runs * n * T * SECS_PER_UNIT / 60.0
    return f"{n_runs} runs at n={n}, T={T:,}  (~{mins:.0f} min single-core)"


def _do_runs(name: str, n: int, T: int, jobs: list) -> str:
    """Run a list of (kwargs-for-run_one, label) jobs into the named JSONL.
    Each job's extra kwargs are recorded in its row by run_one itself."""
    S.N, S.T = n, T
    path, f = _open_out(name, n, T)
    print(f"\n=== {name}: {_estimate(len(jobs), n, T)} -> {os.path.basename(path)}")
    t0 = time.time()
    with f:
        for i, (kwargs, label) in enumerate(jobs, 1):
            row = S.run_one(**kwargs)
            f.write(json.dumps(row) + "\n")
            f.flush()
            done = time.time() - t0
            eta = done / i * (len(jobs) - i)
            lock_txt = f"lock@{row['t_lock']:,}" if row["locked"] else "no lock"
            print(f"  [{i:2d}/{len(jobs)}] {label:<22s} {row['secs']:6.1f}s  "
                  f"drift={row['ln_drift']:+.2f}  {lock_txt}  "
                  f"(eta {eta/60:.0f} min)")
    return path


def _grouped(path: str, group_key: str, metrics: tuple) -> None:
    """Print across-seed means of `metrics`, grouped by `group_key` —
    the experiment's verdict table."""
    rows = load_rows(path)
    groups = {}
    for r in rows:
        groups.setdefault(r.get(group_key), []).append(r)
    hdr = f"  {group_key:>12}  n"
    for m in metrics:
        hdr += f" {m:>11}"
    hdr += f" {'wall':>7}"
    print(hdr)
    for key in sorted(groups, key=_group_sort_key):
        sub = groups[key]
        line = f"  {str(key):>12} {len(sub):>2}"
        for m in metrics:
            vals = []
            for r in sub:
                v = abs(r["ln_drift"]) if m == "|drift|" else r.get(m)
                if v is not None and np.isfinite(v):
                    vals.append(v)
            line += f" {np.mean(vals):>11.3f}" if vals else f" {'—':>11}"
        n_up = sum(1 for r in sub if r.get("wall_side") == 1)
        n_dn = sum(1 for r in sub if r.get("wall_side") == -1)
        line += f" {f'{n_up}+/{n_dn}-':>7}"
        print(line)


def _group_sort_key(key):
    """None sorts first, then by value (named function — breakpointable)."""
    if key is None:
        return (0, 0)
    return (1, key)


# ── the experiments ──────────────────────────────────────────────────────────

def exp1_step6ab() -> None:
    """Was the array-order seat weld statistically neutral? Same arm, same
    seeds, only the step-6 iteration order differs."""
    p = EXP1
    jobs = []
    for order in ("shuffled", "array"):
        for seed in p["SEEDS"]:
            kwargs = dict(cap="pareto", band="fixed", close="clock",
                          size="fixed", seed=seed, step6_order=order)
            jobs.append((kwargs, f"PFCF {order} s{seed}"))
    path = _do_runs("exp1_step6ab", p["N"], p["T"], jobs)
    print("\n  verdict — if the two groups' drift/kurtosis separate beyond "
          "seed scatter, the old bug was adding drift and tail mass:")
    _grouped(path, "step6_order", ("|drift|", "kurt_m1", "acf_abs_L1", "t_lock"))


def exp2_bandseed() -> None:
    """Does Pareto+bands pin DOWN because of physics or shared band luck?
    One world, eight fresh band draws."""
    p = EXP2
    jobs = []
    for bs in p["BAND_SEEDS"]:
        for seed in p["SEEDS"]:
            kwargs = dict(cap="pareto", band="normal", close="clock",
                          size="fixed", seed=seed, band_seed=bs)
            jobs.append((kwargs, f"PNCF bseed={bs} s{seed}"))
    path = _do_runs("exp2_bandseed", p["N"], p["T"], jobs)
    print("\n  verdict — the wall column: unanimous '-' = real asymmetry, "
          "mixed = the 20/20 was shared-draw luck:")
    _grouped(path, "band_seed", ("|drift|", "t_lock"))


def exp3_sizecv() -> None:
    """Can heterogeneous BITES recreate the whale book on equal wallets?
    NFCN with the size spread pushed toward all-in orders."""
    p = EXP3
    jobs = []
    for cv in p["SIZE_CVS"]:
        for seed in p["SEEDS"]:
            kwargs = dict(cap="normal", band="fixed", close="clock",
                          size="normal", seed=seed, size_cv=cv)
            jobs.append((kwargs, f"NFCN cv={cv} s{seed}"))
    path = _do_runs("exp3_sizecv", p["N"], p["T"], jobs)
    print("\n  verdict — if kurtosis/sd stay whale-free even at cv=0.5, "
          "'stock not bite' is unconditional:")
    _grouped(path, "size_cv", ("sd_rob", "kurt_m1", "acf_abs_L1", "t_lock"))


def exp4_tooth() -> None:
    """Does the sawtooth period follow the winners' deployment rate
    (~q/(n*c))? Vary c and q one at a time on the legacy null; T long
    enough that runs lock and grow teeth."""
    p = EXP4
    jobs = []
    # every row carries BOTH dials explicitly, so the grouped tables are
    # complete (the row varying q still knows its c, and vice versa)
    for c in p["C_VALUES"]:
        for seed in p["SEEDS"]:
            kwargs = dict(cap="pareto", band="fixed", close="clock",
                          size="fixed", seed=seed, c=c, q=8,
                          self_match="skip", neg_xbar_guard=True)
            jobs.append((kwargs, f"PFCF c={c} q=8 s{seed}"))
    for q in p["Q_VALUES"]:
        for seed in p["SEEDS"]:
            kwargs = dict(cap="pareto", band="fixed", close="clock",
                          size="fixed", seed=seed, c=0.004, q=q,
                          self_match="skip", neg_xbar_guard=True)
            jobs.append((kwargs, f"PFCF c=0.004 q={q} s{seed}"))
    path = _do_runs("exp4_tooth", p["N"], p["T"], jobs)
    print("\n  verdict — tooth_period vs the varied dial (prediction: "
          "period ~ q/(n*c), so 2x c -> half the period, 2x q -> double):")
    _grouped(path, "c", ("tooth_period", "tooth_size", "t_lock"))
    _grouped(path, "q", ("tooth_period", "tooth_size", "t_lock"))


def exp6_cleanmarket() -> None:
    """Which clean-market switch changes the book's structure? Legacy vs
    each switch alone vs all three, measuring standing depth, the close
    mix (stop vs timer initiations), and drift. Separates 'removed a bug'
    from 'changed the market'."""
    import json as _json
    from simulation_mvp import Config, Simulation

    class Probe(Simulation):
        def __init__(self, cfg, run_checks=True):
            try:
                super().__init__(cfg, run_checks=run_checks)
            except TypeError:      # engine without the toggle: always-checked
                super().__init__(cfg)
            self.depth_samples = []
            self.n_sl = 0
        def _step_trigger_stops(self, t, p_prev):
            r = super()._step_trigger_stops(t, p_prev)
            self.n_sl += len(r[0]) + len(r[1])
            return r
        def _timer_due(self, a, t):
            due = super()._timer_due(a, t)
            if due and not a.closing and a.pos_b != 0:
                self.n_timer = getattr(self, "n_timer", 0) + 1
            return due
        def step(self, t):
            r = super().step(t)
            if t % 10 == 0:
                nb = len(self.book._live(self.book.bids))
                na = len(self.book._live(self.book.asks))
                self.depth_samples.append(nb + na)
            return r

    # every arm pins ALL THREE switches explicitly, plus print_log off —
    # immune to whatever the engine's Config defaults happen to be (the
    # all-arms-identical incident: flipped defaults made "legacy" clean)
    def _arm(sm, ccr, nxg):
        return dict(self_match=sm, close_cancels_rest=ccr,
                    neg_xbar_guard=nxg, print_log=False)
    ARMS = [("legacy", _arm("allow", False, False)),
            ("stp",    _arm("skip",  False, False)),
            ("ccr",    _arm("allow", True,  False)),
            ("nxg",    _arm("allow", False, True)),
            ("clean",  _arm("skip",  True,  True))]
    p = EXP6
    path = os.path.join(HERE, f"results_exp6_cleanmarket_n{p['N']}_T{p['T']}.jsonl")
    print(f"\n=== exp6_cleanmarket: {len(ARMS) * len(p['SEEDS'])} runs at "
          f"n={p['N']}, T={p['T']:,} -> {os.path.basename(path)}")
    t0 = time.time()
    with open(path, "w") as f:
        done = 0
        total = len(ARMS) * len(p["SEEDS"])
        for label, kw in ARMS:
            for seed in p["SEEDS"]:
                cfg = Config(n=p["N"], T=p["T"], seed=seed, **kw)
                s = Probe(cfg, run_checks=False).run()
                drift = float(np.log(s.p / cfg.x_0))
                depth = np.asarray(s.depth_samples, float)
                row = dict(arm="EXP6", arm6=label, seed=seed, ln_drift=drift,
                           wall_side=int(np.sign(drift)) if abs(drift) > 2.5 else 0,
                           depth_mean=float(depth.mean()),
                           depth_early=float(depth[:len(depth) // 2].mean()),
                           n_sl=s.n_sl, n_timer=getattr(s, "n_timer", 0),
                           n_trades=len(s.trades_log))
                f.write(_json.dumps(row) + "\n")
                f.flush()
                done += 1
                eta = (time.time() - t0) / done * (total - done)
                print(f"  [{done:2d}/{total}] {label:>6} s{seed:<3} "
                      f"drift={drift:+.2f} depth={row['depth_mean']:.1f} "
                      f"sl={s.n_sl} timer={row['n_timer']} (eta {eta/60:.0f} min)")
    print("\n  verdict — which switch moves depth / close mix / drift:")
    _grouped(path, "arm6", ("|drift|", "depth_mean", "depth_early",
                            "n_sl", "n_timer"))


def exp5_promise() -> None:
    """Is the down-pinning caused by the own-coin promise's flow asymmetry
    (shorts over-buy by e^tp per round trip)? PNCF with the promise made
    flow-symmetric ("exact"), against the own-coin control, across fresh
    band draws. If pinning vanishes under exact, the mechanism is found."""
    p = EXP5
    jobs = []
    for promise in p["PROMISES"]:
        for bs in p["BAND_SEEDS"]:
            for seed in p["SEEDS"]:
                kwargs = dict(cap="pareto", band="normal", close="clock",
                              size="fixed", seed=seed, band_seed=bs,
                              exit_promise=promise)
                jobs.append((kwargs, f"PNCF {promise} bseed={bs} s{seed}"))
    path = _do_runs("exp5_promise", p["N"], p["T"], jobs)
    print("\n  verdict — wall column per promise: own_coin all '-' and "
          "exact mixed => the over-buy is the mechanism:")
    _grouped(path, "exit_promise", ("|drift|", "t_lock"))


if __name__ == "__main__":
    t0 = time.time()
    registry = {
        "exp1_step6ab": exp1_step6ab,
        "exp2_bandseed": exp2_bandseed,
        "exp3_sizecv": exp3_sizecv,
        "exp4_tooth": exp4_tooth,
        "exp5_promise": exp5_promise,
        "exp6_cleanmarket": exp6_cleanmarket,
    }
    for name in RUN:
        registry[name]()
    print(f"\nall done in {(time.time() - t0)/60:.1f} min")
