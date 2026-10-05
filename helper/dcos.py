"""
dcos.py — directional-change (DC) and overshoot (OS) statistics in event time.

Counts, for each threshold δ, how often a log-price series reverses by δ
from its last extreme (the DC count N(δ)) and how far each move ran on
after the reversal was confirmed (the overshoot ω, measured from the
confirming print as in Glattfelder et al. 2011; the confirming print's own
excess over the threshold level is reported separately). On Brownian motion
N ∝ δ^-2 and ⟨ω⟩ = δ; FX gives N ∝ δ^-1.75 and ⟨ω⟩ ≈ δ
(Guillaume et al. 1997, Glattfelder et al. 2011).

Usage:
    python dcos.py tape_<tag>_events.npz            # event tape (every print)
    python dcos.py tape_<tag>.npy --tick            # tick tape (last print per tick)
    python dcos.py EVENTS --lo 1000 --hi 400000     # restrict to a tick range
    python dcos.py EVENTS --dmin 0.004 --dmax 0.08 --nd 12
    python dcos.py --selftest                       # Brownian check: E_N -> -2, <w>/d -> 1

Prints N(δ), ⟨ω⟩/δ, median ω/δ, the local log-log slope between
neighbouring thresholds, and an OLS fit of log N on log δ over the
thresholds with N ≥ nmin.

Requires numpy; uses numba if installed (131M prints in ~1 min), otherwise
falls back to pure Python (slow: use --tick or a short --hi).
"""
from __future__ import annotations
import argparse, sys
import numpy as np

try:
    from numba import njit
except ImportError:                       # pragma: no cover
    def njit(*a, **k):
        def wrap(f): return f
        return wrap if not (a and callable(a[0])) else a[0]


@njit(cache=True)
def dc_os(lp, d):
    """One pass over a log-price array at threshold d.

    mode +1: last DC was up   (tracking the running max, waiting for a drop of d)
    mode -1: last DC was down (tracking the running min, waiting for a rise of d)
    mode  0: start — track both until one side has moved d.

    Returns (n_dc, sum_os, n_os, os_values, sum_dc_excess).
    The overshoot of a segment is measured from the DC CONFIRMATION PRICE
    (the print that completed the move of d from the extreme) to the
    extreme that closed the segment — the Glattfelder et al. (2011)
    convention, the one FX laws are stated in. The confirming print itself
    usually lies beyond the threshold level ext*e^d; that DC EXCESS is
    returned separately (total move = d + excess + overshoot). On fine
    data the excess is ~0; on coarse prints it is not."""
    hi = lp[0]; lo = lp[0]; ref = lp[0]; conf = lp[0]; mode = 0; n = 0
    os_sum = 0.0; os_n = 0; exc_sum = 0.0
    os_vals = np.empty(len(lp) // 2 + 1)
    for i in range(len(lp)):
        x = lp[i]
        if mode == 0:
            if x > hi: hi = x
            if x < lo: lo = x
            if hi - x >= d:
                mode = -1; ref = hi; conf = x; lo = x; n += 1
            elif x - lo >= d:
                mode = 1; ref = lo; conf = x; hi = x; n += 1
        elif mode == 1:
            if x > hi: hi = x
            if hi - x >= d:
                o = hi - conf; os_vals[os_n] = o; os_sum += o; os_n += 1
                exc_sum += (conf - ref) - d
                mode = -1; ref = hi; conf = x; lo = x; n += 1
        else:
            if x < lo: lo = x
            if x - lo >= d:
                o = conf - lo; os_vals[os_n] = o; os_sum += o; os_n += 1
                exc_sum += (ref - conf) - d
                mode = 1; ref = lo; conf = x; hi = x; n += 1
    return n, os_sum, os_n, os_vals[:os_n], exc_sum


def analyse(lp: np.ndarray, deltas: np.ndarray, nmin: int = 100) -> dict:
    N = []; Om = []; Omed = []; Ex = []
    for d in deltas:
        n, s, k, ov, ex = dc_os(lp, float(d))
        N.append(n); Om.append(s / k / d if k else np.nan)
        Omed.append(float(np.median(ov)) / d if k else np.nan)
        Ex.append(ex / k / d if k else np.nan)
    N = np.array(N, float); Om = np.array(Om); Omed = np.array(Omed); Ex = np.array(Ex)
    sel = N >= nmin
    if sel.sum() >= 3:
        slope, icpt = np.polyfit(np.log(deltas[sel]), np.log(N[sel]), 1)
        r2 = np.corrcoef(np.log(deltas[sel]), np.log(N[sel]))[0, 1] ** 2
    else:
        slope = icpt = r2 = np.nan
    return dict(delta=deltas, N=N, os_mean=Om, os_median=Omed, dc_excess=Ex,
                E_N=slope, R2=r2, fit_mask=sel,
                local_slope=np.diff(np.log(np.maximum(N, 1))) / np.diff(np.log(deltas)))


def report(res: dict, label: str, n_points: int) -> None:
    D = res['delta']
    print(f'{label}: {n_points:,} points')
    print('  δ%        :', ' '.join(f'{100*d:7.2f}' for d in D))
    print('  N_DC      :', ' '.join(f'{int(n):7d}' for n in res['N']))
    print('  ⟨ω⟩/δ     :', ' '.join(f'{o:7.2f}' for o in res['os_mean']))
    print('  median ω/δ:', ' '.join(f'{o:7.2f}' for o in res['os_median']))
    print('  DC excess/δ:', ' '.join(f'{o:7.2f}' for o in res['dc_excess']), '  (confirming print beyond ext·e^δ)')
    print('  local E_N :', '        ' + ' '.join(f'{s:7.2f}' for s in res['local_slope']))
    m = res['fit_mask']
    print(f"  OLS over N>={int(res['N'][m].min()) if m.any() else '-'} ({m.sum()} points, "
          f"δ {100*D[m].min():.2f}–{100*D[m].max():.2f}%): E_N = {res['E_N']:.2f}, R² = {res['R2']:.4f}; "
          f"mean ⟨ω⟩/δ there {np.nanmean(res['os_mean'][m]):.2f}")


def selftest() -> None:
    rng = np.random.default_rng(0)
    b = np.cumsum(rng.standard_normal(5_000_000)) * 1e-3
    res = analyse(b, np.geomspace(0.005, 0.04, 6), nmin=100)
    report(res, 'Brownian motion (expect E_N ≈ -2, ⟨ω⟩/δ ≈ 1)', len(b))
    x = 0.1 * np.sin(np.linspace(0, 20 * np.pi, 100_000))
    n, s, k, _, _ = dc_os(x, 0.05)
    print(f'sine, amplitude 0.1, 10 periods, δ=0.05: {n} DCs (expect 20–21), ⟨ω⟩/δ = {s/k/0.05:.2f} (expect ≈ 2.9)')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', nargs='?', help='tape_<tag>_events.npz (default) or tape_<tag>.npy with --tick')
    ap.add_argument('--tick', action='store_true', help='input is a tick tape (.npy of last prices)')
    ap.add_argument('--lo', type=int, default=1000, help='first tick to include (default 1000: skips the bootstrap)')
    ap.add_argument('--hi', type=int, default=None, help='last tick to include')
    ap.add_argument('--dmin', type=float, default=0.0005); ap.add_argument('--dmax', type=float, default=0.05)
    ap.add_argument('--nd', type=int, default=15, help='number of log-spaced thresholds')
    ap.add_argument('--nmin', type=int, default=100, help='min DC count for a threshold to enter the fit')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.path:
        ap.error('give a tape path or --selftest')
    if a.tick:
        p = np.load(a.path); hi = a.hi if a.hi is not None else len(p)
        lp = np.log(p[a.lo:hi]).astype(np.float64); label = f'{a.path} (tick tape, ticks {a.lo}–{hi})'
    else:
        e = np.load(a.path); t = e['t']; m = t > a.lo
        if a.hi is not None: m &= t <= a.hi
        lp = np.log(e['p'][m]).astype(np.float64); label = f'{a.path} (event tape, ticks {a.lo}–{a.hi or int(t.max())})'
    res = analyse(lp, np.geomspace(a.dmin, a.dmax, a.nd), a.nmin)
    report(res, label, len(lp))


if __name__ == '__main__':
    main()
