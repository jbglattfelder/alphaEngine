# The Alpha Engine — POC

A closed two-currency market (EUR / BTC) simulated from the bottom up. Two fixed
populations of agents trade with each other through a **central limit order
book**. There is no external price feed and no external money: the price is
whatever the trades produce, and money is conserved exactly.

The goal is a **null model** — a market in which every behaviour is either
derived from its rules or measured and bounded — so that when strategies,
heterogeneity, or external traders are added later, anything new is *attributable*
to them rather than to the plumbing.

Method: state the prediction, run the thing that can kill it, log the corpse.
Retractions are filed at equal weight with results.

---

## Start here

Two documents hold the state; everything else is code.

| If you want | Read |
| --- | --- |
| State, orientation, direction, config, invariants, bit-check targets | **`HANDOFF-master.md`** |
| The detailed experiment records and prediction scoring | **`FINDINGS-master.md`** |
| The original v1 spec | `alpha_engine_poc_v1_spec.pdf` |

These absorb the former `CLAUDE.md`, `DIRECTION.md`, `REFERENCE.md`, all
`HANDOFF*` and `FINDINGS_*` files. The two masters are authoritative.

---

## What the model is

- **Agents.** `n` "longs" and `n` "shorts"; side is fixed for life. Initial
  capital is Pareto-drawn and rescaled so the agent total is exact.
- **Clock.** Pressure accrues each tick while flat; at a capital-scaled threshold
  the agent opens one position. With `hold_fires_close=True` (default) the clock
  also runs while holding and a fire-in-position exits at market ("impatience").
- **Exits.** Every position has a take-profit and a stop-loss. The **TP rests in
  the book as a passive limit**; the **SL fires as a market order** when touched.
- **The venue.** A CLOB (`book.py`). It matches; it never takes a position (except
  the optional house maker).

**There are exactly four mechanisms: open, take-profit, stop-loss, timer-exit**
(the pressure clock also closes stale positions; the batch arm runs the first
three). Passive depth is TP limits plus, on the default arm, resting entry
residuals — so *liquidity is other agents' unrealized profit, plus waiting
wishes*, and that fact drives most of the findings.

One tick, **default arm (`entry_mode="rest"`, the pure CLOB shipped by
`run_single`):** accumulate pressure → rest TPs / arm SLs → **SL closes fire as
market orders that walk the book** → firing agents submit **marketable-to-touch
entries that fill what crosses and REST the remainder** (a flat agent re-firing
cancels-and-replaces its resting entry at the live price) → settle → bankruptcy →
record. There is **no balanced-flow auction on this arm** — every entry meets the
book directly.

One tick, **`entry_mode="ioc"` (the batch hybrid — now a one-switch treatment, no
longer any default):**
same up to entries, then balanced buy/sell flow **nets at the last price with no
impact** and only the **net imbalance** walks the book. This is the arm the older
scaling-law / compact-support results were measured on; it is *not* what
`run_single` runs.

Money conservation and PnL zero-sum are asserted every tick. Runs are bit-identical
across machines (`decimal` + `math.fsum` in the capital draw; the model is chaotic).

---

## Modules

| Module | Owns |
| --- | --- |
| `config.py` | All parameters + switches (single source of truth) |
| `agents.py` | Agent + Population + House: capital draw, pressure, firing, sizing |
| `book.py` | **The CLOB**: resting limits, price-time-priority matching, the emergent price |
| `position.py` | Balance-sheet PnL (arXiv:2411.14068) |
| `simulation.py` | The tick loop; wires the modules; records series |
| `analysis.py` | Recorder, Analyser: dashboard + automated sanity checks |
| `dc_analysis.py` | Intrinsic-time DC / overshoot instrument (BM-validated) |
| `main.py` | Entry point |
| `market.py` | **RETIRED** — the Dutch-auction era. Warns on import; read `book.py`. |

Dependency direction: `config <- agents <- book <- simulation`. The book returns
`Fill`s; the simulation applies them. Change parameters in `config.py` only.

---

## Setup

```bash
python3.13 -m venv .venv          # runs unchanged on 3.12
source .venv/bin/activate
pip install -r requirements.txt
```

Run scripts from the repo root (they import their siblings).

---

## Run

Each script has an **edit block at the top** — change it, press Run.

```bash
python run_single.py      # one run -> dashboard.png, pnl_distribution.png, capital_distribution.png
python export_price.py    # one run -> price_feed.csv (the DC-analysis feed)
python scaling_law.py     # feed -> intrinsic-time scaling laws -> scaling_laws.png
python dc_analysis.py price_feed.csv [log|relative]   # analyse any feed (needs a p_int column)
python stylized_facts.py  # Cont (2001) scorecard
python test_bm.py         # validate the DC/OS instrument against Brownian motion
python test_benchmarks.py # bit-exact regression guard (benchmarks.json)
python main.py            # legacy entry point
```

Experiments live in `experiments/` (predictions stated in each header):
`exp_stranding.py`, `exp_tpcluster.py`, `exp_nopen.py`, `exp_durations.py`,
`exp_inventory.py`, `exp_oscillator_phase.py`, `exp_detrend_tail.py`,
`exp_drift_decomp.py`, `exp_side_asymmetry.py`.

---

## The engine switches (which model you are running)

`Config.summary()` prints the resolved set every run — **the header names your
arm.** Full descriptions in `HANDOFF-master.md` §3. In brief:

- **`entry_mode`** — `"rest"` (**default**: pure CLOB, marketable-to-touch entries
  that rest; needs impatience to stay alive) vs `"ioc"` (the batch hybrid: balanced
  flow nets at the last price, only the imbalance walks the book).
- **`hold_fires_close`** — impatience (default True; keeps the pure CLOB live).
- **`close_mode`** — `"home"` (default, symmetric null) vs `"quantity"` (realistic;
  stranding/squeezes — a *treatment*, don't delete it).
- **`exit_promise`** — `"own_coin"` (**default**: each tribe delivers its own coin;
  the symmetric exit the mirror equivariance was verified on) vs `"exact"` /
  `"spend_long"` (treatments that *select* a price direction — see `HANDOFF-master.md`
  §3/§4.9).
- **`book_mode`** — `"coin"` (**default since 2026-07-23**: the verified symmetric
  venue, every order denominated in the coin it delivers) vs `"btc"` (legacy
  base-privileged book, retained as treatment).
- **`mirror`** — the label-relabel involution used to *classify* residual leans, not
  a sizing flag.
- **`sl_mode`** — `"market"` / `"wait"` / `"limit"` (the stranding-fix arms).
- **`stall_T`** — liveness detector for the CLOB absorbing states (detection, not
  prevention).
- **`x_accounting`**, **`log_thresholds`**, **`symmetric_solvency`** (all True):
  the covariant-null defaults.

---

## Gotchas — read before you trust a number

- **The run header must match your intent.** A block that lies about what ran is
  the worst bug class here (four silent-default incidents to date). Check
  `cfg.summary()`.
- **Read wealth/transfer in X, never EUR** — the EUR PnL panel is a moving ruler.
  Use the **log gauge** (`dc_analysis` default) wherever the price spans e-folds.
- **Never read EUR volume as activity** (use BTC volume / clearing counts).
- **Compact-support / tails:** measure `P(|r|>k·sd)`, never kurtosis (it conflates
  peakedness with tail weight).
- **`⟨ω⟩(δ)` is not a power law** — never quote a fitted `E_os`.
- **Compare distributions, never trajectories** — the model is chaotic. Most
  numbers in the docs are 1–3 seeds: direction and order of magnitude only.
- **Symmetry is a large-n claim** (at n=2 the "symmetric" engine gives 5:1).
- **Regenerate stale feeds:** `export_price.py` writes only the columns the run
  recorded; an old `price_feed.csv` can miss `open_long`/`open_short` and break the
  phase analysis. `REUSE_CSV=True` re-analyses an old feed — delete it on a config
  change.
- Committed `*.json` / `*.jsonl` are **run artifacts**, not sources of truth.

---

## What's established (short version)

- **Trading does not redistribute wealth**: ΔGini ≈ 0 over 20 seeds; symmetry fixes
  the shares, conservation only the total.
- **The engine is label-equivariant — the symmetric null was reached.** With the
  coin-symmetric venue (`book_mode="coin"`) and own-coin exit promises, the
  coin-relabel involution (`mirror=True`) inverts the price direction in **5/5 seed
  pairs** (p = 1/32). So P(down) = P(up) *by demonstrated symmetry*, and the earlier
  residual "down-lean" is reclassified as finite-sample noise from a symmetric
  ensemble — not a bias. Verified by an explicit involution the dynamics commute
  with, not by absence of evidence. *Scope:* equivariance is an **ensemble**
  property; per-pair inversion holds in the lock regime (direction committed
  early) — wanderer pairs chaotically decorrelate and can land same-signed
  (measured: seed 9). corr with the mirror twin doubles as a free
  lock-vs-wander classifier.
- **The price level carries no information** — no anchor. On the **batch** arm it
  wanders; on the **CLOB** arm (the default) it is directionally *unstable* — runs
  away up or down, direction a free symmetric mode seeded by noise (a
  symmetry-breaking instability, not a drift). "Prices always fall" was a two-seed
  artifact.
- **Direction is selectable, and selecting it forfeits the null.** `exit_promise`
  arms tilt the price (`"exact"` → 5/5 up, +3.5); any chosen direction is by
  definition a treatment, not the null.
- **The book compresses the capital distribution** (filled ∝ requested^γ, γ from
  ~0.1 thin to ~1 liquid) — the one result not put in by hand.
- **The price's modal step is the TP band** (`sd(r)≈0.78·tp`, median|step|=tp on
  both arms); but the ±2·tp *wall* (compact support) is **batch-only** — the CLOB
  entry mechanism jumps past it (§5.4).
- **The exit mix *is* the dynamics** (q ≈ 0.70 with stops, anti-persistent without:
  SLs are momentum, TPs reversion).
- **N(δ)~δ⁻² is arm-conditional: E_N ≈ −2 on batch n=150, but ≈ −1.6 on the CLOB
  default** (the trending price over-counts large excursions). ⟨ω⟩=δ fails as a MEAN
  (drift-inflated); the median overshoot ≈ BM. Fat tails: **absent on batch**
  (P(|r|>4sd)=0), **present and genuine on the frozen CLOB default** — a power-law
  tail with **Hill α ≈ 2**, shown against a zero-matched BM control and by survival
  under aggregation (raw exceedance ratios are inflated by the 40–72% zero-step
  fraction — use `exp_fat_tails.py`), and present at level 0.5 via a TP-roundness
  hierarchy. Fat tails are reachable at level 0 — two routes.
- **Volatility clustering splits in two**: magnitude clustering is present but
  short-range (dead by lag ~5–20); the long memory (β ≈ 0.27, still 0.31 at lag 500)
  is **activity** clustering — *when* trades happen, not how big they are. Measure
  them separately with `exp_clustering.py`; ACF(|r|) over all steps mixes them.
- **Four independent arguments say the missing piece is an actor, not a parameter**
  — a two-sided quoter (Avellaneda–Stoikov) to provide a spread, absorb the close
  channels, and stabilise the price direction. That is level 1. (Fat tails are *not*
  one of the four — the mechanism gets them free.)

See `HANDOFF-master.md` §0 for the full scorecard and verdict (arm-conditional).
