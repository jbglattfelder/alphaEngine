"""Event-tape stats, memory-lean. Usage: python ev_stats.py LABEL EVENTS_NPZ T OUT_JSON"""
import json
import sys

import numpy as np

sys.path.insert(0, '/home/claude/liquidityengine/helper')
from dcos import dc_os  # noqa: E402

label, ev_path, T, out_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
R = {"label": label}

z = np.load(ev_path)
t = z['t']
R["n_prints"] = int(len(t))
R["prints_per_tick"] = float(len(t) / T)
i0 = int(np.searchsorted(t, 1001))
del t
p64 = z['p']
le = np.log(p64[i0:]).astype(np.float32)
del p64, z
re_ = np.diff(le)                      # float32, ~0.5 GB at 123M

CH = 10_000_000


def moments(x):
    n = 0
    s1 = s2 = s3 = s4 = 0.0
    for i in range(0, len(x), CH):
        c = x[i:i + CH].astype(np.float64)
        n += len(c)
        s1 += c.sum(); s2 += (c**2).sum(); s3 += (c**3).sum(); s4 += (c**4).sum()
    mu = s1 / n
    m2 = s2 / n - mu**2
    m4 = (s4 - 4 * mu * s3 + 6 * mu**2 * s2 - 4 * mu**3 * s1 + n * mu**4) / n
    return mu, m2, m4


mu, m2, m4 = moments(re_)
R["kurt_print"] = float(m4 / m2**2 - 3.0)
R["zero_print_frac"] = float(sum(float((re_[i:i+CH] == 0).sum()) for i in range(0, len(re_), CH)) / len(re_))


def acf_abs_pair(x, lags, mu, var):
    out_r, out_a = {}, {}
    # |r| moments
    n = len(x)
    s_abs = sum(float(np.abs(x[i:i+CH]).sum()) for i in range(0, n, CH))
    mu_a = s_abs / n
    s2_abs = sum(float((np.abs(x[i:i+CH]).astype(np.float64)**2).sum()) for i in range(0, n, CH))
    var_a = s2_abs / n - mu_a**2
    for L in lags:
        if L >= n - 1:
            continue
        sr = sa = 0.0
        for i in range(0, n - L, CH):
            u = x[i:i + CH if i + CH <= n - L else n - L].astype(np.float64)
            v = x[i + L:i + L + len(u)].astype(np.float64)
            sr += float(np.dot(u - mu, v - mu))
            sa += float(np.dot(np.abs(u) - mu_a, np.abs(v) - mu_a))
        out_r[int(L)] = sr / ((n - L) * var)
        out_a[int(L)] = sa / ((n - L) * var_a)
    return out_r, out_a


ev_lags = [1, 2, 3, 5, 10, 30, 100, 300, 1000, 3000, 10000, 100000, 1000000]
acr, aca = acf_abs_pair(re_, ev_lags, mu, m2)
R["acf_ret_event"] = acr
R["acf_abs_event"] = aca

agg = {}
for w in [1, 3, 10, 32, 100, 316, 1000, 3162, 10000, 31623, 100000]:
    nwin = len(re_) // w
    if nwin < 50:
        break
    s = re_[:nwin * w].reshape(nwin, w).astype(np.float64).sum(axis=1) if w <= 32 else \
        re_[:nwin * w].reshape(nwin, w).sum(axis=1, dtype=np.float64)
    ms = s - s.mean()
    agg[str(w)] = float(np.mean(ms**4) / np.mean(ms**2)**2 - 3.0)
    del s, ms
R["kurt_agg"] = agg
del re_

deltas = np.geomspace(0.004, 0.08, 12)
N, Om, Omed, Ex = [], [], [], []
for d in deltas:
    n, s, k, ov, ex = dc_os(le, np.float32(d))
    N.append(int(n))
    Om.append(float(s / k / d) if k else None)
    Omed.append(float(np.median(ov)) / d if k else None)
    Ex.append(float(ex / k / d) if k else None)
    del ov
R["dc"] = {"delta": [float(d) for d in deltas], "N": N, "os_mean": Om,
           "os_median": Omed, "dc_excess": Ex}
Na = np.array(N, float)


def fit(dmin, dmax):
    m = (deltas >= dmin * 0.999) & (deltas <= dmax * 1.001) & (Na >= 100)
    if m.sum() < 3:
        return None
    sl, _ = np.polyfit(np.log(deltas[m]), np.log(Na[m]), 1)
    om = np.nanmean([Om[i] for i in range(len(Om)) if m[i] and Om[i] is not None])
    return {"E_N": float(sl), "om": float(om), "lo": float(deltas[m].min()),
            "hi": float(deltas[m].max()), "k": int(m.sum())}


R["dc_fit_04_5"] = fit(0.004, 0.05)
R["dc_fit_above13"] = fit(0.013, 0.08)
json.dump(R, open(out_path, 'w'), indent=1)
print("OK", label, "| prints", R["n_prints"], "| kurt", round(R["kurt_print"]),
      "| E_N(.4-5)", R["dc_fit_04_5"]["E_N"] if R["dc_fit_04_5"] else None,
      "| om", R["dc_fit_04_5"]["om"] if R["dc_fit_04_5"] else None)
