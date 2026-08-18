"""Run a slice of the 40 (arm, seed) jobs from exp_side_asymmetry; append to jsonl."""
import json
import sys

from exp_side_asymmetry import run_one, SEEDS, OUT

JOBS = [(s, False) for s in SEEDS] + [(s, True) for s in SEEDS]

if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    with open(OUT, "a") as f:
        for seed, log_arm in JOBS[a:b]:
            r = run_one(seed, log_arm)
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(f"seed={seed:2d} log={log_arm} pnl_long={r['pnl_long']:+9.1f} "
                  f"lnp={r['log_price_move']:+6.2f} pred_P4={r['pred_edge_P4']:7.1f}")
