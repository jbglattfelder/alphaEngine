"""it_calibrate.py — ticks per intrinsic-time event on a tick tape.

Intrinsic time ticks once per delta of price movement: at every
directional change and at every further delta of overshoot. This counts
both on a tape and prints the mean spacing, which is the number to put in
Config.it_ticks_per_event so that an intrinsic-clocked agent fires as often
as a tick-clocked one in the same market.

    python helper/it_calibrate.py tape_mvp_n500_s9_..._size-normal.npy [delta=0.01]
"""
import sys
import numpy as np


def events_per_tape(p, delta: float = 0.01):
    up, dn = float(np.exp(delta)), float(np.exp(-delta))
    ext = ref = float(p[0]); mode = 1; n_dc = n_os = 0
    for x in p[1:]:
        x = float(x)
        if mode > 0:
            if x > ext:
                ext = x
                if x >= ref * up:
                    ref = x; n_os += 1
            elif x <= ext * dn:
                mode = -1; ext = ref = x; n_dc += 1
        else:
            if x < ext:
                ext = x
                if x <= ref * dn:
                    ref = x; n_os += 1
            elif x >= ext * up:
                mode = 1; ext = ref = x; n_dc += 1
    return n_dc, n_os


if __name__ == "__main__":
    p = np.load(sys.argv[1])
    delta = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    n_dc, n_os = events_per_tape(p, delta)
    n = n_dc + n_os
    print(f"{len(p):,} ticks, delta={delta:g}: {n_dc:,} directional changes + "
          f"{n_os:,} overshoot ticks = {n:,} events -> {len(p)/max(n,1):.1f} ticks per event")
