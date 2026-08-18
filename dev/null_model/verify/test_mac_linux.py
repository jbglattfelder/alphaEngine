import math
import numpy as np
from simulation_mvp import Config, Simulation

cfg = Config(n=500, T=60_000, seed=9, capital_dist="pareto",
             band_dist="normal", exp_mode="decimal")
sim = Simulation(cfg, run_checks=False).run()
drift = math.log(sim.p / cfg.x_0)
print("ln drift =", repr(drift))
print("expected  -4.4488393740137475  (Linux, libm == decimal)")
print("MATCH:", drift == -4.4488393740137475)
