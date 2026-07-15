"""
main.py — entry point for the Alpha Engine POC.

Load config, run the simulation with the canonical Recorder, and emit the three
standard views:
  - dashboard.png            : per-tick run dashboard (price, alive, capital, PnL, ...)
  - pnl_distribution.png     : who's winning/losing (PnL histogram, PnL-vs-K0, evolution)
  - capital_distribution.png : the Pareto capital draw (long vs short, tail CCDF)

Edit parameters in config.py (the single source of truth), not here.
SNAPSHOT_EVERY controls the per-agent PnL snapshots feeding the PnL-evolution panel;
set 0 to disable. Note the default Config() is the slow c=0.0001 substrate (long
warm-up, sparse trading) — pass an active cfg (e.g. Config(c=0.001, T=20000)) to see
a populated distribution.
"""

from config import Config
from simulation import Simulation
from analysis import Recorder, Analyser

SNAPSHOT_EVERY = 500   # per-agent PnL snapshot cadence (0 = off)


def main() -> None:
    cfg = Config()                                          # 1. load config
    cfg.save("config.json")                                 #    record the chosen values
    print(cfg.summary())

    sim = Simulation(cfg, recorder=Recorder(),             # 2. run
                     run_checks=True,                      #    per-tick EUR/BTC conservation asserts
                     snapshot_every=SNAPSHOT_EVERY).run()

    analyser = Analyser(sim)                                # 3. show results
    analyser.report()
    analyser.plot_dashboard(save_path="dashboard.png", show=True, price_yscale="linear")
    analyser.plot_pnl_distribution(save_path="pnl_distribution.png", show=True)
    sim.pop.plot_capital_distribution(metric="K0",
                                      save_path="capital_distribution.png", show=True)
    print("wrote: dashboard.png, pnl_distribution.png, capital_distribution.png")


if __name__ == "__main__":
    main()
