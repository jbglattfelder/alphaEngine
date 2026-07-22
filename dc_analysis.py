"""
dc_analysis.py — intrinsic-time (directional-change / overshoot) analysis of a price feed.

Implements:
  * Glattfelder, Dupuis & Olsen (2011), "Patterns in high-frequency FX data:
    discovery of 12 empirical scaling laws", arXiv:0809.1040 — algorithm 2
    (directional-change count) transcribed verbatim, plus the overshoot
    dissection and laws (0b), (9)*=dc/os/tm, (11), (12).
  * Glattfelder & Golub (2022), "Bridging the Gap: Decoding the Intrinsic Nature
    of Time in Market Data", arXiv:2204.02682 — the overshoot-variability law
    (27) and the physical/intrinsic-time bridge (23) and invariant (30), which
    decomposes a time series into a VOLATILITY component (number of directional
    changes) and a LIQUIDITY component (variability of overshoots).

NOTATION GOTCHA (load-bearing, do not "fix"):
    The two papers define the averaging operator differently.
      0809.1040 : <x>_p = ( (1/n) sum x_i^p )^(1/p)      (quadratic mean at p=2)
      2204.02682: <x>_2 =   (1/n) sum x_i^2              (plain mean square)
    Only the 2204 convention makes the bridge dimensionally consistent. Check on
    Brownian motion: LHS of (23) = (T/dt)*sigma^2*dt = sigma^2*T; RHS = delta^2 *
    (sigma^2*T/delta^2) = sigma^2*T. So MEAN_SQUARE is used for the bridge, and
    the invariant C = sigma^2 is a variance RATE (per unit physical time).

Reference values (Brownian motion, arXiv:2204.02682 Tbl. 1):
    N_hat(delta) ~ delta^-1.90     (theory -2)
    <omega(delta)> ~ delta^0.98    (theory  1;  <omega> ~= delta)
    <omega-delta>_2 ~ delta^1.91   (theory  2)
    <r(dt)>_2 ~ dt^1.00            (theory  1)
    C^T ~= C^tau                   (theory: both = sigma^2)

Usage:
    python dc_analysis.py                      # reads price_feed.csv
    python dc_analysis.py myfeed.csv
Writes dc_scaling_laws.png and prints the fitted exponents.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np


# ── the dissection ────────────────────────────────────────────────────────────
@dataclass
class DCEvent:
    idx: int          # index in the feed where the DC was registered
    price: float      # price at the DC event
    direction: int    # +1 = up DC, -1 = down DC
    overshoot: float  # overshoot of the PRECEDING dc-segment (relative, e.g. 0.012 = 1.2%)
    n_ticks_tm: int   # ticks in the total move (previous DC event -> this one)


def dc_events(prices: np.ndarray, delta: float) -> list[DCEvent]:
    """Algorithm 2 of arXiv:0809.1040 (directionalChangeCount), extended to also
    measure the overshoot and tick counts.

    The paper's algorithm, verbatim:
        initialise: x_ext = x_0, mode = up
        if mode is down:
            if x < x_ext:                      x_ext <- x
            elif (x - x_ext)/x_ext >=  delta:  n_up++;   x_ext <- x; mode <- up
        elif mode is up:
            if x > x_ext:                      x_ext <- x
            elif (x - x_ext)/x_ext <= -delta:  n_down++; x_ext <- x; mode <- down

    Overshoot (0809.1040 sec. 2.1 / 2204.02682 fig. 1): at each DC event, the
    overshoot associated with the PREVIOUS directional change is the move from
    the price level at which the last DC occurred to the extremum reached since
    (the high in up mode, the low in down mode). Because x_ext is reset to the
    price at every DC event and then tracks the extremum, x_ext at the moment the
    next DC fires IS that extremum.

    The first event's overshoot is an initialisation artifact (there is no
    preceding DC) and is discarded by the caller.
    """
    events: list[DCEvent] = []
    x_ext = float(prices[0])
    x_dc = float(prices[0])   # price at the last DC event
    i_dc = 0
    mode_up = True            # the paper initialises mode = up

    for i in range(len(prices)):
        x = float(prices[i])
        if not mode_up:                                    # mode is down
            if x < x_ext:
                x_ext = x
            elif (x - x_ext) / x_ext >= delta:
                events.append(DCEvent(i, x, +1, abs(x_ext - x_dc) / x_dc, i - i_dc))
                x_ext = x; x_dc = x; i_dc = i; mode_up = True
        else:                                              # mode is up
            if x > x_ext:
                x_ext = x
            elif (x - x_ext) / x_ext <= -delta:
                events.append(DCEvent(i, x, -1, abs(x_ext - x_dc) / x_dc, i - i_dc))
                x_ext = x; x_dc = x; i_dc = i; mode_up = False
    return events


def dc_log_events(y: np.ndarray, delta: float) -> list[DCEvent]:
    """Algorithm 2 in the LOG gauge: run on y = ln(p) with ADDITIVE thresholds.

    Identical logic to dc_events(), with ratios replaced by differences. delta is
    an additive log threshold (delta=0.05 ~ +5.13% / -4.88%: symmetric in log,
    which is the point).

    WHY THIS IS THE DEFAULT (and dc_events is kept only to reproduce the papers):
      1. SCALE-COVARIANT. The home-close arm spans e-folds (FINDINGS V4.2: p from
         1.6e-9 to 6.7e11). A relative overshoot of 1e6 and one of 1e-6 are the
         same physical move in opposite directions; the log gauge calls them
         +13.8 and -13.8, which is what you can average. Measured on the
         n=500/T=100k/sl=0.02 home arm the relative gauge reports <om>/delta =
         3.3e6 -- unplottable; the log gauge reports ~100.
      2. SYMMETRIC. A relative down-move is bounded at -1, an up-move is
         unbounded -- a gauge asymmetry in the MEASUREMENT, in a project built on
         numeraire covariance. Negligible at delta=1%, material at delta=0.44,
         which is where our grid reaches (tick-sd = 0.78*tp here).

    It costs nothing where the relative gauge is valid: measured agreement on BM
    is 0.32% at delta=0.01 and 1.5% at delta=0.05, so the FX results stand.

    NOT A FIX FOR THE RUNAWAY: the 1e6 overshoot is real. On a BM spanning e^24
    the relative gauge gives <om>/delta = 1.22 vs the log gauge's 1.03 -- mildly
    inflated, nowhere near 1e6. An overshoot that size needs a monotone ratchet
    (~14 e-folds with no delta pullback), which BM cannot do. Switching gauge
    makes the number legible, not smaller.
    """
    events: list[DCEvent] = []
    y_ext = float(y[0]); y_dc = float(y[0]); i_dc = 0
    mode_up = True
    for i in range(len(y)):
        v = float(y[i])
        if not mode_up:
            if v < y_ext:
                y_ext = v
            elif v - y_ext >= delta:
                events.append(DCEvent(i, v, +1, abs(y_ext - y_dc), i - i_dc))
                y_ext = v; y_dc = v; i_dc = i; mode_up = True
        else:
            if v > y_ext:
                y_ext = v
            elif v - y_ext <= -delta:
                events.append(DCEvent(i, v, -1, abs(y_ext - y_dc), i - i_dc))
                y_ext = v; y_dc = v; i_dc = i; mode_up = False
    return events


# ── measurements at one threshold ─────────────────────────────────────────────
def measure(prices: np.ndarray, delta: float, T: int, min_events: int = 12,
            gauge: str = "log") -> dict | None:
    """gauge="log" (default, scale-covariant) | "relative" (the papers' gauge)."""
    ev = (dc_log_events(np.log(prices), delta) if gauge == "log"
          else dc_events(prices, delta))
    if len(ev) < min_events:          # too few DC events at this threshold to average over
        return None
    os = np.array([e.overshoot for e in ev[1:]])       # drop the init artifact
    tm_ticks = np.array([e.n_ticks_tm for e in ev[1:]], float)
    N = len(ev)
    return {
        "delta": delta,
        "N": N,                       # law (0b): number of directional changes
        "N_hat": N / T,               # eq (28): normalised by physical time
        "os_mean": float(os.mean()),                    # law (9) *=os : <omega> ~= delta
        "os_median": float(np.median(os)),              # DRIFT-ROBUST: mean >> median => trend, not liquidity
        "os_var2": float(np.mean((os - delta) ** 2)),   # eq (27): <omega-delta>_2 ~ delta^2
        "tm_mean": float(delta + os.mean()),            # law (9) *=tm : ~= 2*delta
        "os_cum": float(os.sum()),                      # law (12) *=os
        "coastline": float(N * delta + os.sum()),       # law (12) *=tm (the coastline)
        "tm_ticks": float(tm_ticks.mean()),             # law (11) *=tm
        "n_os": len(os),
    }


def sq_returns(prices: np.ndarray, dt: int) -> float:
    """<r(dt)>_2 in the 2204 convention: the MEAN SQUARE of relative returns."""
    p = prices[::dt]
    r = np.diff(p) / p[:-1]
    r = r[np.isfinite(r)]
    return float(np.mean(r ** 2)) if len(r) else float("nan")


def fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Fit y = (x/C)^E in log-log space (sec. 3.3: linear model, E=B, C=exp(-A/B)).
    Returns (E, C, adj_R2)."""
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    X, Y = np.log(x[m]), np.log(y[m])
    if len(X) < 3:
        return float("nan"), float("nan"), float("nan")
    B, A = np.polyfit(X, Y, 1)
    resid = Y - (A + B * X)
    ss_res, ss_tot = float(np.sum(resid ** 2)), float(np.sum((Y - Y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    adj = 1 - (1 - r2) * (len(X) - 1) / (len(X) - 2) if len(X) > 2 else r2
    C = float(np.exp(-A / B)) if B != 0 else float("nan")
    return float(B), C, float(adj)


# ── driver ────────────────────────────────────────────────────────────────────
def analyse(prices: np.ndarray, n_deltas: int = 20, n_dts: int = 20,
            delta_lo_mult: float = 8.0, delta_hi_mult: float = 40.0,
            min_events: int = 12, gauge: str = "log",
            plot_path: str | None = "dc_scaling_laws.png") -> dict:
    prices = np.asarray(prices, float)
    prices = prices[np.isfinite(prices) & (prices > 0)]
    T = len(prices)
    # tick scale, matched to the gauge (the two agree to <1% on small steps)
    r1 = (np.diff(np.log(prices)) if gauge == "log"
          else np.diff(prices) / prices[:-1])
    sd = float(np.std(r1[np.isfinite(r1)]))

    # Threshold range is set RELATIVE to the feed's own tick volatility. The FX
    # papers use a fixed 0.035%-5% because FX ticks are ~1e-4; this engine's tick
    # sd can be ~1e-2, so a fixed grid would put every threshold below one tick
    # (a DC every tick) and measure nothing. Logarithmic steps, as in sec. 3.3.
    #
    # DISCRETIZATION BIAS (0809.1040 sec 2.1, and verified here on Brownian motion):
    # for delta near the tick size, a single tick overshoots the threshold and
    # systematically inflates <omega> and flattens the N exponent. Measured on a
    # 400k-tick BM with sigma=0.002 (theory: E_N=-2, <omega>/delta=1):
    #     delta from  1x tick-sd : E_N = -1.66, <omega>/delta = 1.166
    #     delta from  3x tick-sd : E_N = -1.79, <omega>/delta = 1.086
    #     delta from  5x tick-sd : E_N = -1.84, <omega>/delta = 1.057
    #     delta from 10x tick-sd : E_N = -1.85, <omega>/delta = 1.003   <- clean
    # Hence the default floor of 8x. The ceiling trades off against feed length:
    # N ~ sigma^2 T / delta^2, so large delta yields too few events to average.
    deltas = np.exp(np.linspace(np.log(delta_lo_mult * sd),
                                np.log(delta_hi_mult * sd), n_deltas))
    dts = np.unique(np.round(np.exp(np.linspace(np.log(1), np.log(max(T // 50, 2)),
                                                n_dts))).astype(int))

    rows = [m for d in deltas if (m := measure(prices, float(d), T, min_events, gauge)) is not None]
    if len(rows) < 3:
        raise SystemExit("too few usable thresholds — feed too short or too smooth")
    D = np.array([r["delta"] for r in rows])
    res = {"sd_tick": sd, "T": T, "rows": rows, "deltas": D}

    E_N,  C_N,  R_N  = fit(D, np.array([r["N_hat"] for r in rows]))
    E_os, C_os, R_os = fit(D, np.array([r["os_mean"] for r in rows]))
    E_ov, C_ov, R_ov = fit(D, np.array([r["os_var2"] for r in rows]))
    E_tm, C_tm, R_tm = fit(D, np.array([r["tm_mean"] for r in rows]))
    E_cl, C_cl, R_cl = fit(D, np.array([r["coastline"] for r in rows]))
    sq = np.array([sq_returns(prices, int(dt)) for dt in dts])
    E_r,  C_r,  R_r  = fit(dts.astype(float), sq)

    res["fits"] = {
        "N_hat(delta)":        (E_N,  C_N,  R_N,  -2.0),
        "<omega(delta)>":      (E_os, C_os, R_os,  1.0),
        "<omega-delta>_2":     (E_ov, C_ov, R_ov,  2.0),
        "<tm(delta)>":         (E_tm, C_tm, R_tm,  1.0),
        "coastline(delta)":    (E_cl, C_cl, R_cl, -1.0),
        "<r(dt)>_2":           (E_r,  C_r,  R_r,   1.0),
    }

    # the bridge, eq (30): C^T = <r(dt)>_2 / dt   ~=   <omega-delta>_2 * N_hat = C^tau
    res["C_T"] = sq / dts
    res["C_tau"] = np.array([r["os_var2"] * r["N_hat"] for r in rows])
    res["dts"] = dts
    res["sq"] = sq

    # ── report ───────────────────────────────────────────────────────────────
    print(f"feed: {T:,} ticks   tick sd(r) = {sd:.4g}   gauge = {gauge}")
    print(f"delta grid: {D[0]:.4g} .. {D[-1]:.4g}  ({D[0]*100:.2f}% .. {D[-1]*100:.2f}%)\n")
    print(f"{'law':>18} | {'exponent E':>10} {'C':>12} {'adj R2':>8} | {'BM/theory':>9}")
    for k, (E, C, R, th) in res["fits"].items():
        print(f"{k:>18} | {E:>10.3f} {C:>12.4g} {R:>8.4f} | {th:>9.1f}")
    ct, ctau = float(np.median(res["C_T"])), float(np.median(res["C_tau"]))
    print(f"\nbridge eq (30):  C^T = {ct:.4g}   C^tau = {ctau:.4g}   "
          f"ratio C^tau/C^T = {ctau/ct:.3f}   (lambda = {ct/ctau:.3f})")
    print(f"  volatility component  N_hat(delta) : exponent {E_N:+.3f}")
    print(f"  liquidity  component  <omega-delta>_2 : exponent {E_ov:+.3f}")
    print(f"  <omega>/delta over the grid: "
          f"{np.mean([r['os_mean']/r['delta'] for r in rows]):.3f}  (BM/FX: ~1)")

    if plot_path:
        _plot(res, plot_path)
    return res


def _plot(res: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows, D = res["rows"], res["deltas"]
    fig, ax = plt.subplots(2, 3, figsize=(14, 8))
    fig.suptitle("Intrinsic-time scaling laws (Glattfelder-Dupuis-Olsen 2011; "
                 "Glattfelder-Golub 2022)", fontsize=11, fontweight="bold")

    def panel(a, x, y, xlabel, ylabel, title, E, C, ref=None):
        a.loglog(x, y, "o", ms=4, color="#2563EB")
        m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
        if m.sum() > 2 and np.isfinite(E):
            xs = np.array([x[m].min(), x[m].max()])
            a.loglog(xs, (xs / C) ** E, "-", color="#B45309", lw=1.4,
                     label=f"E = {E:.3f}")
        if ref is not None:
            a.loglog(x, ref, ":", color="#6B7280", lw=1.2, label="theory")
        a.set_xlabel(xlabel); a.set_ylabel(ylabel); a.set_title(title, fontsize=10)
        a.legend(fontsize=8); a.grid(True, which="both", ls=":", alpha=0.4)

    f = res["fits"]
    panel(ax[0, 0], D, np.array([r["N_hat"] for r in rows]), "delta", "N(delta)/T",
          "Law (0b): DC count  [VOLATILITY]", f["N_hat(delta)"][0], f["N_hat(delta)"][1])
    panel(ax[0, 1], D, np.array([r["os_mean"] for r in rows]), "delta", "<omega>",
          "Law (9) os: mean overshoot", f["<omega(delta)>"][0], f["<omega(delta)>"][1], ref=D)
    panel(ax[0, 2], D, np.array([r["os_var2"] for r in rows]), "delta", "<omega-delta>_2",
          "Eq (27): OS variability  [LIQUIDITY]", f["<omega-delta>_2"][0], f["<omega-delta>_2"][1],
          ref=D ** 2)
    panel(ax[1, 0], D, np.array([r["tm_mean"] for r in rows]), "delta", "<|dx_tm|>",
          "Law (9) tm: total move (~2 delta)", f["<tm(delta)>"][0], f["<tm(delta)>"][1], ref=2 * D)
    panel(ax[1, 1], res["dts"].astype(float), res["sq"], "dt (ticks)", "<r(dt)>_2",
          "Eq (24): squared returns", f["<r(dt)>_2"][0], f["<r(dt)>_2"][1])

    a = ax[1, 2]
    a.semilogy(range(len(res["C_T"])), res["C_T"], "o-", ms=3, color="#2563EB", label="C^T (physical)")
    a.semilogy(range(len(res["C_tau"])), res["C_tau"], "s-", ms=3, color="#B45309", label="C^tau (intrinsic)")
    a.set_xlabel("threshold index"); a.set_ylabel("C")
    a.set_title("Eq (30): the invariant  C^T ?= C^tau", fontsize=10)
    a.legend(fontsize=8); a.grid(True, which="both", ls=":", alpha=0.4)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=140, bbox_inches="tight")
    print(f"\nwrote {path}")


def load_csv(path: str, col: str = "p_int") -> np.ndarray:
    import csv as _csv
    with open(path) as fh:
        rd = _csv.DictReader(fh)
        return np.array([float(row[col]) for row in rd])


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "price_feed.csv"
    g = sys.argv[2] if len(sys.argv) > 2 else "log"   # "log" | "relative"
    analyse(load_csv(src), gauge=g)
