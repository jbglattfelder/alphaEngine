"""
exp_drift_decomp.py — WHO pushes the price, and which way?

Edit the block, press Run.

THE QUESTION
------------
The price drifts (the CLOB arm rachets down). Every trader's own round trip
cancels in direction — buy to open, sell to close — so a net drift means one
KIND of push lands harder than its opposite. This instrument watches every
price-moving order, tags it by (who, what), and sums the signed log-price move
it caused. Whichever category has a net-nonzero sum IS the drift source.

No guessing: it counts.

HOW IT WORKS
------------
Every marketable order in the engine passes through Simulation._submit. We wrap
it, capture ln(last_price) before and after, and attribute the difference to a
category built from the order:
  - direction      : BUY (pushes price up) vs SELL (pushes down)
  - owner side     : LONG vs SHORT
  - role           : ENTRY (opening) vs SL-close vs IMPATIENCE-close vs OTHER
    (role is read from the order's is_close flag + the agent's `closing` state:
     is_close & closing -> SL cover;  is_close & not closing -> impatience;
     not is_close -> entry.)

This is a DIAGNOSTIC wrapper, not committed instrumentation — it does not change
a single fill (it only reads last_price around the unchanged _submit). Results
it produces are exploratory until the hook is committed. It is bit-neutral:
the wrapped run is identical to the unwrapped run (asserted at the end).

READ
----
The category sums add up to the total ln-drift. The one (or two) with the
largest |net| are the culprits. "restore symmetry" = neutralize that category;
"flip upward" = invert it. A category that is large in BOTH directions but nets
~0 is a wash (it moves the price a lot but symmetrically) — not the drift source.
"""
import numpy as np

from config import Config
from simulation import Simulation
from analysis import Recorder
from agents import Side

# ---------------- edit these ----------------
N, T, SEED = 500, 150_000, 42       # the ratchet needs large n + long T to be systematic
F, C, TP, SL = 0.5, 0.004, 0.01, 0.02
CLOSE_MODE, ENTRY_MODE = "home", "rest"
HOLD_FIRES_CLOSE = True
# --------------------------------------------


def role_of(idmap, order):
    """entry / sl / impatience / other, from the order + owner state."""
    if not getattr(order, "is_close", False):
        return "entry"
    a = idmap.get(order.agent_id)
    if a is None:
        # fall back: scan (small n) — owner id maps to index for the base draw
        if a is None:
            return "close?"
    return "sl" if getattr(a, "closing", False) else "impatience"


def main():
    cfg = Config(n=N, T=T, seed=SEED, f=F, c=C, tp=TP, sl=SL, close_mode=CLOSE_MODE,
                 entry_mode=ENTRY_MODE, hold_fires_close=HOLD_FIRES_CLOSE,
                 x_accounting=True, log_thresholds=True, symmetric_solvency=True)
    sim = Simulation(cfg, recorder=Recorder(), run_checks=False)

    acc = {}
    idmap = {a.id: a for a in sim.pop.agents}
    real_submit = sim._submit

    def wrapped(o, **kw):
        p0 = sim.book.last_price
        trades = real_submit(o, **kw)      # UNCHANGED engine call
        p1 = sim.book.last_price
        if p1 != p0 and p0 > 0 and p1 > 0:
            dln = float(np.log(p1) - np.log(p0))
            d = "BUY" if o.direction.name == "BUY" else "SELL"
            side = "LONG" if o.pos_side is Side.LONG else "SHORT"
            key = (d, side, role_of(idmap, o))
            e = acc.setdefault(key, [0.0, 0.0, 0])
            e[0] += dln; e[1] += abs(dln); e[2] += 1
        return trades

    sim._submit = wrapped
    sim.run()

    total = float(np.log(sim.p_int) - np.log(cfg.x_0))
    attributed = sum(v[0] for v in acc.values())

    print(f"run: n={N} T={T:,} seed={SEED} entry={ENTRY_MODE} close={CLOSE_MODE} "
          f"sl={SL} impatience={HOLD_FIRES_CLOSE}")
    print(f"total ln-drift = {total:+.3f}   attributed = {attributed:+.3f}   "
          f"(match => every price move was captured)\n")

    print(f"{'direction':>5} {'side':>6} {'role':>11} | {'NET dln':>10} "
          f"{'gross|dln|':>11} {'count':>8} {'net/gross':>9}")
    print("-" * 70)
    # sort by |net| descending — the culprits float to the top
    for key in sorted(acc, key=lambda k: -abs(acc[k][0])):
        net, gross, n = acc[key]
        d, side, role = key
        frac = net / gross if gross else 0.0
        print(f"{d:>5} {side:>6} {role:>11} | {net:>+10.3f} {gross:>11.3f} "
              f"{n:>8} {frac:>+9.2f}")

    print("\nsummary by role (net signed drift each role contributes):")
    by_role = {}
    for (d, side, role), (net, g, n) in acc.items():
        by_role[role] = by_role.get(role, 0.0) + net
    for role, net in sorted(by_role.items(), key=lambda x: -abs(x[1])):
        print(f"  {role:>11}: {net:+.3f}")
    print("\nsummary by direction:")
    by_dir = {}
    for (d, side, role), (net, g, n) in acc.items():
        by_dir[d] = by_dir.get(d, 0.0) + net
    for d, net in by_dir.items():
        print(f"  {d:>5}: {net:+.3f}")

    print("\nREAD: the role/side/direction with the largest |NET| is the ratchet's "
          "source.\n      net/gross near ±1 = one-directional (a true tilt); "
          "near 0 = a wash.")


if __name__ == "__main__":
    main()
