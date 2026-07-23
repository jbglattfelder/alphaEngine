"""
export_price.py — run one config and export the price feed to CSV.

The CSV is the hand-off point between the engine and the scaling-law analysis
(dc_analysis.py), so the analysis never has to import the engine and can be
pointed at any feed — ours, a GRW control, or real market data with the same
columns.

Columns:
    tick          physical time (the model's clock)
    p_int         emergent price (EUR/BTC)              <- the feed
    matched_btc   BTC cleared this tick (activity, numeraire-covariant)
    matched_eur   EUR cleared this tick (activity, price-dependent: see HANDOFF rule 4)
    crossed       1 if the tick had any trade
    open_long/short, stuck_long/short, long_x_share     (context, not used by the analysis)

Edit the block, Run.
"""
import csv

from config import Config
from simulation import Simulation
from analysis import Recorder

# ---------------- edit these ----------------
N, T, SEED = 500, 150_000, 42
C, TP, SL = 0.004, 0.01, 0.01
ENTRY_MODE = "rest"          # "ioc" | "rest"
HOLD_FIRES_CLOSE = True    # impatience (see HANDOFF-master.md par 4.7)
OUT = "price_feed.csv"
RUN_CHECKS = True          # False is faster on long runs
# --------------------------------------------

COLS = ["tick", "p_int", "matched_btc", "matched_eur", "crossed",
        "open_long", "open_short", "stuck_long", "stuck_short", "long_x_share"]


def main() -> None:
    cfg = Config(n=N, T=T, seed=SEED, c=C, tp=TP, sl=SL,
                 entry_mode=ENTRY_MODE, hold_fires_close=HOLD_FIRES_CLOSE)
    print(cfg.summary())
    sim = Simulation(cfg, recorder=Recorder(), run_checks=RUN_CHECKS).run()
    rec = sim.recorder

    have = [c for c in COLS if c in rec.history]
    missing = [c for c in COLS if c not in rec.history]
    if missing:
        print(f"note: series not recorded by this engine, skipped: {missing}")

    series = {c: rec.series(c) for c in have}
    n = len(series["p_int"])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(have)
        for i in range(n):
            w.writerow([series[c][i] for c in have])

    # provenance: the config that produced the feed, next to the feed
    cfg.save(OUT.replace(".csv", "_config.json"))
    print(f"wrote {OUT}  ({n:,} rows)  + {OUT.replace('.csv','_config.json')}")
    print(f"p_final = {sim.p_int!r}")


if __name__ == "__main__":
    main()
