import math
import numpy as np
from config import Config
from simulation import Simulation
from agents import Side

def transfer_eur(sim):
    tl=sim.trade_log; p=sum(r["pnl"] for r in tl if r["side"]=="L"); n=sum(r["entry_q"] for r in tl if r["side"]=="L")
    return p/n if n else float("nan")

def long_x_share(sim):
    rp=sim.p_int**0.5
    wx=lambda a: a.eur/rp + a.btc*rp
    L=sum(wx(a) for a in sim.pop.agents if a.side is Side.LONG)
    S=sum(wx(a) for a in sim.pop.agents if a.side is Side.SHORT)
    return L/(L+S)

seeds=[42]
for f in (0.5, 0.1, 0.9):
    lnp=[]; tr=[]; sh=[]
    for s in seeds:
        sim=Simulation(Config(f=f,c=0.004,T=100_000,seed=s,x_accounting=True,
                              log_thresholds=True,symmetric_solvency=True),run_checks=True).run()
        lnp.append(math.log(sim.p_int/sim.cfg.x_0)); tr.append(transfer_eur(sim)); sh.append(long_x_share(sim))
    lnp=np.array(lnp); sh=np.array(sh)
    print(f"x_acct f={f}: drift lnp={lnp.mean():+.3f}(sd{lnp.std():.2f}) up/dn={int((lnp>0).sum())}/{len(lnp)}  "
          f"long X-wealth share={sh.mean():.4f} (sd {sh.std():.4f})  transfer_eur={np.nanmean(tr):+.4f}")