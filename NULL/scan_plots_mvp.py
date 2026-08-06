"""
scan_plots_mvp.py — figures for the block parameter scan (scan_mvp.py).

Reads scan_results.jsonl and writes two figures:

  scan_prices_<tag>.png — one panel per arm, all seeds' price paths
                          overlaid as ln(p/x_0): the qualitative story.
  scan_stats_<tag>.png  — per-arm strips of the quantitative measures:
                          drift magnitude, tick volatility, fat tails,
                          volatility clustering, DC-count exponent,
                          overshoot/delta ratio.

Arm code letters (default concept capitalised):
    1st: capital  P=pareto  N=normal
    2nd: bands    F=fixed   N=normal
    3rd: closing  C=clock   N=normal
"PFC" is the frozen null; "NNN" has all three blocks switched.
"""

from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "scan_results.jsonl")

# arms ordered by number of switched blocks (null first, all-switched last)
ARM_ORDER = ["PFC", "NFC", "PNC", "PFN", "NNC", "NFN", "PNN", "NNN"]
ARM_LABEL = {
    "PFC": "PFC — the null",
    "NFC": "NFC — capital normal",
    "PNC": "PNC — bands normal",
    "PFN": "PFN — closing normal",
    "NNC": "NNC — cap+bands",
    "NFN": "NFN — cap+closing",
    "PNN": "PNN — bands+closing",
    "NNN": "NNN — all switched",
}
SEED_COLORS = ["#2563EB", "#C2680A", "#15803D", "#7C3AED", "#DB2777", "#0891B2"]


def load_rows() -> list[dict]:
    """Read every finished run from the JSONL file."""
    rows = []
    with open(IN) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def plot_prices(rows: list[dict], save_path: str, show: bool = False) -> str:
    """One panel per arm; every seed's ln(p/x_0) path overlaid."""
    import matplotlib.pyplot as plt

    n, T = rows[0]["n"], rows[0]["T"]
    seeds = sorted({r["seed"] for r in rows})
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)

    # common symmetric y-range so panels are visually comparable
    y_max = 0.0
    for r in rows:
        path = np.log(np.asarray(r["path"]))
        y_max = max(y_max, float(np.max(np.abs(path))))
    y_max = min(y_max * 1.05, 6.0)

    fig, axes = plt.subplots(2, 4, figsize=(17, 7), sharey=True)
    fig.suptitle(f"Block scan — emergent price, ln(p/x_0)  |  n={n}, "
                 f"T={T:,}, seeds {seeds}", fontsize=12, fontweight="bold")
    for ax, arm in zip(axes.flat, ARM_ORDER):
        ax.axhline(0, color="#9CA3AF", lw=0.8, ls=":")
        for r in sorted(by_arm.get(arm, []), key=_seed_of):
            path = np.log(np.asarray(r["path"]))
            x = np.linspace(0, T, len(path))
            color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
            ax.plot(x, path, lw=0.9, color=color, label=f"seed {r['seed']}")
        ax.set_title(ARM_LABEL[arm], fontsize=10,
                     fontweight="bold" if arm == "PFC" else "normal")
        ax.set_ylim(-y_max, y_max)
        ax.grid(True, ls=":", alpha=0.35)
    for ax in axes[1]:
        ax.set_xlabel("tick")
    for ax in axes[:, 0]:
        ax.set_ylabel("ln(p / x_0)")
    axes[0, 0].legend(fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return save_path


def _seed_of(row: dict) -> int:
    """Sort key: the run's seed (named function — breakpointable)."""
    return row["seed"]


def plot_stats(rows: list[dict], save_path: str, show: bool = False) -> str:
    """Six per-arm strip panels: each dot is one seed; the bar is the
    across-seed mean. References drawn where a theory value exists."""
    import matplotlib.pyplot as plt

    n, T = rows[0]["n"], rows[0]["T"]
    seeds = sorted({r["seed"] for r in rows})
    x_of = {}
    for i, arm in enumerate(ARM_ORDER):
        x_of[arm] = i

    panels = [
        ("abs_ln_drift", "|ln drift|  (price displacement)", None, "linear"),
        ("sd_rob", "robust tick sd(r)", None, "linear"),
        ("kurt_m1", "excess kurtosis (m=1)  — fat tails", 0.0, "log"),
        ("acf_abs_L1", "ACF(|r|) at lag 1 — clustering", 0.0, "linear"),
        ("E_N", "DC-count exponent E_N", -2.0, "linear"),
        ("os_ratio", "⟨ω⟩/δ — overshoot ratio", 1.0, "linear"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
    fig.suptitle(f"Block scan — measures per arm  |  n={n}, T={T:,}, "
                 f"{len(seeds)} seeds (dot = one seed, bar = mean)",
                 fontsize=12, fontweight="bold")
    for ax, (key, title, ref, scale) in zip(axes.flat, panels):
        for r in rows:
            if key == "abs_ln_drift":
                val = abs(r["ln_drift"])
            else:
                val = r[key]
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            x = x_of[r["arm"]]
            color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
            ax.plot(x, val, "o", ms=5, color=color, alpha=0.85)
        # per-arm mean bars
        for arm in ARM_ORDER:
            vals = []
            for r in rows:
                if r["arm"] != arm:
                    continue
                v = abs(r["ln_drift"]) if key == "abs_ln_drift" else r[key]
                if v is not None and np.isfinite(v):
                    vals.append(v)
            if vals:
                ax.plot([x_of[arm] - 0.25, x_of[arm] + 0.25],
                        [np.mean(vals)] * 2, "-", color="#111827", lw=2)
        if ref is not None:
            ax.axhline(ref, color="#9CA3AF", lw=1.0, ls="--",
                       label={-2.0: "BM theory −2", 1.0: "BM ⟨ω⟩=δ",
                              0.0: "0"}[ref])
            ax.legend(fontsize=7, frameon=False)
        if scale == "log":
            ax.set_yscale("log")
        ax.set_xticks(range(len(ARM_ORDER)))
        ax.set_xticklabels(ARM_ORDER, fontsize=9)
        ax.axvspan(-0.5, 0.5, color="#2563EB", alpha=0.06)   # the null column
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
    """Across-seed means per arm, one line per arm."""
    print(f"\n{'arm':>4} {'|drift|':>8} {'sd_rob':>8} {'zero%':>6} "
          f"{'kurt_m1':>9} {'ACF|r|L1':>9} {'E_N':>7} {'⟨ω⟩/δ':>7} "
          f"{'alive%':>7} {'trades':>9}")
    for arm in ARM_ORDER:
        sub = [r for r in rows if r["arm"] == arm]
        if not sub:
            continue

        def mean_of(key, transform=None):
            vals = []
            for r in sub:
                v = r[key]
                if transform is not None:
                    v = transform(v)
                if v is not None and np.isfinite(v):
                    vals.append(v)
            return np.mean(vals) if vals else float("nan")

        print(f"{arm:>4} {mean_of('ln_drift', abs):>8.3f} "
              f"{mean_of('sd_rob'):>8.4f} {100*mean_of('zero_frac'):>5.1f}% "
              f"{mean_of('kurt_m1'):>9.1f} {mean_of('acf_abs_L1'):>9.3f} "
              f"{mean_of('E_N'):>7.2f} {mean_of('os_ratio'):>7.2f} "
              f"{100*mean_of('alive_frac'):>6.1f}% {mean_of('n_trades'):>9.0f}")


if __name__ == "__main__":
    rows = load_rows()
    n, T = rows[0]["n"], rows[0]["T"]
    tag = f"mvp_scan_n{n}_T{T}"
    print(f"{len(rows)} runs loaded")
    print_table(rows)
    plot_prices(rows, os.path.join(HERE, f"scan_prices_{tag}.png"))
    plot_stats(rows, os.path.join(HERE, f"scan_stats_{tag}.png"))
