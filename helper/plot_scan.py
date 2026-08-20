"""
plot_scan.py — figures and tables for scan_simulation_mvp.py results.

Works on any scan family. Set SCAN below (mirroring the scan script) or
pass a path to load_rows():

  "blocks"  reads scan_results.jsonl; runs are grouped by their four-
            letter arm code (capital P/N, bands F/N, closing C/N,
            size F/N — "PFCF" is the frozen default). Rows from older
            three-letter scans are read as size="fixed".
  any other family ("bands", "peaky", "qsweep", ...) reads
            scan_results_<family>.jsonl; runs are grouped by their
            "label" field, in the order the scan defined them.

Outputs (into eval/runs, family name in the file name):
  scan_prices_*.png — one panel per group, all seeds' price paths
                      overlaid as ln(p/x_0): the qualitative story.
  scan_stats_*.png  — per-group strips of the quantitative measures
                      (drift, volatility, tails, clustering, DC laws).
  scan_wall_*.png   — the wealth-wall witnesses per group.
  print_table()     — the numbers behind the figures.
"""

from __future__ import annotations

import itertools
import json
import os
import sys

from typing import Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(HERE)                      # repo root
sys.path.insert(0, os.path.join(_ROOT, "helper"))
OUT = os.path.join(_ROOT, "eval", "scans")   # all run outputs land here
os.makedirs(OUT, exist_ok=True)
def _default_in() -> str:
    return os.path.join(OUT, "scan_results.jsonl" if SCAN == "blocks"
                        else f"scan_results_{SCAN}.jsonl")

SCAN = "blocks"          # which family's results to read (see docstring)

FROZEN_DEFAULT = "PFCF"  # highlighted in blocks figures


def group_of(r: dict) -> str:
    """A row's group: the family label if present, else the arm code."""
    return r.get("label", r["arm"])

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
    """Panel title: family labels pass through; blocks arm codes get their
    knob spelling, with the frozen default marked."""
    if len(code) != 4 or any(c not in "PNFC" for c in code):
        return code                       # a family label, not an arm code
    parts = [f"cap={'pareto' if code[0] == 'P' else 'normal'}",
             f"band={'fixed' if code[1] == 'F' else 'normal'}",
             f"close={'clock' if code[2] == 'C' else 'normal'}",
             f"size={'fixed' if code[3] == 'F' else 'normal'}"]
    tagline = f"{code}  ({', '.join(parts)})"
    if code == FROZEN_DEFAULT:
        tagline += "  — the frozen default"
    return tagline


ARM_ORDER = _all_codes()
SEED_COLORS = ["#2563EB", "#C2680A", "#15803D", "#7C3AED", "#DB2777", "#0891B2"]


def load_rows(path: Optional[str] = None) -> list[dict]:
    """Read every finished run; normalise older three-letter arm codes
    (pre-size scans) to four letters with size='fixed'."""
    if path is None:
        path = _default_in()
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if len(r["arm"]) == 3:
                r["arm"] = r["arm"] + "F"
                r.setdefault("size", "fixed")
            _backfill_wall(r)
            rows.append(r)
    return rows


def _backfill_wall(r: dict) -> None:
    """Rows from scans predating the wall metrics carry the raw material
    (decimated price + wealth paths, t_lock) but not the derived numbers.
    Compute them here so an existing expensive JSONL never needs re-running.
    CAVEAT: paths are decimated (~T/500 tick resolution), so the backfilled
    n_reentries is a LOWER BOUND — escapes shorter than the decimation step
    are invisible. wall_side and ammo_at_lock are effectively exact."""
    if "wall_side" in r or "path" not in r or "t_lock" not in r:
        return
    path = np.asarray(r["path"], float)
    x0 = r.get("x_0", path[0])
    lnp = np.log(path / x0)
    T = r["T"]
    idx_lock = min(len(lnp) - 1, int(round(r["t_lock"] / T * (len(lnp) - 1))))
    outside = np.abs(lnp) > 2.5
    if not r.get("locked") or not outside.any():
        r["wall_side"] = 0
        r["ammo_at_lock"] = float("nan")
        r["n_reentries"] = 0
        return
    r["wall_side"] = 1 if float(np.mean(lnp[idx_lock:])) > 0 else -1
    ammo = float("nan")
    key = "eur_long_path" if r["wall_side"] > 0 else "btc_short_path"
    if key in r:
        w = np.asarray(r[key], float)
        j = min(len(w) - 1, int(round(r["t_lock"] / T * (len(w) - 1))))
        if w[0]:
            ammo = float(w[j] / w[0])
    r["ammo_at_lock"] = ammo
    first_out = int(np.argmax(outside))
    later = outside[first_out:]
    reentries = 0
    for i in range(1, len(later)):
        if later[i - 1] and not later[i]:
            reentries += 1
    r["n_reentries"] = int(reentries)      # lower bound (decimated path)


def _groups_in(rows: list[dict]) -> list[str]:
    """Groups present, in display order: arm-code order for blocks,
    first-appearance order for family labels."""
    if "label" in rows[0]:
        return list(dict.fromkeys(group_of(r) for r in rows))
    return [a for a in ARM_ORDER if any(r["arm"] == a for r in rows)]


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
        by_arm.setdefault(group_of(r), []).append(r)
    arms = [a for a in _groups_in(rows) if a in by_arm]

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
    gvals = _group_values(rows, GROUP_BY) if GROUP_BY else None
    for ax, arm in zip(axes.flat, arms):
        ax.axhline(0, color="#9CA3AF", lw=0.8, ls=":")
        for r in sorted(by_arm[arm], key=_seed_of):
            path = np.asarray(r["path"])
            x0 = r.get("x_0", path[0])
            lnp = np.log(path / x0)
            x = np.linspace(0, T, len(lnp))
            if gvals is not None:
                v = r.get(GROUP_BY)
                color = SEED_COLORS[gvals.index(v) % len(SEED_COLORS)]
                label = f"{GROUP_BY}={v}"
            else:
                color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
                label = f"seed {r['seed']}"
            ax.plot(x, lnp, lw=0.9, color=color, label=label)
        bold = arm == FROZEN_DEFAULT
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
    handles, labels = axes[0, 0].get_legend_handles_labels()
    seen = dict(zip(labels, handles))          # dedupe repeated sweep labels
    axes[0, 0].legend(seen.values(), seen.keys(), fontsize=7, frameon=False)
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
    if GROUP_BY:
        # sweep mode: one x-position per swept value, arms ignored
        arms = _group_values(rows, GROUP_BY)
        x_of = {}
        for i, v in enumerate(arms):
            x_of[v] = i
        cat_of = _cat_by_group
    else:
        arms = _groups_in(rows)
        x_of = {}
        for i, arm in enumerate(arms):
            x_of[arm] = i
        cat_of = _cat_by_arm

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
                 f"blue = the frozen default (blocks scan)",
                 fontsize=12, fontweight="bold")
    for ax, (key, title, ref, scale) in zip(axes.flat, panels):
        for r in rows:
            if key == "abs_ln_drift":
                val = abs(r["ln_drift"])
            else:
                val = r.get(key)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            x = x_of[cat_of(r)]
            color = SEED_COLORS[seeds.index(r["seed"]) % len(SEED_COLORS)]
            ax.plot(x, val, "o", ms=4, color=color, alpha=0.85)
        for arm in arms:
            vals = []
            for r in rows:
                if cat_of(r) != arm:
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
        if GROUP_BY:
            ax.set_xticklabels([f"{GROUP_BY}={v}" for v in arms],
                               fontsize=7, rotation=45, ha="right")
        else:
            ax.set_xticklabels(arms, fontsize=7, rotation=45, ha="right")
        if not GROUP_BY and FROZEN_DEFAULT in x_of:
            ax.axvspan(x_of[FROZEN_DEFAULT] - 0.5, x_of[FROZEN_DEFAULT] + 0.5,
                       color="#2563EB", alpha=0.07)
        if not GROUP_BY and FROZEN_DEFAULT in x_of:
            ax.axvspan(x_of[FROZEN_DEFAULT] - 0.5,
                       x_of[FROZEN_DEFAULT] + 0.5,
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


def plot_wall(rows: list[dict], save_path: str, show: bool = False,
              value_weighted: bool = False) -> str:
    """Dark corner 2, the wall caught red-handed: per arm, each run's two
    ammunition lines over time, with a vertical dash at the lock tick.

    value_weighted=False — raw COIN per side, fraction of start: the longs'
    EUR (pushes the price UP) and the shorts' BTC (pushes it DOWN). The
    n=500 scan showed the loser still holds 60-100%% of its coin at lock:
    coin is the wrong currency for pushing power.

    value_weighted=True — pushing POWER: each side's fuel measured in the
    coin it BUYS, fraction of start. Up-fuel = eur_long / p (how much BTC
    the longs' EUR can still lift); down-fuel = btc_short * p (how much
    EUR the shorts' BTC can still absorb). The price devalues the loser's
    fuel as it moves: the value-wall prediction is that the loser's line
    hits ~0 exactly at the dash."""
    import matplotlib.pyplot as plt

    rows = [r for r in rows if "eur_long_path" in r]
    if not rows:
        print("plot_wall: no wealth paths in these rows (older scan) — skipped")
        return ""
    n, T = rows[0]["n"], rows[0]["T"]
    by_arm = {}
    for r in rows:
        by_arm.setdefault(group_of(r), []).append(r)
    arms = [a for a in _groups_in(rows) if a in by_arm]

    n_cols = 4
    n_rows_fig = (len(arms) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows_fig, n_cols,
                             figsize=(17, 3.2 * n_rows_fig),
                             sharey=not value_weighted,
                             squeeze=False)
    if value_weighted:
        head = ("The VALUE wall — pushing power per side, in the coin it "
                "buys, fraction of start")
        legend = ("BLUE = longs' EUR/p (BTC it can still lift), ORANGE = "
                  "shorts' BTC*p (EUR it can still absorb)")
    else:
        head = "The wealth wall — pushing coin per side, fraction of start"
        legend = "BLUE = longs' EUR (up-fuel), ORANGE = shorts' BTC (down-fuel)"
    fig.suptitle(f"{head}  |  n={n}, T={T:,}  |  {legend}, dash = lock tick",
                 fontsize=11, fontweight="bold")
    for ax, arm in zip(axes.flat, arms):
        for r in sorted(by_arm[arm], key=_seed_of):
            el = np.asarray(r["eur_long_path"], float)
            bs = np.asarray(r["btc_short_path"], float)
            if value_weighted:
                # resample the price path onto each wealth path's grid (both
                # are ~500-point decimations of the same T ticks)
                price = np.asarray(r["path"], float)
                xp = np.linspace(0.0, 1.0, len(price))
                el_p = np.interp(np.linspace(0.0, 1.0, len(el)), xp, price)
                bs_p = np.interp(np.linspace(0.0, 1.0, len(bs)), xp, price)
                el = el / el_p          # EUR fuel valued in the BTC it buys
                bs = bs * bs_p          # BTC fuel valued in the EUR it buys
            x_el = np.linspace(0, T, len(el))
            x_bs = np.linspace(0, T, len(bs))
            ax.plot(x_el, el / el[0], lw=0.8, color="#2563EB", alpha=0.6)
            ax.plot(x_bs, bs / bs[0], lw=0.8, color="#C2680A", alpha=0.6)
            if r.get("locked"):
                ax.axvline(r["t_lock"], color="#111827", lw=0.7, ls="--",
                           alpha=0.5)
        bold = arm == FROZEN_DEFAULT
        ax.set_title(_label(arm), fontsize=9,
                     fontweight="bold" if bold else "normal")
        if value_weighted:
            # locked runs span 0.05x..100x+ (a EUR pile lifts enormous BTC
            # once the price collapses): multiplicative range -> log axis,
            # per-panel autoscale, guide line at 1
            ax.set_yscale("log")
            ax.axhline(1.0, color="#9CA3AF", lw=0.6, ls=":")
        else:
            ax.set_ylim(0, 1.05)
        ax.grid(True, ls=":", alpha=0.35)
    for ax in axes.flat[len(arms):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("tick")
    for row_axes in axes:
        row_axes[0].set_ylabel("fraction of start")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    print(f"wrote {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return save_path


def _cat_by_arm(r: dict):
    """Stats category in scan mode: the arm code."""
    return group_of(r)


def _cat_by_group(r: dict):
    """Stats category in sweep mode: the swept key's value."""
    return r.get(GROUP_BY)


def print_table(rows: list[dict]) -> None:
    """Across-seed means per arm, one line per arm present in the data."""
    has_phase = "t_lock" in rows[0]
    hdr = (f"\n{'group':>14} {'|drift|':>8} {'sd_rob':>8} {'zero%':>6} "
           f"{'kurt_m1':>9} {'ACF|r|L1':>9} {'E_N':>7} {'⟨ω⟩/δ':>7} "
           f"{'alive%':>7} {'trades':>9}")
    if has_phase:
        hdr += f" {'t_lock':>9} {'tooth_T':>8} {'tooth_sz':>8}"
    has_wall = "wall_side" in rows[0]
    if has_wall:
        hdr += f" {'wall':>7} {'ammo@lk':>8} {'re-ent':>7}"
    print(hdr)
    for arm in _groups_in(rows):
        sub = [r for r in rows if group_of(r) == arm]
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

        line = (f"{arm:>14} {mean_of('ln_drift', abs):>8.3f} "
                f"{mean_of('sd_rob'):>8.4f} {100*mean_of('zero_frac'):>5.1f}% "
                f"{mean_of('kurt_m1'):>9.1f} {mean_of('acf_abs_L1'):>9.3f} "
                f"{mean_of('E_N'):>7.2f} {mean_of('os_ratio'):>7.2f} "
                f"{100*mean_of('alive_frac'):>6.1f}% {mean_of('n_trades'):>9.0f}")
        if has_phase:
            line += (f" {mean_of('t_lock'):>9.0f} {mean_of('tooth_period'):>8.0f} "
                     f"{mean_of('tooth_size'):>8.2f}")
        if has_wall:
            n_up = 0
            n_dn = 0
            for r in sub:
                if r.get("wall_side") == 1:
                    n_up += 1
                elif r.get("wall_side") == -1:
                    n_dn += 1
            line += (f" {f'{n_up}+/{n_dn}-':>7} {mean_of('ammo_at_lock'):>8.3f} "
                     f"{mean_of('n_reentries'):>7.1f}")
        print(line)


GROUP_BY = None    # e.g. "c", "q", "band_seed", "step6_order", "size_cv":
                   # sweep mode — prices colored by this key, stats x-axis =
                   # its values instead of arms. Set via --group-by <key>.


def _group_values(rows: list[dict], key: str) -> list:
    """The sorted distinct values of the swept key (None first)."""
    vals = sorted({r.get(key) for r in rows}, key=_none_first)
    return vals


def _none_first(v):
    """Sort key: None before everything (named function — breakpointable)."""
    if v is None:
        return (0, 0)
    return (1, v)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--group-by" in args:
        i = args.index("--group-by")
        GROUP_BY = args[i + 1]
        del args[i:i + 2]
    if args:
        _cli_in = args[0]          # plot any results file: python plot_scan.py my.jsonl
        globals()["_default_in"] = lambda _p=_cli_in: _p
        args = args[1:]
    if args:
        raise SystemExit(f"unrecognised arguments: {args} — usage: "
                         f"python plot_scan.py [results.jsonl] "
                         f"[--group-by KEY]")
    if GROUP_BY:
        print(f"SWEEP MODE: grouping by '{GROUP_BY}' "
              f"(colors/x-axis = its values, not seeds/arms)")
    rows = load_rows()
    if not rows:
        import glob
        have = sorted(os.path.basename(f)
                      for f in glob.glob(os.path.join(OUT, "scan_results*.jsonl"))
                      if os.path.getsize(f) > 0)
        raise SystemExit(
            f"no rows in {_default_in()} — is SCAN (currently '{SCAN}') set to "
            f"the family you ran? Non-empty results in eval/runs: {have or 'none'}")
    n, T = rows[0]["n"], rows[0]["T"]
    fam = "" if SCAN == "blocks" else f"_{SCAN}"
    tag = f"mvp_scan{fam}_n{n}_T{T}"
    if GROUP_BY:
        tag += f"_by-{GROUP_BY}"   # sweep figures never collide with plain ones
    print(f"{len(rows)} runs loaded, groups present: {_groups_in(rows)}")
    print_table(rows)
    plot_prices(rows, os.path.join(OUT, f"scan_prices_{tag}.png"))
    plot_stats(rows, os.path.join(OUT, f"scan_stats_{tag}.png"))
    plot_wall(rows, os.path.join(OUT, f"scan_wall_{tag}.png"))
    plot_wall(rows, os.path.join(OUT, f"scan_wall_value_{tag}.png"),
              value_weighted=True)
