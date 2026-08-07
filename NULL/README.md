# The Alpha Engine — Null Model

A minimal agent-based model of a market. Closed two-currency economy
(BTC/EUR), a central limit order book, and agents with zero intelligence.
No external price feed, no external money, no strategies. The price is
whatever the last trade printed.

The point: booms, crashes, fat tails, and calm/wild spells emerge from the
**plumbing** of markets — the position lifecycle and the order book — before
any opinion, information, or intelligence enters. This model is the null
against which all of that must later be measured.

## The model

- **2n agents**, side fixed for life: *n* longs start EUR-heavy and buy BTC;
  *n* shorts start BTC-heavy and sell BTC. Initial capital is drawn from a
  Pareto distribution (a few whales, many minnows) and rescaled so each side
  holds exactly K/2.
- Each agent has an internal **clock**: pressure rises by `c` per tick and
  fires at a capital-scaled threshold `d` (whales fire proportionally
  rarely). Every agent, for its whole life, can only ever do four things:

  1. **Join** — the clock fires while flat: open one position, sized at
     wealth/q in geometric-mean units (the same formula for both tribes).
     Entries are marketable-to-touch limits; the unfilled remainder rests.
  2. **Leave happy** — every open position immediately rests a take-profit
     limit one band (`tp`, log-symmetric) from its entry. These resting
     winners-in-waiting *are* the book's liquidity.
  3. **Leave sad** — the price through the stop line one band (`sl`) the
     other way fires a market order: out now, at whatever the book gives.
  4. **Time out** — the same clock fires while holding: exit at market
     (impatience). This is what keeps a pure CLOB alive at all.

- **Exits promise the agent's own coin**: a long delivers the BTC it bought;
  a short re-spends the EUR it received. Self-funded on both sides, losses
  bounded, side-symmetric.
- **Conservation is exact**: no EUR or BTC is created or destroyed, and PnL
  is zero-sum to the last bit (asserted every tick).

All randomness is rolled up front — the capital draw, a phase jitter on the
clocks, and per-tick queue-order shuffles on dedicated streams. After that,
clockwork.

## Files

| file                   | what it is |
|------------------------|------------|
| `simulation_mvp.py`    | the entire engine, one file: config, orders, book, agents, tick loop |
| `dashboard_mvp.py`     | plots: price + PnL distribution; order-book depth, volume, deepest state |
| `scaling_law_mvp.py`   | intrinsic-time scaling laws (DC count / overshoot) from the price feed |
| `stylized_facts_mvp.py`| the Cont (2001) stylized-facts scorecard from the price feed |
| `dc_analysis.py`       | the directional-change / overshoot algorithms (feed-only, engine-blind) |
| `verify/verify_mvp.py` | proves bit-equality against the reference engine, tick by tick |

The emergent price has exactly **one write site** in the whole codebase —
the boxed block inside `Book.submit()`. Everything else only reads it.

## Run

```bash
python NULL/simulation_mvp.py
```

Edit the block at the bottom of the file (n, T, seed, and the three model
switches). A default run (n=150, T=100k) takes ~1.5 minutes and writes:

- `dashboard_<tag>.png` — the emergent price and the final per-agent PnL
  distribution (with the zero-sum Σ in the title)
- `orderbook_<tag>.png` — resting orders and volume per side over time, and
  the run's deepest book state as a cumulative depth chart
- `price_btc_eur_<tag>.csv` — `tick, BTC/EUR` (full precision)
- `trades_<tag>.csv` — every print: `tick, trade_id, agent_id, buy_sell,
  size, price` (agent ids are `L0..L{n-1}` / `S0..S{n-1}`; attribution is
  the taker)

- `scaling_laws_<tag>.png` — the intrinsic-time laws (DC count / mean
  overshoot, log-log, with fits and the BM references)
- `stylized_facts_<tag>.png` — the Cont scorecard (ACF of r and |r|,
  kurtosis under aggregation), with the printed report in the console

`<tag>` is the minimal config designator, e.g. `mvp_n150_s9_x0-1.0`
(n, seed, x_0; a non-default block switch appends itself, so variant runs
never overwrite the null's files). All four figures come from one run;
`scaling_law_mvp.py` and `stylized_facts_mvp.py` can also run standalone,
reusing the tagged price CSV when present (instant, no simulation).

## The three switches

Each mechanism the model's behaviour could be blamed on is interchangeable.
The defaults are the null; each alternative draws on its own RNG stream, so
flipping one switch changes nothing else.

| switch         | default (the null)          | alternative |
|----------------|-----------------------------|-------------|
| `capital_dist` | `"pareto"` — heavy-tailed   | `"normal"` — homogeneous population |
| `band_dist`    | `"fixed"` — one tp/sl for all | `"normal"` — per-agent bands |
| `closing`      | `"clock"` — pressure timer  | `"normal"` — drawn holding times |
| `size_dist`    | `"fixed"` — everyone deploys wealth/q | `"normal"` — per-agent fraction q_i |

## Reproducibility

Runs are bit-identical across machines and across time. The capital draw
goes through exact PCG64 uniforms and a `decimal` inverse-CDF (libm is not
correctly rounded; one ulp rewrites a chaotic run), totals use `math.fsum`,
and every stochastic choice sits on a named, seed-derived stream.

`python verify_mvp.py` runs this engine and the reference engine on the
default configuration (n=150 and n=2, T=100k, seed 9) and asserts that
nine recorded series — price, trade activity, book depth, survivors, side
PnL — are equal **to the bit** on every one of the 100,000 ticks.

The step-6 close-refire loop runs on its own dedicated per-tick shuffle
(`step6_order="shuffled"`, the default) — the legacy engine's array-order
seat asymmetry, whose documented fix had been committed into dead code, is
repaired here. `step6_order="array"` reproduces the legacy frozen commit
bit-for-bit; that is the arm `verify_mvp.py` proves against the reference
engine, so the lineage stays checkable while the default null is clean.

## What the null shows

With zero intelligence: price evolution is random and path-dependent, the
favourite step size is exactly one take-profit band, large moves are far
more frequent than a Gaussian allows (fat tails), and activity clusters in
time. None of it is coded in. If a future mechanism — heterogeneous agents,
a market maker, external coupling — claims to *explain* one of these
features, it must first beat this model, which produces them with nothing.
