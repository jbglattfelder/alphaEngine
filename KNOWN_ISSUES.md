# Known issues of this frozen version

This repository is frozen at the version that produced the figures in
*The Liquidity Engine: Engineering Markets* (2026). An audit of code,
docs and paper in October 2026 found the items below. **None of them is
fixed here**, so that the engine stays byte-identical to the one behind
the paper; fixes live in the development repository. Items are grouped by
what they affect.

The engine's mechanics are sound and match the paper: the n=2
walkthrough of Sec. 3.4 (ticks 54, 144, 145, 146, 369) is reproduced line
for line by `eval/bench/log_mvp_n2_…txt`, and all NNNN reference runs are
reproducible from this code.

## 1. Which arm is "the null"

The paper's null is **NNNN** (normal capital, normal bands, normal
closing, normal size). In this version the `Config` class defaults are
**PFCF** (the historical starting point), the validator's n=150
fingerprint is pinned on PFCF and its n=2 fingerprint on NFNN, and the
docs used to say NFNN. Every script sets the four knobs explicitly, so the
defaults matter only for a hand-built `Config()`. The NNNN arm itself —
the paper's arm and the "master dial" `band_dist="normal"` — is not
covered by a fingerprint in this version.

## 2. Validator

- **Test 13 (K×8 scale-freedom) cannot fail.** It prints WARN when the
  price paths differ but counts as a pass, so the summary line says
  "13/13 passed" either way. On the PFCF default it does differ.
  *Cause:* the Pareto capital draw converts `x_min` through `str()`
  (`Decimal(str(x_min))`), and `str(8·x)` is not 8·`str(x)`, so a K×8 run
  draws different last bits. The normal arm (NNNN) is unaffected: the
  paper's K-invariance claim holds for NNNN and fails only for the Pareto
  arms, by rounding.
- Conservation is checked at 1e-6 relative per coin, zero-sum at 1e-4 EUR
  absolute — not the paper's Eq. (10) (residuals in X, ≤ 1e-9 K). The
  engine's in-run assert is a 1e-3 relative tripwire.
- Test 12 recomputes one multiplier of one agent on the same machine;
  test 11 checks one row per CSV; ledger closure runs at n=2 only.
- The validator writes nine tape files into the working directory on
  each run.

## 3. Helpers behind numbers in the docs

- `helper/audit_exploit.py` (source of "wins 87%") fills **at the signal
  print itself**. The signal exists only once that print has happened and
  a tick is atomic, so the number is an upper bound, not a tradeable
  result. It also books the bid–ask bounce of both legs as edge and
  counts ties as losses. Measured on the n=7,500 NNNN seed-9 tape with
  fills one *tick* after the signal, the edge is +0.8 bp (hit 49%); one
  *print* after the signal, +9.5 bp (hit 29%, right-skewed).
- `helper/audit_impact.py`: the injected external agent is appended to
  the agent list, so the engine rests a take-profit at its entry price,
  arms a stop there and times it out next tick — **every injection is
  unwound one tick later**, and the t+0 column is always zero. There is
  no no-injection control. Its results should not be used.
- `helper/agent_pnl_mvp.py` marks each ledger at that agent's own last
  fill price, so Σ PnL across agents is not zero (+41.6 EUR on the NNNN
  n=2 T=100k run against an assert of < 1e-4). PnL is in EUR, not X.
- `helper/run_experiments_mvp.py` crashes on import (`sys.path` is set
  after the import) and would load the root engine rather than the
  archived predecessor it needs — which was removed from the tree at the
  freeze (git history before `1c6865f`, `dev/null_model/`).
- Nothing in this version computes the median spread quoted in the paper
  (0.02–0.04% at n=7,500); the docs' older "~0.05%" is from n=5,000.
- `helper/stylized_facts_mvp.py` and `helper/plots_from_tape.py` use two
  different ACF estimators; the "per-tick" kurtosis in `plots_from_tape`
  is computed on fixed blocks of ⌈prints/ticks⌉ prints, not on ticks.
- `eval/validate/agent_pnl_mvp.py` and `eval/validate/verify_mvp.py` are
  stale copies from the removed predecessor and do not run on the root
  engine.

## 4. Engine details the paper describes differently

These are conventions of the engine, not bugs; the paper should describe
them as they are.

- **Timer closes execute after new entries.** Stop closes fire in step 4,
  before the tick's entries; timer closes are committed in step 3b but
  fire in step 6, after them. The paper's "Ordering" paragraph says both
  precede entries.
- **A negative-average-entry leftover is not closed.** It places no
  take-profit and arms no stop, and sits until its timer sweeps it. The
  paper says "treated as closed".
- **Stops are checked once per tick against the last price.** A move
  through a stop level that reverses within the same tick does not
  trigger it. In production the check must be per print.
- **The price moves when an order is filled, not only on market orders.**
  Entries are limit orders priced at the best opposite quote, and a
  take-profit placed in step 2 can cross and print.
- **Pareto capital: `x_min` is not the floor.** The draw is rescaled to
  sum to K/2, so the realised floor is ≈ 1.7·x_min and seed-dependent.
- **Dust thresholds are not mirror images.** The short's "close done"
  threshold is `1e-9·x_min` EUR (depends on n); the long's is
  `1e-9/x_0·K/K_ref` BTC; the entry dust and the long fire-close floor are
  not K-scaled. No effect at current sizes.
- **Dust prints.** A sub-cent residual budget can print a trade of
  0.000000 BTC; such prints count in the trade totals and enter the event
  tape (about 1% of prints at n=2).
- `cfg_tag` omits T, tp, sl, c, q and K: runs that differ only in those
  overwrite each other's outputs.
- Seeding: the jitter stream `seed+90210` coincides with the capital
  stream of seed `seed+90210`; steps 4 and 5 share one shuffle stream;
  the "normal" capital arm censors at the floor (an atom) rather than
  truncating.

## 5. Scan and figures

- The scan fits DC laws without a truncation guard; the figures use
  `trunc_frac=0.125`. Scan `E_N` and ⟨ω⟩/δ are therefore not comparable
  with the figures.
- The scan has 6 seeds (96 runs); `eval/EVALUATION.md` says 8 and 128.
- The scan driver writes tapes and book snapshots for every run.
- The family table prints `|mean(drift)|`, not `mean(|drift|)`, so signed
  drifts cancel across seeds.
- The JSONL results behind the scan figures are not committed
  (`*.jsonl` is ignored).

## 6. Repo hygiene

- `eval/validate/` holds unreferenced `.xls` files.
- `.gitignore`'s `.*/` also hides `.github/`.
- Inconsistent names in `eval/runs/` (`-T1m` vs `_T1m`, `venu_sim`).
