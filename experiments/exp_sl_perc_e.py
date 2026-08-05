"""
exp_gauge_dc.py — what the THRESHOLD GAUGE alone does to the DC scaling laws.

One geometric random walk (drift-free by construction, in log). The SAME paths
are run through the directional-change algorithm twice:

  PCT gauge : reversal when price moves +/- delta in PERCENT of the extreme
              (up: p >= E*(1+delta), down: p <= E*(1-delta))
  LOG gauge : reversal when |ln(p/E)| >= delta  (exp(+/-delta) bands)

Percent bands are asymmetric in log space: a -delta% move is a LARGER log move
than +delta% ( -ln(1-d) = d + d^2/2 + ...  vs  ln(1+d) = d - d^2/2 + ... ).
On a perfectly symmetric walk this manufactures (i) an up/down event-count
asymmetry, (ii) distorted N(delta) and overshoot laws, growing ~delta^2 —
pure convention, zero dynamics. This is the standalone exhibit of the
engine's `log_thresholds` design decision.

Output: gauge_dc.png (three panels: N(delta), <os>/delta, up/down count ratio).
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SIGMA = 0.01
T = 150_000
N_PATHS = 2
DELTAS = np.geomspace(1e-2, 0.30, 16)


def dc_events(p: np.ndarray, delta: float, gauge: str):
    """Standard DC sweep. Overshoot in the gauge's OWN units."""
    if gauge == "log":
        up = lambda x, ref: np.log(x / ref) >= delta
        dn = lambda x, ref: np.log(x / ref) <= -delta
        extent = lambda a, b: abs(np.log(a / b))
    else:
        up = lambda x, ref: x >= ref * (1.0 + delta)
        dn = lambda x, ref: x <= ref * (1.0 - delta)
        extent = lambda a, b: abs(a / b - 1.0)
    mode = 0
    hi = lo = ext = anchor = p[0]
    n_up = n_dn = 0
    overshoots = []
    for x in p:
        if mode == 0:
            hi = max(hi, x); lo = min(lo, x)
            if up(x, lo):
                mode = +1; n_up += 1; anchor = lo; ext = x
            elif dn(x, hi):
                mode = -1; n_dn += 1; anchor = hi; ext = x
        elif mode == +1:
            if x > ext:
                ext = x
            if dn(x, ext):
                overshoots.append((+1, max(extent(ext, anchor) - delta, 0.0)))
                mode = -1; n_dn += 1; anchor = ext; ext = x
        else:
            if x < ext:
                ext = x
            if up(x, ext):
                overshoots.append((-1, max(extent(ext, anchor) - delta, 0.0)))
                mode = +1; n_up += 1; anchor = ext; ext = x
    return n_up, n_dn, overshoots


def main() -> None:
    rng = np.random.default_rng(7)
    paths = [np.exp(np.cumsum(rng.normal(0.0, SIGMA, T))) for _ in range(N_PATHS)]

    res = {g: {"N": [], "os": [], "ratio": []} for g in ("pct", "log")}
    for d in DELTAS:
        for g in ("pct", "log"):
            nu = nd = 0
            oss = []
            for p in paths:
                a, b, o = dc_events(p, float(d), g)
                nu += a; nd += b; oss += o
            res[g]["N"].append((nu + nd) / N_PATHS)
            res[g].setdefault("raw", []).append([o for _, o in oss])
            vals = np.array([o for _, o in oss]) if oss else np.array([np.nan])
            res[g]["os"].append(np.nanmean(vals) / d)
            res[g].setdefault("os_abs", []).append(np.nanmean(vals))
            osu = np.mean([o for sgn, o in oss if sgn > 0]) if oss else np.nan
            osd = np.mean([o for sgn, o in oss if sgn < 0]) if oss else np.nan
            res[g]["ratio"].append(osu / osd if osd else np.nan)
        print(f"delta={d:.3f}  N: pct={res['pct']['N'][-1]:7.1f} log={res['log']['N'][-1]:7.1f}"
              f"   os/d: pct={res['pct']['os'][-1]:.3f} log={res['log']['os'][-1]:.3f}"
              f"   up/down(pct)={res['pct']['ratio'][-1]:.3f}")

    fig, axes = plt.subplots(2, 3, figsize=(18.0, 10.0))
    axes = axes.ravel()
    axg = axes[0]
    y0 = np.log(paths[0])
    axg.plot(np.arange(0, T, 50), y0[::50], lw=0.7, color="#444466")
    tv = 0.7979 * SIGMA * T
    axg.set_title("the walk itself (log-price, path 1)")
    axg.set_xlabel("tick"); axg.set_ylabel("ln p"); axg.grid(alpha=0.3)
    axg.text(0.03, 0.97, (f"net range \u2248 \u03c3\u221aT = {SIGMA*np.sqrt(T):.1f}\n"
                          f"total variation \u2248 0.8\u03c3T = {tv:,.0f}\n"
                          f"swings of size \u03b4: N \u2248 T\u03c3\u00b2/\u03b4\u00b2\n"
                          f"  \u03b4=0.20 \u2192 {150_000*SIGMA**2/0.04:.0f}/path\n"
                          f"  \u03b4=0.30 \u2192 {150_000*SIGMA**2/0.09:.0f}/path"),
             transform=axg.transAxes, fontsize=11, va="top",
             bbox=dict(boxstyle="round", fc="#FFF6BF", ec="#BBAA66"))
    axeq = axes[5]
    axeq.axis("off")
    axeq.set_title("percentage-band theory", fontsize=13)
    axeq.text(0.02, 0.96, (
        "Thresholds in log space:\n"
        r"   $a=\ln(1+\delta)$   ends down-trends"
        "\n"
        r"   $b=-\ln(1-\delta)$   ends up-trends,  $b>a$"
        "\n\n"
        "Overshoot of a trend (log units):\n"
        r"   $\omega \sim \rho + \mathrm{Exp}(m)$,  $m$ = ending threshold,"
        "\n"
        r"   $\rho \approx 0.583\,\sigma$  (tick correction)"
        "\n\n"
        "Measured in percent (convex map $e^{\omega}$):\n"
        r"   $E[\omega^{\%}_{up}] = (1{+}\delta)\left[\dfrac{e^{\rho}}{1-b}-1\right]$"
        "\n\n"
        r"   $E[\omega^{\%}_{dn}] = (1{-}\delta)\left[1-\dfrac{e^{-\rho}}{1+a}\right]$"
        "\n\n"
        r"Pole: $b \to 1 \;\Leftrightarrow\; \delta \to 1-e^{-1} \approx 0.632$"
        "\n"
        r"Asymmetry ratio $= E[\omega^{\%}_{up}]\, /\, E[\omega^{\%}_{dn}]$"
        "\n\n"
        "Log bands:  " r"$a=b=\delta \;\Rightarrow\; E[\omega]=\delta+\rho$" ",\n"
        "symmetric — all red pathologies vanish."),
        transform=axeq.transAxes, fontsize=12.5, va="top", family="serif",
        bbox=dict(boxstyle="round,pad=0.6", fc="#F8F5FF", ec="#8877BB"))
    axes = axes[1:]
    fig.suptitle(f"Drift-free GRW ({N_PATHS}\u00d7{T:,}, \u03c3={SIGMA}) \u2014 the MEASUREMENT gauge alone: % vs e^(\u00b1\u03b4) bands",
                 fontsize=14, fontweight="bold")
    C = {"pct": "#CC4444", "log": "#3366BB"}
    RHO = 0.583 * SIGMA          # discrete-step overshoot constant (Siegmund)
    a_ = np.log(1 + DELTAS); b_ = -np.log(1 - DELTAS)
    with np.errstate(divide="ignore"):
        up_pct = (1 + DELTAS) * np.where(b_ < 1, b_ / (1 - b_), np.inf)
    dn_pct = (1 - DELTAS) * a_ / (1 + a_)
    os_pct_theory = 0.5 * (up_pct + dn_pct)
    ratio_theory = up_pct / dn_pct
    with np.errstate(divide="ignore"):
        up_c = (1 + DELTAS) * np.where(b_ < 1, np.exp(RHO) / (1 - b_) - 1, np.inf)
    dn_c = (1 - DELTAS) * (1 - np.exp(-RHO) / (1 + a_))
    # the (1+/-delta) base factors: confirmation consumes exactly delta in pct,
    # the overshoot rides on the grown/shrunk base
    os_pct_corr = 0.5 * (up_c + dn_c)
    ratio_corr = up_c / dn_c
    os_log_corr = DELTAS + RHO           # log gauge with tick correction
    def ci(vals):
        v = np.asarray(vals, float)
        return (1.96 * v.std() / max(np.sqrt(len(v)), 1)) if len(v) > 1 else 0.0

    L = {"pct": "percent bands  p\u00b7(1\u00b1\u03b4)", "log": "log bands  p\u00b7e^{\u00b1\u03b4}"}

    ax = axes[0]
    for g in ("pct", "log"):
        ax.loglog(DELTAS, res[g]["N"], "o-", color=C[g], label=L[g])
    k = res["log"]["N"][0] * DELTAS[0] ** 2
    ax.loglog(DELTAS, k / DELTAS ** 2, ":", color="gray", label="theory \u03b4\u207b\u00b2 (BM)")
    ax.set_xlabel("\u03b4"); ax.set_ylabel("N(\u03b4) directional changes")
    ax.set_title("Law (0b): DC count"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    for g in ("pct", "log"):
        sel = DELTAS >= 3 * SIGMA
        E = np.polyfit(np.log(DELTAS[sel]), np.log(np.array(res[g]["os_abs"])[sel]), 1)[0]
        errs = [ci(v) / 1 for v in res[g]["raw"]]
        ax.errorbar(DELTAS, res[g]["os_abs"], yerr=errs, fmt="o-", color=C[g],
                    capsize=3, label=L[g] + f"  (fit \u03b4>3\u03c3: E = {E:.2f})")
        ax.set_xscale("log"); ax.set_yscale("log")
    ax.loglog(DELTAS, DELTAS, ":", color="gray", label="theory \u27e8\u03c9\u27e9 = \u03b4 (slope 1)")
    ax.loglog(DELTAS, os_pct_corr, "--", color="#CC4444", alpha=0.85,
              label="percent theory + tick corr. \u03c1\u22480.583\u03c3")
    ax.loglog(DELTAS, os_log_corr, "--", color="#3366BB", alpha=0.85,
              label="log theory + tick corr.  \u03b4+\u03c1")
    ax.set_xlabel("\u03b4"); ax.set_ylabel("\u27e8\u03c9(\u03b4)\u27e9")
    ax.set_title("Law (9,os): overshoot SCALING LAW"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2]
    for g in ("pct", "log"):
        errs = [ci(v) / d for v, d in zip(res[g]["raw"], DELTAS)]
        ax.errorbar(DELTAS, res[g]["os"], yerr=errs, fmt="o-", color=C[g], capsize=3, label=L[g])
        ax.set_xscale("log"); ax.set_yscale("log")
    ax.semilogx(DELTAS, os_pct_corr / DELTAS, "--", color="#CC4444", alpha=0.85,
                label="percent theory + tick corr. (pole at \u03b4\u22480.632)")
    ax.semilogx(DELTAS, os_log_corr / DELTAS, "--", color="#3366BB", alpha=0.85,
                label="log theory + tick corr.  1+\u03c1/\u03b4")
    ax.axhline(1.0, ls=":", color="gray", label="theory \u27e8\u03c9\u27e9=\u03b4")
    ax.set_xlabel("\u03b4"); ax.set_ylabel("\u27e8\u03c9(\u03b4)\u27e9 / \u03b4")
    ax.axvline(SIGMA, ls="-.", color="#888888", lw=1)
    ax.text(SIGMA*1.15, 0.9, "\u03b4 = \u03c3 (tick scale)", rotation=90, fontsize=9,
            color="#666666", va="top", transform=ax.get_xaxis_transform())
    ax.set_title("mean overshoot / \u03b4:  discreteness wall (left) vs gauge pole (right)", fontsize=12); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[3]
    for g in ("pct", "log"):
        ax.semilogx(DELTAS, res[g]["ratio"], "o-", color=C[g], label=L[g])
    ax.axhline(1.0, ls=":", color="gray", label="symmetric walk = 1")
    ax.semilogx(DELTAS, ratio_theory, "--", color="#CC8888", alpha=0.5,
                label="continuous theory")
    ax.semilogx(DELTAS, ratio_corr, "--", color="#CC4444", alpha=0.9,
                label="theory + tick corr. \u03c1")
    ax.set_xlabel("\u03b4"); ax.set_ylabel("\u27e8\u03c9 up-trends\u27e9 / \u27e8\u03c9 down-trends\u27e9")
    ax.set_title("The manufactured asymmetry\n(counts alternate by construction; it hides in overshoots)")
    ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gauge_dc.png")
    fig.savefig(os.path.abspath(out), dpi=140)
    for g in ("pct", "log"):
        n_ev = len(res[g]["raw"][-1])
        print(f"largest delta = {DELTAS[-1]:.3f}: {g} gauge, total DC events across "
              f"{N_PATHS} paths = {int(res[g]['N'][-1]*N_PATHS)}, overshoot samples = {n_ev}")
    print("wrote gauge_dc.png")


if __name__ == "__main__":
    main()
