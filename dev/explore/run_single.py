"""
run_single.py — one run -> dashboard + capital distribution + PnL distribution.

Edit the block below and press Run. PNGs are written next to this file; set
SHOW=True to also pop windows in your IDE.

NOTE (fixed 2026-07-15): the previous version of this file had only N/T/SEED/F/C
in the block and passed only those to Config(). Any TP/SL added to the block was
SILENTLY IGNORED and tp/sl fell through to the config.py defaults -- a block that
lied about what ran. Every switch below is now passed explicitly, and
Config.summary() prints the resolved exits/close_mode/sl_mode/sizing so the run
states its own mechanism. If you add a knob here, WIRE IT INTO Config() BELOW.
"""
from config import Config
from simulation import Simulation
from analysis import Recorder, Analyser

# ---------------- edit these ----------------
N     = 150     # agents PER SIDE   (total population = 2*N)
T     = 100_000    # number of ticks
SEED  = 9
F     = 0.5     # initial home fraction
C     = 0.004   # firing rate (activity); higher = livelier & slower

TP    = 0.01     # take-profit band
SL    = 0.01     # stop-loss band

CLOSE_MODE = "home"      # "home" = each tribe delivers what it holds (v4 symmetric null)
                         # "quantity" = both tribes re-trade a fixed BTC quantity (v3; stranding)
SL_MODE    = "market"    # "market" | "limit" | "wait"   (close_mode="home" requires "market")

X_ACCOUNTING       = True       # geometric-mean (X) sizing, identical formula both tribes
LOG_THRESHOLDS     = True       # log-symmetric TP/SL bands (kills the percentage gauge drift)
SYMMETRIC_SOLVENCY = True       # clamp SELLs by BTC held, mirroring the EUR clamp on BUYs
ENTRY_MODE         = "rest"     # how ENTRIES meet the market (v5 pure-CLOB switch)
BOOK_MODE          = "coin"     # the venue's denomination 
EXIT_PROMISE       = "own_coin" # home-mode exit denomination — WHOSE exit promises WHICH currency

HOLD_FIRES_CLOSE   = True   # impatience: the pressure clock also runs while HOLDING -> close

SNAPSHOT_EVERY = 500   # per-agent PnL snapshot cadence (0 = off; faster on long runs)
RUN_CHECKS     = True  # per-tick conservation + solvency asserts (False is faster)
SHOW           = True
# --------------------------------------------

cfg = Config(n=N, T=T, seed=SEED, f=F, c=C,
             tp=TP, sl=SL,
             close_mode=CLOSE_MODE, sl_mode=SL_MODE,
             x_accounting=X_ACCOUNTING,
             log_thresholds=LOG_THRESHOLDS,
             symmetric_solvency=SYMMETRIC_SOLVENCY,
             entry_mode=ENTRY_MODE,
             hold_fires_close=HOLD_FIRES_CLOSE,
             book_mode=BOOK_MODE,
             exit_promise=EXIT_PROMISE)
print(cfg.summary())          # prints the RESOLVED switches -- check them against the block

sim = Simulation(cfg, recorder=Recorder(), run_checks=RUN_CHECKS,
                 snapshot_every=SNAPSHOT_EVERY).run()
print(sim.summary())

an = Analyser(sim)
an.report()
an.plot_dashboard(save_path="dashboard.png", show=SHOW, price_yscale="linear")
an.plot_pnl_distribution(save_path="pnl_distribution.png", show=SHOW)
sim.pop.plot_capital_distribution(metric="K0", save_path="capital_distribution.png", show=SHOW)
print("wrote: dashboard.png, pnl_distribution.png, capital_distribution.png")
