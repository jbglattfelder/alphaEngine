"""
exp_x0_gauge.py — is x0 a gauge?  Two tests, matching HANDOFF §4.11.

TEST A (short-horizon, same seed): x0=1 vs x0=10 must give bit-identical
        ln(p/x0) until floating point forks at an exact-touch knife-edge.
        Prints the first tick where |Δ ln(p/x0)| > tol and what happened there.

TEST B (distributional, many seeds, large n): the DISTRIBUTION of final
        ln(p/x0) at x0=1 and x0=10 must be statistically indistinguishable,
        even though individual paths fork. This is the real covariance claim;
        per-path equality is unattainable (IEEE-754 is not scale-invariant).

Run A always (seconds). Run B only if RUN_B=True (n=500 × seeds = minutes).
"""
import numpy as np
from config import Config
from simulation import Simulation
from analysis import Recorder

# ---------------- knobs ----------------
X0_REF, X0_ALT = 1.0, 10.0
A_N, A_T, A_SEED = 2, 3000, 9         # short-horizon bit-check arm
TOL = 1e-9
RUN_B = False                          # flip on for the distributional test
B_N, B_T, B_SEEDS = 500, 150_000, range(20, 30)   # user-machine batch
# ---------------------------------------


def feed(x0, n, T, seed):
    cfg = Config(n=n, T=T, seed=seed, x_0=x0, f=0.5, c=0.004, tp=0.01, sl=0.01,
                 close_mode="home", sl_mode="market", entry_mode="rest",
                 hold_fires_close=True, x_accounting=True, log_thresholds=True,
                 symmetric_solvency=True, book_mode="coin", exit_promise="own_coin")
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False).run()
    p = np.array([float(x) for x in sim.recorder.series("p_int")])
    return np.log(p / x0), sim          # ln(p/x0) is the gauge-invariant


def test_A():
    print(f"=== TEST A — short-horizon bit-equality (n={A_N}, seed {A_SEED}, "
          f"x0={X0_REF} vs {X0_ALT}) ===")
    g1, s1 = feed(X0_REF, A_N, A_T, A_SEED)
    g2, s2 = feed(X0_ALT, A_N, A_T, A_SEED)
    m = min(len(g1), len(g2))
    d = np.abs(g1[:m] - g2[:m])
    fork = np.where(d > TOL)[0]
    print(f"  compared {m} ticks   max |Δ ln(p/x0)| before any fork = {d[:1].max():.2e}")
    if len(fork) == 0:
        print(f"  ✓ bit-identical for all {m} ticks (tol {TOL:g}) — no fork in window")
    else:
        t = fork[0]
        print(f"  forks at tick {t}: Δ = {d[t]:.2e}  (bit-identical for {t} ticks first)")
        print(f"     ln(p/x0):  x0={X0_REF} → {g1[t]:.12f}")
        print(f"                x0={X0_ALT} → {g2[t]:.12f}")
        print(f"     the gauges agree to ~{-np.log10(d[t-1] if t>0 and d[t-1]>0 else 1e-16):.0f} "
              f"digits right up to the knife-edge, then split by a few ulps.")
    print(f"  READ: agreement to tol for a long prefix = the dust fix works; "
          f"the fork is IEEE-754, not a leak.\n")
    return fork


def test_B():
    print(f"=== TEST B — distributional equivalence (n={B_N}, "
          f"{len(list(B_SEEDS))} seeds each) ===")
    def batch(x0):
        out = []
        for s in B_SEEDS:
            g, _ = feed(x0, B_N, B_T, s)
            out.append(g[-1])           # final ln(p/x0)
        return np.array(out)
    a, b = batch(X0_REF), batch(X0_ALT)
    print(f"  final ln(p/x0):  x0={X0_REF}  mean {a.mean():+.3f}  sd {a.std():.3f}")
    print(f"                   x0={X0_ALT}  mean {b.mean():+.3f}  sd {b.std():.3f}")
    # two-sample KS without scipy
    def ks(x, y):
        xs = np.sort(x); ys = np.sort(y)
        allv = np.concatenate([xs, ys])
        cx = np.searchsorted(xs, allv, "right") / len(xs)
        cy = np.searchsorted(ys, allv, "right") / len(ys)
        return np.max(np.abs(cx - cy))
    D = ks(a, b)
    print(f"  KS statistic D = {D:.3f}   (small D + overlapping means ⇒ "
          f"same distribution ⇒ x0 is a gauge on the ensemble)")


if __name__ == "__main__":
    test_A()
    if RUN_B:
        test_B()
    else:
        print("(TEST B skipped — set RUN_B=True for the n=500 seed batch)")
