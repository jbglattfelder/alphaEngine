import sys, math
import numpy as np
from config import Config
from simulation import Simulation
from agents import Side
def long_x_share(sim):
    rp=sim.p_int**0.5
    wx=lambda a: a.eur/rp + a.btc*rp
    L=sum(wx(a) for a in sim.pop.agents if a.side is Side.LONG)
    S=sum(wx(a) for a in sim.pop.agents if a.side is Side.SHORT)
    return L/(L+S)
f=float(sys.argv[1])
lnp=[]; sh=[]
for s in (1,2,3,4,5,6):
    sim=Simulation(Config(f=f,c=0.004,T=8000,seed=s,x_accounting=True,
                          log_thresholds=True,symmetric_solvency=True),run_checks=True).run()
    lnp.append(math.log(sim.p_int/sim.cfg.x_0)); sh.append(long_x_share(sim))
lnp=np.array(lnp); sh=np.array(sh)
print(f"f={f}: drift lnp={lnp.mean():+.3f}(sd{lnp.std():.2f})  long X-share={sh.mean():.4f} (sd {sh.std():.4f})")
