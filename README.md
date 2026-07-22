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

**There are only three mechanisms: open, take profit, stop out.** The only passive
depth is TP limits — so *liquidity is other agents' unrealized profit*, and that
single fact drives most of the findings. One tick (ioc default): accumulate
pressure → rest TPs / arm SLs → check SL triggers → gather entries → cross the flow
(balanced buys and sells net at the last price with no impact; only the **net
imbalance** walks the book) → settle → bankruptcy → record.

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

Experiments (predictions stated in each header): `exp_stranding.py`,
`exp_tpcluster.py`, `exp_nopen.py`, `exp_durations.py`, `exp_inventory.py`,
`exp_oscillator_phase.py`.

---

## The engine switches (which model you are running)

`Config.summary()` prints the resolved set every run — **the header names your
arm.** Full descriptions in `HANDOFF-master.md` §3. In brief:

- **`close_mode`** — `"home"` (default, symmetric null) vs `"quantity"` (realistic;
  stranding/squeezes — a *treatment*, don't delete it).
- **`entry_mode`** — `"ioc"` (default hybrid: net balanced flow, walk the imbalance)
  vs `"rest"` (pure CLOB; needs impatience to stay alive).
- **`hold_fires_close`** — impatience (default True; keeps the pure CLOB live).
- **`sl_mode`** — `"market"` / `"wait"` / `"limit"` (the stranding-fix arms).
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
- **The price level carries no information** — no anchor, so it wanders.
- **The book compresses the capital distribution** (filled ∝ requested^γ, γ from
  ~0.1 thin to ~1 liquid) — the one result not put in by hand.
- **The price is a lattice walk whose spacing is the TP band** (`sd(r)=0.78·tp`).
- **The exit mix *is* the dynamics** (q = 0.70 with stops, 0.52 without: SLs are
  momentum, TPs reversion).
- **N(δ)~δ⁻² holds; ⟨ω⟩=δ does not; fat tails are unreachable under homogeneous
  bands but appear at "level 0.5" with a TP-roundness hierarchy.**
- **Five independent arguments say the missing piece is an actor, not a parameter**
  — a two-sided quoter (Avellaneda–Stoikov). That is level 1.

See `HANDOFF-master.md` §0 for the full scorecard and verdict.
