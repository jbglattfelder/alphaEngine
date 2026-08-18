"""Stylized-facts scorecard for a set of runs (uses saved p_int series).

Facts tested (Cont 2001):
  SF1 absence of linear autocorrelation: ACF(r) ~ 0 beyond lag ~1
  SF2 volatility clustering: ACF(|r|) > 0, slow decay
  SF3 heavy tails: excess kurtosis >> 0 at tick scale
  SF4 aggregational gaussianity: kurtosis falls as returns are aggregated
  SF5 activity: fraction of ticks with trades / zero returns
"""
import json, glob, sys
import numpy as np


def acf(x, lags):
    x = x - x.mean()
    v = float((x * x).mean())
    if v == 0:
        return np.zeros(len(lags))
    return np.array([float((x[:-L] * x[L:]).mean()) / v for L in lags])


def facts(p):
    p = np.asarray(p, float)
    r = np.diff(np.log(p))
    out = {}
    out["zero_frac"] = float((r == 0).mean())
    out["sd"] = float(r.std())
    lags_r = [1, 2, 3, 5, 10, 20]
    lags_a = [1, 5, 10, 25, 50, 100, 250]
    out["acf_r"] = acf(r, lags_r)
    out["acf_abs"] = acf(np.abs(r), lags_a)
    def kurt(x):
        s = x.std()
        return float(((x - x.mean()) ** 4).mean() / s**4 - 3.0) if s > 0 else float("nan")
    out["kurt"] = {}
    for m in (1, 5, 25, 125):
        n = (len(r) // m) * m
        rm = r[:n].reshape(-1, m).sum(axis=1)
        out["kurt"][m] = kurt(rm)
    return out


def table(arm, files):
    rows = []
    for f in sorted(files):
        r = json.load(open(f))
        rows.append((r["seed"], facts(r["series"]["p_int"])))
    print(f"\n=== {arm} ({len(rows)} seeds) ===")
    print(f"{'seed':>4} {'sd(r)':>8} {'zero%':>6} | ACF(r) L1 L5 L20 | ACF|r| L1 L10 L100 L250 | kurt m=1 5 25 125")
    agg = {"acf_r": [], "acf_abs": [], "k": []}
    for s, F in rows:
        ar, aa, k = F["acf_r"], F["acf_abs"], F["kurt"]
        agg["acf_r"].append(ar); agg["acf_abs"].append(aa)
        agg["k"].append([k[1], k[5], k[25], k[125]])
        print(f"{s:>4} {F['sd']:>8.4f} {100*F['zero_frac']:>5.1f}% | "
              f"{ar[0]:+.2f} {ar[3]:+.2f} {ar[5]:+.2f} | "
              f"{aa[0]:+.2f} {aa[2]:+.2f} {aa[5]:+.2f} {aa[6]:+.2f} | "
              f"{k[1]:6.1f} {k[5]:6.1f} {k[25]:6.1f} {k[125]:6.1f}")
    m = lambda a: np.mean(np.array(a), axis=0)
    ar, aa, kk = m(agg["acf_r"]), m(agg["acf_abs"]), m(agg["k"])
    print(f"MEAN        | ACF(r): L1={ar[0]:+.3f} L5={ar[3]:+.3f} L20={ar[5]:+.3f} | "
          f"ACF|r|: L1={aa[0]:+.3f} L10={aa[2]:+.3f} L100={aa[5]:+.3f} L250={aa[6]:+.3f} | "
          f"kurt: {kk[0]:.1f} -> {kk[1]:.1f} -> {kk[2]:.1f} -> {kk[3]:.1f}")


if __name__ == "__main__":
    specs = sys.argv[1:] or ["home2:.", "base:../stranding_v2"]
    for spec in specs:
        arm, d = spec.split(":")
        table(arm, glob.glob(f"{d}/stranding_{arm}_*.json"))
