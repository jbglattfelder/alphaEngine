"""Tick+book stats. Usage: python tb_stats.py LABEL TICK_NPY BOOK_NPZ OUT_JSON"""
import json
import sys

import numpy as np

label, tick_path, bk_path, out_path = sys.argv[1:5]
R = {"label": label}

p = np.load(tick_path).astype(np.float64)
lp = np.log(p)
T = len(p)
R["T"] = T
R["ln_drift_full"] = float(lp[-1] - lp[0])
R["ln_drift_400k"] = float(lp[min(400_000, T - 1)] - lp[0])
R["ln_range"] = float(lp.max() - lp.min())
R["seg_drifts"] = [round(float(lp[min((i + 1) * 100_000, T - 1)] - lp[i * 100_000]), 3)
                   for i in range(T // 100_000)]
r = np.diff(lp[1000:])
R["zero_tick_frac"] = float(np.mean(r == 0.0))
R["sd_tick"] = float(r.std())
m = r - r.mean()
R["kurt_tick"] = float(np.mean(m**4) / np.mean(m**2)**2 - 3.0)


def acf(x, lags):
    x = x - x.mean()
    v = float(np.dot(x, x))
    return {int(L): float(np.dot(x[:-L], x[L:]) / v) for L in lags if L < len(x)}


tick_lags = [1, 2, 3, 5, 10, 20, 30, 60, 100, 200, 300, 600, 1000, 2000, 5000, 10000]
R["acf_ret_tick"] = acf(r, tick_lags)
R["acf_abs_tick"] = acf(np.abs(r), tick_lags)
mem = 0
for L in tick_lags:
    if R["acf_abs_tick"][L] >= 0.05:
        mem = L
    else:
        break
R["mem_ticks_005"] = mem
del r, m

z = np.load(bk_path)
bt = np.asarray(z['t'])
bids = np.asarray(z['bids'], np.float64)
asks = np.asarray(z['asks'], np.float64)
keep = bt >= 1000
bt, bids, asks = bt[keep], bids[keep], asks[keep]
bb, ba = bids[:, 0, 0], asks[:, 0, 0]
two = ~np.isnan(bb) & ~np.isnan(ba)
R["two_sided_frac"] = float(np.mean(two))
mid = 0.5 * (bb[two] + ba[two])
spr = (ba[two] - bb[two]) / mid
R["spread_pct"] = {"median": float(np.median(spr) * 100),
                   "p10": float(np.percentile(spr, 10) * 100),
                   "p90": float(np.percentile(spr, 90) * 100)}
R["levels_median"] = float(np.median((~np.isnan(bids[:, :, 0])).sum(axis=1)
                                     + (~np.isnan(asks[:, :, 0])).sum(axis=1)))
vb = np.nansum(np.where(np.isnan(bids[:, :, 1]), 0, bids[:, :, 1]), axis=1)
va = np.nansum(np.where(np.isnan(asks[:, :, 1]), 0, asks[:, :, 1]), axis=1)
ok = (vb + va) > 0
imb = np.zeros(len(vb))
imb[ok] = (va[ok] - vb[ok]) / (va[ok] + vb[ok])
lean = {}
bt_i = bt.astype(np.int64)
for h in [100, 300, 1000, 3000, 10000, 30000]:
    sel = (bt_i - h >= 0) & (bt_i + h < T) & ok
    if sel.sum() < 100:
        continue
    tt = bt_i[sel]
    pre = np.sign(lp[tt] - lp[tt - h])
    fol = np.sign(lp[tt + h] - lp[tt])
    iv = imb[sel]
    lean[str(h)] = {"with_preceding": float(np.corrcoef(pre, iv)[0, 1]),
                    "with_following": float(np.corrcoef(fol, iv)[0, 1])}
R["lean"] = lean
json.dump(R, open(out_path, 'w'), indent=1)
print("OK", label, "| drift", round(R["ln_drift_full"], 2), "| acf1", round(R["acf_ret_tick"][1], 2),
      "| mem", R["mem_ticks_005"], "| spread", round(R["spread_pct"]["median"], 4),
      "| 2sided", round(R["two_sided_frac"], 3), "| lean100",
      round(lean.get("100", {}).get("with_preceding", float('nan')), 2))
