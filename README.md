# The Alpha Engine — POC

A closed two-currency market (EUR / BTC) simulated from the bottom up. Two fixed
populations of agents trade with each other through a **central limit order
book**. There is no external price feed and no external money: the price is
whatever the trades produce, and money is conserved exactly.

The goal is a **null model** — a market in which every behaviour is either
derived from its rules or measured and bounded — so that when strategies,
heterogeneity, or external traders are added later, anything new is
*attributable* to them rather than to the plumbing.

The method: state the prediction, run the thing that can kill it, log the corpse.
Retractions are filed at equal weight with results (see `HANDOFF.md` §4).

---

## Start here

| If you want | Read |
| --- | --- |
| The measured state, and what was retracted | `HANDOFF.md` |
| Why we're doing this and what's next | `DIRECTION.md` |
| What the price process **is** (liquidity, scaling laws, the runaway) | `HANDOFF-v4.md` |
| The short-stranding asymmetry (open thread) | `HANDOFF_stranding-v2.md`, `FINDINGS_stranding.md` |
| Rules for changing code | `CLAUDE.md` |
| Bit-check targets (reproducibility) | `REFERENCE.md` |
| The original v1 spec | `alpha_engine_poc_v1_spec.pdf` |

---

## What the model is

- **Agents.** `n` "longs" and `n` "shorts"; side is fixed for life. Initial
  capital is drawn from a Pareto law and rescaled so the total is exact.
- **Clock.** Pressure accumulates each tick while an agent is flat; when it
  crosses a capital-scaled threshold the agent opens one position. It cannot open
  another while holding one.
- **Exits.** Every position has a take-profit and a stop-loss. The **TP rests in
  the book as a passive limit**; the **SL fires as a market order** when touched.
- **The venue.** A CLOB (`book.py`). It matches; it never takes a position.

**There are only three mechanisms: open, take profit, stop out.** Sorted by role:
aggressive flow is the entry imbalance plus SL covers; passive depth is TP limits
**and nothing else**. So *liquidity is other agents' unrealized profit* — there
are no market makers, and every resting order exists only because someone holds
an open position. That single fact drives most of `HANDOFF-v4.md`.

One tick: accumulate pressure → rest TPs / arm SLs → check SL triggers → fire
entries → cross the flow (balanced buys and sells match at the last price with no
impact; only the **net imbalance** walks the book and moves the price) → settle
closed positions → bankruptcy check → record.

Money conservation and PnL zero-sum are asserted every tick. Runs are
bit-identical across machines (the capital draw uses `decimal` + `math.fsum`
because the model is chaotic — one bit rewrites a run).

---

## Modules

| Module | Owns |
| --- | --- |
| `config.py` | All parameters + switches (single source of truth) |
| `agents.py` | Agent + Population: capital draw, pressure, firing, sizing |
| `book.py` | **The CLOB**: resting limits, price-time-priority matching, the emergent price |
| `position.py` | Balance-sheet PnL (Glattfelder & Houweling 2024, arXiv:2411.14068) |
| `simulation.py` | The tick loop; wires the modules |
| `analysis.py` | Recorder, Analyser: dashboard + automated sanity checks |
| `main.py` | Entry point |
| `market.py` | **RETIRED.** The Dutch-auction era. Nothing imports it; it warns on import. Kept only as a record — read `book.py` for the live mechanism. |

Dependency direction is `config <- agents <- book <- simulation`. The book
returns `Fill`s; the simulation applies them to agents. Keep it that way.

---

## Setup

```bash
python3.13 -m venv .venv          # runs unchanged on 3.12
source .venv/bin/activate
pip install -r requirements.txt
```

In VS Code: Cmd+Shift+P → "Python: Select Interpreter" → `.venv/bin/python`.
Scripts import their siblings, so **run them from the repo root**.

---

## Run

Each of these has an **edit block at the top** — change it, press Run.

```bash
python run_single.py      # one run -> dashboard.png, pnl_distribution.png, capital_distribution.png
python scaling_law.py     # one run -> price_feed.csv -> intrinsic-time scaling laws -> scaling_laws.png
python export_price.py    # one run -> price_feed.csv (feed only)
python stylized_facts.py  # Cont (2001) scorecard: ACF(r), volatility clustering, kurtosis
python dc_analysis.py price_feed.csv [log|relative]   # analyse any feed; needs only a p_int column
python test_bm.py         # validate the DC/OS instrument against Brownian motion
python main.py            # legacy entry point -- see the close_mode gotcha below
```

Sweeps / experiments: `xrun.py`, `xone.py` (X-accounting f-sweeps),
`exp_side_asymmetry.py`, `exp_microchannel.py`, `exp_evolution.py`,
`exp_chunk.py`. Each states its predictions in its header, before the runs.

`scaling_law.py` has `REUSE_CSV=True`: a second Run re-analyses the existing feed
in seconds instead of re-running the engine (~9 min at n=500/T=100k). **Delete
the CSV when you change the config**, or you will analyse the old feed.

---

## Gotchas — read before you trust a number

- **`close_mode` default vs. what you run.** `config.py` defaults to
  `"quantity"` (each tribe re-trades a fixed BTC quantity; produces stranding);
  current work uses `"home"` (each tribe delivers what it holds; the symmetric
  toy model). Anything that doesn't pass it explicitly — `main.py`, a bare
  `Config()` — runs a **different model**. `REFERENCE.md`'s targets were
  generated on the quantity path. Resolve deliberately; don't delete `quantity`
  (it's where squeezes and cover-driven drift live — see `HANDOFF-v4.md` §5).
- **Every knob must be passed.** A block that lies about what ran is the worst
  bug class here; three of them were found and fixed. `Config.summary()` now
  prints the resolved exits / `close_mode` / `sl_mode` / sizing — **check them
  against your block on every run.**
- **Read transfer in X, never in EUR.** The EUR PnL panels are a moving ruler:
  the long-share of geometric-mean wealth stays pinned near 0.5 while EUR PnL
  swings ±17k over the same run. Same rule applies to the analysis code — use
  the **log gauge** (`dc_analysis` default) anywhere the price spans e-folds.
- **Never read EUR volume as activity.** Use BTC volume or clearing counts.
- **Compare distributions, never trajectories.** The model is chaotic; two seeds
  of the *same* config produce completely different runs. Most numbers in the
  docs are 1–3 seeds: direction and order of magnitude only.
- **Symmetry is a large-n claim.** At n=2 the same "symmetric" engine gives a
  5:1 tribe asymmetry.
- **`⟨ω⟩(δ)` is not a power law** — it's a hump. Never quote a fitted `E_os`.
- **matplotlib's first import** builds a font cache (30s–2min on macOS). Let it
  finish; don't Ctrl+C.

Committed `*.json` / `*.jsonl` files are **run artifacts**, not sources of truth.
Parameters live in `config.py`.

---

## What's been established (short version)

- **Trading does not redistribute wealth**: ΔGini = +0.0003 ± 0.0004 over 20
  seeds, surviving 10,000× price moves. Symmetry fixes the shares; conservation
  only fixes the total.
- **The price level carries no information.** No anchor, so it wanders; its drift
  direction is a statement about the numeraire, not the market.
- **The book compresses the capital distribution** — the one result not put in by
  hand. Agents *request* size ∝ capital but get *filled* ∝ capital^γ, with γ
  rising from ~0.1 (thin) to ~1 (liquid) as the firing rate rises. Nobody wrote
  an exponent anywhere. (Caveat: the thin endpoint doesn't survive separating the
  tribes — see `HANDOFF.md` §3d.)
- **The price is a lattice walk whose spacing is the TP band**: `sd(r) = 0.78·tp`
  and `median|log-step| = tp` **exactly**, over an 8× range of `tp`, at every `n`.
- **The exit mix *is* the dynamics.** Continuation probability q = 0.703 with
  stops on, 0.516 with them off (BM ≈ 0.5): SLs are momentum, TPs are reversion.
- **N(δ) ~ δ⁻² holds; ⟨ω⟩ = δ does not.** Counting reversals needs no liquidity
  provider; how far a price *runs* is exactly a question about depth — and our
  depth is endogenous to the run. See `HANDOFF-v4.md` for the pre-registered
  level-1 prediction that follows.

Open threads, in order: the runaway, the overshoot hump, `close_mode`'s effect on
the DC law at n=500, the n=2↔n=150 sign flip, stranding.
