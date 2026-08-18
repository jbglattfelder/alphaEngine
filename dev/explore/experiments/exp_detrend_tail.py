"""
exp_detrend_tail.py — is the CLOB arm's broken overshoot law a DRIFT or FAT TAILS?

Edit CSV path / run inline; press Run.

THE QUESTION
------------
On the pure-CLOB (impatience) arm, ⟨ω⟩/δ ≈ 8 and P(|r|>4sd) > 0 — both look like
"broken compact support / fat tails." But a *trending* price produces large DC
overshoots WITHOUT any large single steps: the overshoot integrates the drift
over the excursion. The tell is already visible in exp_oscillator_phase: mean
⟨ω⟩ is ~5-8× the MEDIAN overshoot, the signature of a few long one-directional
runs dominating the mean. The median overshoot is ~δ (normal); the mean is a
driftometer.

This script separates the two by removing the mean log-drift and re-measuring.

PREDICTION (stated before running)
----------------------------------
If the CLOB arm has a DRIFT, not fat tails:
  - detrended P(|r|>4sd) collapses toward 0 (matching the batch/home arm), and
  - detrended ⟨ω⟩/δ falls toward ~1.
If it has genuine FAT TAILS:
  - the tail SURVIVES detrending (P(|r|>4sd) stays materially > 0).

FALSIFIER either way: whichever outcome, the other hypothesis is retracted.

NOTE ON WHAT DETRENDING CAN AND CANNOT DO
-----------------------------------------
Removing the *mean* per-step drift is the right control for a CONSTANT tilt. If
the drift is bursty (the relaxation-oscillator flush steps down in bursts), a
constant-drift removal under-corrects and a residual tail may remain that is
still drift, not tails. So: tail collapses -> drift, clean. Tail survives ->
suggestive of tails but check the residual isn't itself autocorrelated in sign
(a sign-ACF > 0 in the residual means leftover trend, not tails). Both diagnostics
are printed.
"""
import csv
import sys
from math import erfc, sqrt

import numpy as np

CSV = "price_feed-42.csv"          # <- your full-run feed (needs a p_int column)
TP = 0.01                       # for the >2*tp readout only


def load_p(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    key = "p_int" if "p_int" in rows[0] else list(rows[0])[0]
    return np.array([float(r[key]) for r in rows])


def tail_report(r, label):
    sd = r.std()
    gt = lambda k: float(np.mean(np.abs(r) > k * sd))
    g = lambda k: erfc(k / sqrt(2))
    print(f"  {label:14} sd={sd:.5f}  "
          f"P>3sd={gt(3):.2e}({gt(3)/g(3):.1f}x)  "
          f"P>4sd={gt(4):.2e}({gt(4)/g(4) if g(4)>0 else 0:.1f}x)  "
          f"P>5sd={gt(5):.2e}  |step|>2tp={np.mean(np.abs(r[np.abs(r)>1e-12])>2*TP):.2%}")


def sign_acf1(r):
    nz = np.sign(r[np.abs(r) > 1e-12])
    if len(nz) < 3:
        return float("nan")
    return float(np.mean(nz[1:] == nz[:-1]))



def local_detrend(y, win):
    """Remove the LOCAL trend: residual = y - rolling median(y, win). A constant
    detrend removes a steady tilt; a rolling median removes a BURSTY one (the
    relaxation-oscillator flush steps down in correlated runs, not at a steady
    rate). If the tail survives THIS, it is not the ratchet."""
    import numpy as np
    n = len(y); half = win // 2
    med = np.empty(n)
    # simple O(n*win) rolling median is fine at 150k; use a strided approach
    from numpy.lib.stride_tricks import sliding_window_view as swv
    pad = np.pad(y, (half, win - half - 1), mode="edge")
    med = np.median(swv(pad, win), axis=1)
    return y - med


def local_report(y, win):
    import numpy as np
    yl = local_detrend(y, win)
    r = np.diff(yl)
    print(f"\n--- LOCAL detrend (rolling median, window={win}) ---")
    print(f"  residual sign-q1 = {sign_acf1(r):.3f}   "
          f"(-> ~0.5 means the bursts are gone; >>0.5 means window too large)")
    tail_report(r, f"local-dt w={win}")
    return yl


def main(path=CSV):
    p = load_p(path)
    y = np.log(p)
    r = np.diff(y)
    mu = r.mean()
    r_dt = r - mu                      # remove constant per-step drift

    print(f"feed: {len(p):,} steps | mean drift/step = {mu:+.3e} "
          f"(total ln-drift {y[-1]-y[0]:+.2f})")
    print(f"continuation q1: raw={sign_acf1(r):.3f}  detrended={sign_acf1(r_dt):.3f}"
          f"   (residual q1 >> 0.5 => leftover trend, not tails)\n")

    print("TAIL, raw vs detrended (ratio = empirical / Gaussian):")
    tail_report(r, "raw")
    tail_report(r_dt, "detrended")

    # overshoot on raw vs detrended, via the committed instrument if available
    try:
        from dc_analysis import dc_log_events
        def os_ratio(series_y, klo=8, khi=32, n=12):
            sd = np.std(np.diff(series_y))
            ds = np.exp(np.linspace(np.log(klo*sd), np.log(khi*sd), n))
            rs = []
            for d in ds:
                ev = dc_log_events(series_y, float(d))
                if len(ev) >= 10:
                    om = np.array([e.overshoot for e in ev])
                    rs.append((d, om.mean()/d, np.median(om)/d, len(ev)))
            return rs
        print("\n⟨ω⟩/δ  and  median-ω/δ,  raw vs detrended:")
        print(f"  {'δ/sd':>5} {'raw <ω>/δ':>10} {'raw med/δ':>10} {'dt <ω>/δ':>10} {'dt med/δ':>10}")
        yr = y
        ydt = np.concatenate([[y[0]], y[0] + np.cumsum(r_dt)])
        raw = os_ratio(yr); dt = os_ratio(ydt)
        for (d1, m1, md1, n1), (d2, m2, md2, n2) in zip(raw, dt):
            print(f"  {d1/np.std(np.diff(yr)):>5.0f} {m1:>10.2f} {md1:>10.2f} "
                  f"{m2:>10.2f} {md2:>10.2f}")
    except Exception as e:
        print(f"\n(overshoot section skipped: {e})")

    # LOCAL detrend: the decisive test. Sweep windows; the right window is the one
    # that drives residual sign-q1 down to ~0.5 (bursts removed) with the LEAST
    # smoothing. Watch the tail across windows: if it collapses as q1 -> 0.5, the
    # "tail" was the ratchet; if it persists at q1 ~ 0.5, it is real.
    print("\nLOCAL-DETREND SWEEP (find the window where sign-q1 -> 0.5, watch the tail):")
    for win in (25, 75, 251, 751):
        local_report(y, win)

    print("\nREAD:")
    print("  detrended P>4sd -> 0 and dt <ω>/δ -> ~1  => DRIFT, not fat tails "
          "(compact support intact once the trend is removed)")
    print("  detrended tail SURVIVES and residual q1 ~ 0.5 => genuine fat tails")
    print("  detrended tail survives BUT residual q1 >> 0.5 => bursty drift, "
          "under-corrected; not established either way")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CSV)
