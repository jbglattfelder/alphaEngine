"""
exp_oscillator_phase.py — phase-conditioned DC decomposition of the impatience
oscillator (HANDOFF_clob §6/§7).

PREDICTION (registered in HANDOFF_clob §6 before any run): the super-linear
overshoot of the pooled n=500 figure (level ⟨ω⟩/δ = 6.58, slope 1.69) is
concentrated in the FLUSH phase; build-phase overshoots are near-BM.

Consumes the export_price.py CSV (needs p_int, open_long, open_short — run
export_price with ENTRY_MODE="rest", HOLD_FIRES_CLOSE=True, T=100_000).
Phase = sign of the smoothed open-count trend (build: rising; flush: falling).

NOTE (measured 2026-07-17): a T=24k window is useless here — it captures the
initial monotone collapse, and monotone sawtooths produce almost no DC events
(15 where the full-horizon rate implies ~110). Use the full multi-cycle feed;
report event counts next to every ratio.

Usage: python3 exp_oscillator_phase.py price_feed.csv
"""
import sys

import numpy as np

from dc_analysis import dc_log_events, load_csv


def main(path: str) -> None:
    import csv
    p = load_csv(path, col="p_int")
    with open(path) as f:
        rows = list(csv.DictReader(f))
    op = np.array([float(r["open_long"]) + float(r["open_short"]) for r in rows])
    y = np.log(p)
    r = np.diff(y)
    sd = r[r != 0].std()

    k = 401
    ops = np.convolve(op, np.ones(k) / k, mode="same")
    phase = np.where(np.gradient(ops) > 0, "build", "flush")
    print(f"{len(p)} ticks | sd={sd:.4g} | build {100*(phase=='build').mean():.0f}% "
          f"/ flush {100*(phase=='flush').mean():.0f}%")
    print(f"{'d/sd':>5} {'phase':>6} {'events':>7} {'<w>/d':>7} {'med':>6}")
    for kmult in (8, 12, 16, 24, 32):
        delta = kmult * sd
        ev = dc_log_events(y, delta)[1:]
        for ph in ("build", "flush"):
            sel = [e for e in ev if phase[min(e.idx, len(phase) - 1)] == ph]
            if len(sel) < 10:
                print(f"{kmult:>5} {ph:>6} {len(sel):>7}   (too few)")
                continue
            w = np.array([e.overshoot for e in sel]) / delta
            print(f"{kmult:>5} {ph:>6} {len(sel):>7} {w.mean():>7.2f} {np.median(w):>6.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "price_feed.csv")
