"""Chunked, checkpointed run recording effective size n_eff(t)=1/sum(w_i^2) on wealth shares (X units)."""
import sys, os, time, pickle, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,'helper'))
import simulation_mvp as S
n=int(sys.argv[1]); budget=float(sys.argv[2]); seed=int(sys.argv[3]) if len(sys.argv)>3 else 9; every=1000
os.makedirs(os.path.join(HERE,'neff'),exist_ok=True); ck=os.path.join(HERE,'neff',f'ck_n{n}_s{seed}.pkl'); rec=os.path.join(HERE,'neff',f'rec_n{n}_s{seed}.npz')
if os.path.exists(ck):
    sim,R=pickle.load(open(ck,'rb'))
else:
    cfg=S.Config(n=n,T=10_000_000,seed=seed,capital_dist='normal',band_dist='normal',closing='normal',size_dist='normal',
                 save_book=False,save_tapes=False,save_csv=False)
    for k in ('save_log','write_log'):
        if hasattr(cfg,k): setattr(cfg,k,False)
    sim=S.Simulation(cfg); R={k:[] for k in ('t','p','neff','alive_L','alive_S','top1','gini','eur_L','btc_L','eur_S','btc_S','open_L','open_S','stuck_L','stuck_S')}
def snapshot(t):
    p=sim.p; rp=np.sqrt(p)
    w=np.array([a.eur/rp+a.btc*rp for a in sim.agents]); w=np.maximum(w,0); s=w/w.sum()
    al=[a for a in sim.agents if a.alive]
    R['t'].append(t); R['p'].append(p); R['neff'].append(1.0/np.sum(s**2))
    R['alive_L'].append(sum(1 for a in al if a.is_long)); R['alive_S'].append(sum(1 for a in al if not a.is_long))
    ss=np.sort(s)[::-1]; R['top1'].append(ss[:max(1,len(ss)//100)].sum())
    k=len(s); R['gini'].append((2*np.sum(np.arange(1,k+1)*np.sort(s))/k)-(k+1)/k)
    for tag,sel in (('L',lambda a:a.is_long),('S',lambda a:not a.is_long)):
        A=[a for a in sim.agents if sel(a)]
        R['eur_'+tag].append(sum(a.eur for a in A)); R['btc_'+tag].append(sum(a.btc for a in A))
        R['open_'+tag].append(sum(1 for a in A if a.alive and (a.pos_b!=0 or a.pos_q!=0)))
        R['stuck_'+tag].append(sum(1 for a in A if a.alive and a.closing))
t0=time.time(); t=sim.t
if t==0: snapshot(0)
keep=True
while time.time()-t0<budget and keep:
    t+=1; keep=sim.step(t)
    if t%every==0:
        snapshot(t); sim.trades_log.clear()
sim._logf=None
pickle.dump((sim,R),open(ck,'wb')); np.savez(rec,**{k:np.array(v) for k,v in R.items()})
print(f'n={n} t={t:,} p={sim.p:.2f} neff={R["neff"][-1]:.0f} alive={R["alive_L"][-1]}/{R["alive_S"][-1]} top1={R["top1"][-1]:.3f} keep={keep} ({time.time()-t0:.0f}s)')
