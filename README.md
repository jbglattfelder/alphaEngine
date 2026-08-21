# Alpha Engine — the null model

## 1. What this is

A **closed two-currency market** (BTC/EUR) populated by agents with **zero
intelligence**. `n` "longs" open positions by **buying** BTC; `n` "shorts"
open by **selling** it; side is fixed for life. At the default `f=0.5`
every agent starts with the identical wallet (half EUR, half BTC) — the
only asymmetry between the sides is the direction they trade. There is no
external price feed and no external money: **the price is the last trade**, liquidity is other
agents' resting orders, money is conserved to the bit, and PnL is exactly
zero-sum. Every agent only ever does four things:

1. **JOIN** — an internal clock fires; the agent opens one position.
2. **LEAVE HAPPY** — a take-profit limit rests in the book ("wake me at +1%").
3. **LEAVE SAD** — a stop-loss fires a market order ("get me out now").
4. **TIME OUT** — the clock fires while holding: exit at market.

**There is no market maker, so the bid–ask spread is emergent:** it is
simply the gap between the nearest resting buy and sell orders — and
nobody guarantees there are any. In a large calm market the book is
almost always two-sided and tight: at n=5,000 (NFNN defaults), ~98% of
ticks have both sides quoted, with a median spread of ~0.05% of the
price and a wide distribution (often near zero; ~0.6% at the 90th
percentile; the ceiling is the ±1% exit-band scale, since resting
take-profits are what populate the book). In small or one-sided markets
the spread can be band-wide, or a side can be empty entirely — a market
order that finds nobody home simply retries next tick. The engine
guarantees the book is never *crossed*, not that it is always quoted.

**The intent.** This is a *null model* in the strict sense: the baseline
against which any claim about markets must be measured. Before attributing a
market phenomenon — fat tails, volatility clustering, crashes, trends,
persistent winners — to information, strategy, or psychology, one must know
how much of it a market produces with **none of those things**: identical
mechanical agents, heterogeneous only in wealth, timing, and luck. Whatever
this model already exhibits needs no explanation from intelligence. Whatever
it lacks marks the genuine explanatory work left for cognition.

**The philosophical context.** The model is an exercise in emergence:
macro-structure from micro-rules that contain no trace of it. Nothing in the
code knows what a bubble, a squeeze, a liquidity drought, or a trend is — yet
all of them occur, driven entirely by the interaction of order-book mechanics
with the initial dice (who got the money, who wakes first). The price that
emerges is not an estimate of any value; it is a pure social fact, the memory
of the last agreement. In that sense the null model is a laboratory for the
oldest question of complexity science, applied to finance: how much of the
world's apparent purposefulness is mechanism wearing a costume?

Runs are **deterministic and bit-portable**: the same `Config` produces the
same run, to the last bit, on any machine (all randomness is seeded; the one
platform-dependent function, `exp`, is precomputed with correctly-rounded
decimal arithmetic at setup).

## 2. The four knobs

Each knob selects how one ingredient is distributed across agents. Each draws
on its **own RNG stream**, so changing one cannot perturb the others — an A/B
comparison stays an A/B comparison.

| knob | options | meaning |
|---|---|---|
| `capital_dist` | `"pareto"` \| `"normal"` | who gets how much money (heavy-tailed whales vs a homogeneous crowd) |
| `band_dist` | `"fixed"` \| `"normal"` | the TP/SL exit bands: identical ±1% for all, or drawn per agent |
| `closing` | `"clock"` \| `"normal"` | the timer exit: deterministic pressure threshold, or a drawn holding time |
| `size_dist` | `"fixed"` \| `"normal"` | order fraction: everyone deploys wealth/q, or a per-agent q_i |

A configuration is named by its four letters in this order — e.g. **PFCF**
(pareto, fixed, clock, fixed) or **NFNN** (normal, fixed, normal, normal).
Everything else (n, T, seed, bands, clock rate, floors, outputs) lives in
`Config` at the top of `simulation_mvp.py`, one comment per field.

## 3. Running it (the default run)

```bash
python simulation_mvp.py
```

That's all. The block at the bottom of `simulation_mvp.py` runs **n=2 per
side, T=150,000 ticks, seed 9, NFNN** — the smallest market that has all the
mechanics, small enough to read every single decision in the log. It prints
the resolved config and a run summary, pops six figures (set `SHOW = False`
to suppress), and writes every output listed below next to the code.

To run something else, edit the marked block at the bottom of the file:

```python
N = 150                    # agents per side
T = 100_000                # ticks
CAPITAL_DIST = "pareto"    # ... the four knobs; pareto/fixed/clock/fixed = PFCF
```

To sweep all 16 knob combinations: `python scan_simulation_mvp.py`.
To check the engine (12 invariants, ~30 s): `python validate_simulation_mvp.py`.

## 4. The outputs

Every artifact carries the run's tag, e.g.
`mvp_n2_s9_x0-100.0_cap-normal_close-normal_size-normal` (n, seed, x₀, and
every non-default knob — default-knob runs stay short).

| file | content |
|---|---|
| `dashboard_<tag>.png` | the run at a glance: price, drift, per-side wealth and PnL, population |
| `orderbook_<tag>.png` | book depth and volume per side over time + the deepest book snapshot |
| `stylized_facts_<tag>.png` | return ACF, volatility clustering, kurtosis vs aggregation, on the tick tape |
| `stylized_facts_event_<tag>.png` | the same measurements on the **event tape** (one price per print — the model's intrinsic clock) |
| `scaling_laws_<tag>.png` | directional-change scaling laws (N(δ), overshoot ω(δ)) on the tick tape |
| `scaling_laws_event_<tag>.png` | the same laws in event time |
| `price_btc_eur_<tag>.csv` | the tick tape: `tick, price` |
| `trades_<tag>.csv` | every print, **both parties**: `tick, trade_id, agent_id (taker), buy_sell, size, price, buy_agent, sell_agent, maker_id`. Per-agent analysis must select on `buy_agent`/`sell_agent` — the taker column alone sees only half an agent's fills |
| `log_<tag>.txt` | the narrative log: one line per decision (init, order placed, trade with counterparty, stop hit, timer due, settle). Repetitive retry loops compress to one summary line. `print_log=False` turns it off — do so for large runs |

Optional (`save_tapes=True`): `tape_<tag>.npy` (tick prices) and
`tape_<tag>_events.npz` (every print's price and tick) — the raw arrays, so
any analysis can be re-sliced later without re-running the simulation.

## 5. The code

**Root — the two scripts you run, plus the check:**

| file | role |
|---|---|
| `simulation_mvp.py` | **the model.** Config, order book, agents, the six-step tick loop, all writers. One file, every method commented |
| `scan_simulation_mvp.py` | the sweep driver: all 16 knob combinations × seeds, one JSONL row per run (drift, lock, teeth, walls, stylized facts, scaling) |
| `validate_simulation_mvp.py` | 12 numbered engine tests: determinism, the two frozen fingerprints, conservation, zero-sum, no self-trades, no degenerate quotes, book never crossed, solvency, ledger closure, CSV integrity, the decimal invariant. Exit 0 = healthy |

**`helper/` — imported, not run directly:**

| file | role |
|---|---|
| `dashboard_mvp.py` | the dashboard and order-book figures |
| `stylized_facts_mvp.py` | ACF / clustering / kurtosis measurements and figure |
| `scaling_law_mvp.py` | directional-change scaling analysis and figure |
| `dc_analysis.py` | the DC event detector the scaling module builds on |
| `plot_scan.py` | reads the scan JSONL; verdict tables and comparison figures |
| `run_experiments_mvp.py` | replays the level-0 experiment ledger (exp1–exp6). Probes historical switches, so it runs on the **archived** engine in `dev/null_model/` |
| `agent_pnl_mvp.py` | per-agent PnL ledgers from full two-sided fills (balance-sheet b/q accounting); validates to the engine's wallets and to Σp = 0 |

## 6. Directory structure

```
/                     the null model: two runnable scripts + the validator
├── helper/           auxiliary modules (imported by the root scripts)
├── eval/             simulation output
│   ├── bench/        benchmark reference runs (n=2 and n=150)
│   ├── runs/         exploration output
│   └── validate/     under construction: spreadsheet-level analysis of
│                     individual agent behavior
└── dev/              legacy and research ARCHIVE — read, don't run
    ├── explore/      initial R&D (the original engine, experiments, figures)
    └── null_model/   the frozen predecessor of /, with its full history
```

## 7. A note on `dev/`

The archive is the project's memory, and it is deliberately preserved: how
this model was found, debugged, validated bit-for-bit against its legacy
implementation, and experimentally mapped (six experiments, the bug hunts,
the retractions) is documented in **`dev/explore/FINDINGS-master.md`** and
**`dev/explore/HANDOFF-master.md`**, with the frozen predecessor's own record
in **`dev/null_model/EVALUATION.md`**. The archive's longest story is the
**symmetry chase**: run after run pinned in one direction, and the question
was whether the engine secretly favors a side. The hunt went through a dual
line-by-line audit of every side-conditional, a mirrored-capital test (both
tribes handed the identical wealth multiset), and the exit-promise ablation
(each side delivering its own coin — the mirror-equivariant rule — against
the flow-symmetric alternative). Verdict: the code is an exact mirror; the
**dice** decide the direction — the structure of the capital draw picks each
run's winner before the first trade. Nothing in `dev/` is needed to use the
model — but if you want to know *why* any line of the root engine is the way
it is, the answer is in there.
