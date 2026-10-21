"""A13-style spread stats for the IT arms. Writes sp_<tag>.json."""
import json
import sys

import numpy as np

label, bk_path, out_path = sys.argv[1:4]
R = {"label": label}

z = np.load(bk_path)
bt = np.asarray(z['t']).astype(np.int64)
bids = np.asarray(z['bids'], np.float64)
asks = np.asarray(z['asks'], np.float64)
keep = bt >= 1000
bt, bids, asks = bt[keep], bids[keep], asks[keep]
bb, ba = bids[:, 0, 0], asks[:, 0, 0]
two = ~np.isnan(bb) & ~np.isnan(ba)
mid = 0.5 * (bb + ba)
spr = np.full(len(bb), np.nan)
spr[two] = (ba[two] - bb[two]) / mid[two] * 100.0   # % of mid

# two-sided within 1% of mid (A12 panel-a convention)
near_b = np.nanmax(np.where(np.isnan(bids[:, :, 0]), -np.inf, bids[:, :, 0]), axis=1)
near_a = np.nanmin(np.where(np.isnan(asks[:, :, 0]), np.inf, asks[:, :, 0]), axis=1)
ok = two.copy()
w1 = np.zeros(len(bb), bool)
w1[ok] = (near_b[ok] >= mid[ok] * 0.99) & (near_a[ok] <= mid[ok] * 1.01)
R["two_sided_frac"] = float(np.mean(two))
R["two_sided_1pct_frac"] = float(np.mean(w1))

sv = spr[two]
R["spread_pct"] = {q: float(np.percentile(sv, qq)) for q, qq in
                   [("p10", 10), ("p25", 25), ("median", 50), ("p75", 75), ("p90", 90)]}
R["frac_below_cent"] = float(np.mean(sv < 0.01))   # one cent on 100 EUR = 0.01%

# (a) median spread per 50k-tick window
W = 50_000
nw = int(bt.max() // W) + 1
win_med, win_x = [], []
for k in range(nw):
    m = (bt >= k * W) & (bt < (k + 1) * W) & two
    if m.sum() < 50:
        win_med.append(None)
    else:
        win_med.append(float(np.median(spr[m])))
    win_x.append(int((k + 0.5) * W))
R["win_x"] = win_x
R["win_med"] = win_med

# (b) CDF on a log grid
grid = np.geomspace(1e-5, 1.0, 120)
R["cdf_grid"] = [float(g) for g in grid]
R["cdf"] = [float(np.mean(sv <= g)) for g in grid]

json.dump(R, open(out_path, 'w'), indent=1)
print("OK", label, "| med", round(R["spread_pct"]["median"], 4),
      "| IQR", round(R["spread_pct"]["p25"], 4), "-", round(R["spread_pct"]["p75"], 4),
      "| <1cent", round(R["frac_below_cent"], 3),
      "| 2sided", round(R["two_sided_frac"], 4), "| 2sided@1%", round(R["two_sided_1pct_frac"], 4))
