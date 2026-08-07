"""
scan_plots_mvp.py — figures for the block parameter scan (scan_mvp.py).

Reads scan_results.jsonl and writes two figures:

  scan_prices_<tag>.png — one panel per arm, all seeds' price paths
                          overlaid as ln(p/x_0): the qualitative story.
  scan_stats_<tag>.png  — per-arm strips of the quantitative measures:
                          drift magnitude, tick volatility, fat tails,
                          volatility clustering, DC-count exponent,
                          overshoot/delta ratio.

Arm code, one letter per block:
    1st  capital  P=pareto  N=normal
    2nd  bands    F=fixed   N=normal
    3rd  closing  C=clock   N=normal
    4th  size     F=fixed   N=normal  (per-agent q_i)
"PFCF" is the legacy null, "NFNF" the current default, "NNNN" all switched.
Rows from older 2^3 scans (three-letter arms) are read as size="fixed".
"""

from __future__ import annotations

import itertools
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "scan_results.jsonl")

LEGACY_NULL = "PFCF"
CURRENT_DEFAULT = "NFNF"

# which letter means "switched to normal" in each slot
_NORMAL_AT = ("N", "N", "N", "N")
_BLOCK_NAME = ("cap", "bands", "close", "size")


def _n_switched(code: str) -> int:
    """How many blocks of this arm are on their normal/heterogeneous arm."""
    count = 0
    for letter, normal_letter in zip(code, _NORMAL_AT):
        if letter == normal_letter:
            count += 1
    return count


def _all_codes() -> list[str]:
    """Every 4-letter arm code, ordered: fewest switches first (the legacy
    null leads), ties alphabetical."""
    codes = []
    for a, b, c, d in itertools.product("PN", "FN", "CN", "FN"):
        codes.append(a + b + c + d)
    codes.sort(key=_order_key)
    return codes


def _order_key(code: str) -> tuple:
    """Sort key: number of switched blocks, then the code itself."""
    return (_n_switched(code), code)


def _label(code: str) -> str:
    """Human label for one arm."""
    if code == LEGACY_NULL:
        return f"{code} — legacy null"
    if code == CURRENT_DEFAULT:
        return f"{code} — CURRENT DEFAULT"
    parts = []
    for letter, normal_letter, name in zip(code, _NORMAL_AT, _BLOCK_NAME):
        if letter == normal_letter:
            parts.append(name)
    return f"{code} — {'+'.join(parts)}"


ARM_ORDER = _all_codes()
SEED_COLORS = ["#2563EB", "#C2680A", "#15803D", "#7C3AED", "#DB2777", "#0891B2"]


def load_rows() -> list[dict]:
    """Read every finished run; normalise older three-letter arm codes
    (pre-size scans) to four letters with size='fixed'."""
    rows = []
    with open(IN) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if len(r["arm"]) == 3:
                r["arm"] = r["arm"] + "F"
                r.setdefault("size", "fixed")
            rows.append(r)
    return rows


def _seed_of(row: dict) -> int:
    """Sort key: the run's seed (named function — breakpointable)."""
    return row["seed"]


def plot_prices(rows: list[dict], save_path: str, show: bool = False) -> str:
    """One panel per arm present in the data; every seed's ln(p/x_0) path."""
    import matplotlib.pyplot as plt

    n, T = rows[0]["n"], rows[0]["T"]
    seeds = sorted({r["seed"] for r in rows})
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    arms = [a for a in ARM_ORDER if a in by_arm]

    # x_0 per row: older rows lack it; infer from the first path point
    y_max = 0.0
    for r in rows:
        path = np.asarray(r["path"])
        x0 = r.get("x_0", path[0])
        y_max = max(y_max, float(np.max(np.abs(np.log(path / x0)))))
    y_max = min(y_max * 1.05, 6.0)

    n_cols = 4
    n_rows_fig = (len(arms) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows_fig, n_cols,
                             figsize=(17, 3.4 * n_rows_fig), sharey=True,
                             squeeze=False)
    fig.suptitle(f"Block scan — emergent price, ln(p/x_0)  |  n={n}, "
                 f"T={T:,}, seeds {seeds}", fontsize=12, fontweight="bold")
    for ax, arm in zip(axes.flat, arms):
        ax.axhline(0, color="#9CA3AF", lw=0.8, ls=":")
        for r in sorted(by_arm[arm], key=_seed_of):
            path = np.asarray(r["path"])
            x0 = r.get("x_0", path[0])
            lnp = np.log(path / x0)
            x = np.linspace(0, T, len(lnp))
            color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
            ax.plot(x, lnp, lw=0.9, color=color, label=f"seed {r['seed']}")
        bold = arm in (LEGACY_NULL, CURRENT_DEFAULT)
        ax.set_title(_label(arm), fontsize=9,
                     fontweight="bold" if bold else "normal")
        ax.set_ylim(-y_max, y_max)
        ax.grid(True, ls=":", alpha=0.35)
    for ax in axes.flat[len(arms):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("tick")
    for row_axes in axes:
        row_axes[0].set_ylabel("ln(p / x_0)")
    axes[0, 0].legend(fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return save_path


def plot_stats(rows: list[dict], save_path: str, show: bool = False) -> str:
    """Six per-arm strip panels: each dot is one seed; the bar is the
    across-seed mean. The legacy null's column is shaded blue, the current
    default's green. References drawn where a theory value exists."""
    import matplotlib.pyplot as plt

    n, T = rows[0]["n"], rows[0]["T"]
    seeds = sorted({r["seed"] for r in rows})
    arms = [a for a in ARM_ORDER if any(r["arm"] == a for r in rows)]
    x_of = {}
    for i, arm in enumerate(arms):
        x_of[arm] = i

    panels = [
        ("abs_ln_drift", "|ln drift|  (price displacement)", None, "linear"),
        ("sd_rob", "robust tick sd(r)", None, "linear"),
        ("kurt_m1", "excess kurtosis (m=1)  — fat tails", 0.0, "log"),
        ("acf_abs_L1", "ACF(|r|) at lag 1 — clustering", 0.0, "linear"),
        ("E_N", "DC-count exponent E_N", -2.0, "linear"),
        ("os_ratio", "⟨ω⟩/δ — overshoot ratio", 1.0, "linear"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(17, 8.5))
    fig.suptitle(f"Block scan — measures per arm  |  n={n}, T={T:,}, "
                 f"{len(seeds)} seeds (dot = one seed, bar = mean)  |  "
                 f"blue = legacy null, green = current default",
                 fontsize=12, fontweight="bold")
    for ax, (key, title, ref, scale) in zip(axes.flat, panels):
        for r in rows:
            if key == "abs_ln_drift":
                val = abs(r["ln_drift"])
            else:
                val = r.get(key)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            x = x_of[r["arm"]]
            color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
            ax.plot(x, val, "o", ms=4, color=color, alpha=0.85)
        for arm in arms:
            vals = []
            for r in rows:
                if r["arm"] != arm:
                    continue
                v = abs(r["ln_drift"]) if key == "abs_ln_drift" else r.get(key)
                if v is not None and np.isfinite(v):
                    vals.append(v)
            if vals:
                ax.plot([x_of[arm] - 0.3, x_of[arm] + 0.3],
                        [np.mean(vals)] * 2, "-", color="#111827", lw=2)
        if ref is not None:
            ax.axhline(ref, color="#9CA3AF", lw=1.0, ls="--",
                       label={-2.0: "BM theory −2", 1.0: "BM ⟨ω⟩=δ",
                              0.0: "0"}[ref])
            ax.legend(fontsize=7, frameon=False)
        if scale == "log":
            ax.set_yscale("log")
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms, fontsize=7, rotation=45, ha="right")
        if LEGACY_NULL in x_of:
            ax.axvspan(x_of[LEGACY_NULL] - 0.5, x_of[LEGACY_NULL] + 0.5,
                       color="#2563EB", alpha=0.07)
        if CURRENT_DEFAULT in x_of:
            ax.axvspan(x_of[CURRENT_DEFAULT] - 0.5,
                       x_of[CURRENT_DEFAULT] + 0.5,
                       color="#15803D", alpha=0.10)
        ax.set_title(title, fontsize=10)
        ax.grid(True, axis="y", ls=":", alpha=0.35)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return save_path


def print_table(rows: list[dict]) -> None:
    """Across-seed means per arm, one line per arm present in the data."""
    has_phase = "t_lock" in rows[0]
    hdr = (f"\n{'arm':>5} {'|drift|':>8} {'sd_rob':>8} {'zero%':>6} "
           f"{'kurt_m1':>9} {'ACF|r|L1':>9} {'E_N':>7} {'⟨ω⟩/δ':>7} "
           f"{'alive%':>7} {'trades':>9}")
    if has_phase:
        hdr += f" {'t_lock':>9} {'tooth_T':>8} {'tooth_sz':>8}"
    print(hdr)
    for arm in ARM_ORDER:
        sub = [r for r in rows if r["arm"] == arm]
        if not sub:
            continue

        def mean_of(key, transform=None):
            vals = []
            for r in sub:
                v = r.get(key)
                if v is None:
                    continue
                if transform is not None:
                    v = transform(v)
                if np.isfinite(v):
                    vals.append(v)
            return np.mean(vals) if vals else float("nan")

        line = (f"{arm:>5} {mean_of('ln_drift', abs):>8.3f} "
                f"{mean_of('sd_rob'):>8.4f} {100*mean_of('zero_frac'):>5.1f}% "
                f"{mean_of('kurt_m1'):>9.1f} {mean_of('acf_abs_L1'):>9.3f} "
                f"{mean_of('E_N'):>7.2f} {mean_of('os_ratio'):>7.2f} "
                f"{100*mean_of('alive_frac'):>6.1f}% {mean_of('n_trades'):>9.0f}")
        if has_phase:
            line += (f" {mean_of('t_lock'):>9.0f} {mean_of('tooth_period'):>8.0f} "
                     f"{mean_of('tooth_size'):>8.2f}")
        print(line)


if __name__ == "__main__":
    rows = load_rows()
    n, T = rows[0]["n"], rows[0]["T"]
    tag = f"mvp_scan_n{n}_T{T}"
    print(f"{len(rows)} runs loaded, arms present: "
          f"{sorted({r['arm'] for r in rows}, key=_order_key)}")
    print_table(rows)
    plot_prices(rows, os.path.join(HERE, f"scan_prices_{tag}.png"))
    plot_stats(rows, os.path.join(HERE, f"scan_stats_{tag}.png"))
