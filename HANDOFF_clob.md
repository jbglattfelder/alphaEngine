# HANDOFF: the pure CLOB (entry_mode="rest") — two ways a market dies, and what liveness costs

The v5 thread: delete the auction, run everything through the book. Status:
implemented, guarded, characterized far enough to state a theorem-shaped
result. **All numbers 1–2 seeds — direction and mechanism, not levels.**
Code: `entry_mode` + `hold_fires_close` in config; benchmark cases 9–10.

## 1. The design

Pressure clock fires → entry submitted as a **marketable-to-touch limit**
(cross at the opposite best; residual rests; fallback to last price on an empty
side). One resting entry per agent; a fire while flat **cancels-and-replaces**
it at the live touch (b'), so no quote outlives its owner's period d/c and W
stays vestigial. TPs re-rest when a resting entry deepens the position (growth
only — shrinkage is a partial TP fill keeping its queue priority). The resting
entry is cancelled the moment a close begins, which is the solvency choke
point: a resting BUY may not overdraw EUR a cover is about to spend. SL closes
are market orders in both modes. `entry_mode="ioc"` is the hybrid, bit-identical
(benchmarks 1–8 unchanged through both refreezes).

## 2. Found on the way: entry-at-last is a fixed point

The first implementation quoted entries AT the last price. Result: a busy
market whose price never moved once — every fill executes at last, so last
never updates. The entry-price convention is not a small tilt here; the
maximally passive choice kills price formation outright. Marketable-to-touch
is the minimal parameter-free aggression that keeps the price alive.

## 3. Theorem-shaped result: two absorbing classes

**Class 1 — all-holding (taker starvation).** Every order in this model exists
because of its owner's position state; when every agent holds, all remaining
orders are passive exits, and the only takers the model can mint (new entries,
triggered SLs) both require a resource the state has exhausted (a flat agent /
a price move). Measured: n=2 froze at tick ~4; **n=500 froze by tick ~1,000**
(all 1,000 agents open, price parked inside every band, 99k green-checked dead
ticks). Not a fluctuation — an attractor: rest-mode's guaranteed fills drain
the flat pool at ~c·n, self-accelerating. The hybrid never died here for an
unglamorous reason: **IOC failure was the taker supply** — discarded entries
returned their agents to flat. ioc lives by wasting takers; rest deadlocks by
conserving them.

**Class 2 — same-side desire (counterparty starvation).** Rigid tribes can
align: measured at n=2 with impatience ON, the market died at ~19k in the
state {2 shorts holding (exit = BUY), 2 longs flat (entry = BUY)} — four
buyers, zero sellers, all resting interest one side, closes firing into an
empty book forever. No within-population rule can fix this class: aggression
needs an opposite resting order, and here every desire points the same way.
Combinatorially negligible at n=150; guaranteed reachable at small n.

## 4. The impatience arm (hold_fires_close) — scored

One clock, two roles: pressure also accrues while holding, and a fire while
in-position is an exit at market. No new parameter; the exit timescale is the
agent's own period d/c; scale-covariant. This distributes *unconditional-in-
market-state timing* into every agent.

Pre-registered: deadlock disappears at n=2 AND n=500 (P1); liquidity stats
improve vs plain rest (P2). Scored:

| arm (n=150, T=30k) | last trade | trades/tick | two-sided | worst drought | round trips |
|---|---|---|---|---|---|
| rest, plain | tick 347 | 0.007 | 0.8% | 29,652 | 681 |
| rest + impatience | tick 29,986 | 0.246 | **86.6%** | **189** | 44,421 |
| ioc hybrid (ref) | live | 0.54 | 13.9% | 843 | 18,268 |

**P2 confirmed emphatically** — the impatience CLOB is the best liquidity
venue of any arm measured in this project, beating the hybrid 86.6% vs 13.9%
two-sided. **P1 falsified at n=2** by Class 2 above (Class 1 it does kill, at
every n tested: a stale position is always a mintable taker). All sanity
checks pass everywhere; solvency exact.

## 5. The liveness statement

Impatience buys unconditional **timing**; it cannot buy unconditional
**side**. A guarantee of tradability therefore needs a participant who is
always on **both** sides regardless of its own state — the house maker
(HANDOFF-v4 §6.7), now demanded by a fifth independent argument and, for
Class 2, provably the unique class of fix. The refined claim for DIRECTION:
*someone must act unconditionally on market state; impatience distributes the
timing half into the population, and only the maker supplies the side half.*
Level 1's comparison gains a third arm — null / impatience-CLOB / maker-CLOB —
and "what unconditional liquidity is worth" splits into two separately priced
components.

## 6. Open

- Everything at 1–2 seeds. The n=150 impatience numbers want ≥10 seeds and a
  (n·c) sweep before they're load-bearing.
- The impatience CLOB's *statistics* (q(m), DC laws, tails) are unmeasured —
  it is a different price process; characterize before comparing to level 1.
- Class-2 hitting probability vs n: presumably ~exponentially small; one sweep
  would bound where "statistically live" is honest.
- The maker build itself: A–S quotes from house inventory, GRW zero-feedback
  control arm, pre-registered ⟨ω⟩/δ → 1 and "both absorbing classes become
  impossible" (the binary falsifiers, checkable at n=2 in seconds).

## 7. Addendum (n=500, impatience): the relaxation oscillator

First look at impatience at scale (user run, T=100k, plus certified
reproduction at T=8k): the system ORBITS the Class-1 attractor instead of
falling in — flat pool drains toward all-holding (depth builds to ~580),
takers thin, price drifts one-way, stale clocks flush positions en masse,
pool refills; period ~11k ticks, appearing nowhere in the inputs. An
endogenous boom-flush cycle: the richest macro-dynamics of any arm so far.
Unmeasured: period/amplitude scaling with (n, c, sl); the persistent
downward inter-cycle ratchet (a new convention tilt, presumably the
marketable-to-touch asymmetry) wants the standard treatment. Also logged:
the mystery that found it was a silent local default flip
(hold_fires_close=True) — the fourth such incident; cfg.summary() now
prints the engine switches so a run header always names its arm.
