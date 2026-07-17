"""
exp_inventory.py — are the thin tails INVENTORY-limited?

Edit the block, press Run.

THE QUESTION
------------
The engine has momentum at one tick (q = 0.703; stops are market orders in the
direction of the move) yet NEGATIVE excess kurtosis at every scale. Osler (2005,
JIMF 24:219) finds stop-loss cascades are what fatten FX tails, so the momentum
is there but the tails are not. Why?

Measured gate (density.py, n=500, tp=sl=0.01, c=0.004): only **35 of 1000 agents
hold a position at any moment**, and their stops span just **3 sl-widths**. So the
stops are ALREADY tightly clustered, and the entire pool a cascade could detonate
is ~3.5% of the population. A cascade capped at ~35 small market orders cannot
move the price far. That points at inventory, not at clustering.

PREDICTION — STATED BEFORE THE RUN
----------------------------------
If the tails are inventory-limited, excess kurtosis rises with the mean open
count as c rises, and the fraction of multi-band price steps (|step| > 2*tp,
i.e. an order walking through several resting TPs at once) rises with it.

FALSIFIER: if kurtosis stays negative while the open count grows several-fold,
the inventory hypothesis is dead and clustering (cfg.sl_grid) goes back on the
table. Either way it is one existing knob and no new code.

WHY c AND NOT tp
----------------
c changes the firing rate -- hence open count = firing rate x holding time --
without changing the step size: sd(r) = 0.78*tp is set by the BAND, not by c
(measured over an 8x range of tp). Varying tp instead moves the lattice, the tick
volatility AND the total excursion at once; that sweep is confounded three ways
(HANDOFF-v4 section 2.1). c is the clean lever.

NOTE ON COST: n=500 runs at ~5.5 s / 1000 ticks. The defaults below are ~10 min
total. Drop N to 150 for a fast (but thinner-inventory) smoke test.
"""
import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder

# ---------------- edit these ----------------
N, T, SEED = 500, 100_000, 1
F, TP, SL = 0.5, 0.01, 0.01
CLOSE_MODE, SL_MODE = "home", "market"

C_VALUES = (0.002, 0.004, 0.01, 0.02, 0.05)   # the firing-rate sweep

RUN_CHECKS = False     # per-tick asserts; False is faster on a sweep
PLOT = True            # scatter kurtosis vs open count
# --------------------------------------------


def kurt(x: np.ndarray) -> float:
    x = x - x.mean(); s = x.std()
    return float(np.mean((x / s) ** 4) - 3.0) if s > 0 else float("nan")


def agg(r: np.ndarray, m: int) -> np.ndarray:
    n = len(r) // m * m
    return r[:n].reshape(-1, m).sum(axis=1)


def acf1(x: np.ndarray) -> float:
    x = x - x.mean()
    return float(np.sum(x[1:] * x[:-1]) / np.sum(x * x))


def main() -> None:
    print(f"inventory sweep | n={N}, T={T:,}, seed={SEED}, tp=sl={TP}, close={CLOSE_MODE}")
    print("PREDICTION: excess kurtosis RISES with mean open count.\n")
    print(f"{'c':>7} {'open':>7} {'open%':>6} {'sd(r)':>8} {'sd/tp':>6} | "
          f"{'kurt(1)':>8} {'kurt(5)':>8} {'kurt(25)':>9} | {'ACF(r)':>7} {'q':>6} {'>2tp':>6}")
    rows = []
    for c in C_VALUES:
        sim = Simulation(Config(n=N, T=T, seed=SEED, f=F, c=c, tp=TP, sl=SL,
                                close_mode=CLOSE_MODE, sl_mode=SL_MODE),
                         recorder=Recorder(), run_checks=RUN_CHECKS).run()
        rec = sim.recorder
        # mean open positions over the run (recorded per tick by simulation.py)
        op = np.array(rec.series("open_long"), float) + np.array(rec.series("open_short"), float)
        open_mean = float(op.mean())

        p = np.array([float(x) for x in rec.series("p_int")])
        r = np.diff(np.log(p))
        nz = r[np.abs(r) > 1e-12]
        if len(nz) < 100:
            print(f"{c:>7} {open_mean:>7.1f}  -- market too quiet to measure --")
            continue
        sd = float(np.std(r))
        q = float(np.mean(np.sign(nz)[1:] == np.sign(nz)[:-1]))
        gt2 = float(np.mean(np.abs(nz) > 2 * TP))

        row = dict(c=c, open=open_mean, sd=sd, k1=kurt(r), k5=kurt(agg(r, 5)),
                   k25=kurt(agg(r, 25)), acf=acf1(r), q=q, gt2=gt2)
        rows.append(row)
        print(f"{c:>7} {open_mean:>7.1f} {100*open_mean/(2*N):>5.1f}% {sd:>8.4f} "
              f"{sd/TP:>6.2f} | {row['k1']:>8.2f} {row['k5']:>8.2f} {row['k25']:>9.2f} | "
              f"{row['acf']:>7.3f} {q:>6.3f} {gt2:>5.1%}")

    if len(rows) >= 3:
        o = np.array([x["open"] for x in rows]); k = np.array([x["k1"] for x in rows])
        cc = float(np.corrcoef(o, k)[0, 1])
        print(f"\ncorr(open count, excess kurtosis at m=1) = {cc:+.3f}")
        print("  strongly positive -> inventory-limited, as predicted")
        print("  ~0 or negative    -> PREDICTION FALSIFIED; retract the inventory hypothesis")
        print(f"sd/tp across the sweep: {np.array([x['sd']/TP for x in rows]).round(3)}"
              f"   (should be ~constant: c must NOT move the step size)")
        if PLOT:
            _plot(rows)


def _plot(rows) -> None:
    import matplotlib.pyplot as plt
    o = [x["open"] for x in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    fig.suptitle(f"Are the thin tails inventory-limited?  n={N}, T={T:,}, tp=sl={TP}",
                 fontsize=11, fontweight="bold")
    for m, key, col in ((1, "k1", "#2563EB"), (5, "k5", "#15803D"), (25, "k25", "#B45309")):
        a1.plot(o, [x[key] for x in rows], "o-", ms=6, color=col, label=f"m={m}")
    a1.axhline(0, color="#111", ls="--", lw=1.0, label="Gaussian")
    a1.set_xlabel("mean open positions"); a1.set_ylabel("excess kurtosis")
    a1.set_title("Tails vs inventory", fontsize=10)
    a1.legend(fontsize=8); a1.grid(True, ls=":", alpha=0.4)

    a2.plot(o, [x["gt2"] for x in rows], "o-", ms=6, color="#2563EB", label="frac |step| > 2·tp")
    a2b = a2.twinx()
    a2b.plot(o, [x["q"] for x in rows], "s--", ms=5, color="#B45309", label="q (continuation)")
    a2b.axhline(0.5, color="#B45309", ls=":", lw=0.8)
    a2.set_xlabel("mean open positions"); a2.set_ylabel("frac multi-band steps")
    a2b.set_ylabel("q", color="#B45309")
    a2.set_title("Cascade signature vs inventory", fontsize=10)
    h1, l1 = a2.get_legend_handles_labels(); h2, l2 = a2b.get_legend_handles_labels()
    a2.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
    a2.grid(True, ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig("inventory.png", dpi=140, bbox_inches="tight")
    print("wrote inventory.png")
    plt.show()


if __name__ == "__main__":
    main()
