# The Alpha Engine — State and Journey

Written as a handoff. Readable by a person or by an LLM picking up the work.
Every claim here is either measured or marked as unverified.

---

## 1. Why this exists

The Alpha Engine is a simulation of a closed market. Two currencies, EUR and BTC.
Three hundred agents trade with each other. No outside price feed, no outside money.
The price is not set by anyone — it is whatever the trades produce.

The eventual purpose is an internal market that external traders will interact with.
Before that can be meaningful, we need to know what the internal market does *on its own*.
That is the current goal: a **null model** — a market where we understand every behaviour
and can account for where it came from.

The method is bottom-up. Simple local rules, exact conservation of money, no assumed
price process, no equilibrium condition. The point of building it this way is that
nothing can hide: if the price drifts, the drift must come from a line of code we wrote.
There is no free parameter to absorb it and no closure assumption to bury it.

---

## 2. What the model is

- **Agents.** 150 "longs" and 150 "shorts". An agent's side is fixed for life.
  Longs hold mostly EUR, shorts mostly BTC.
- **Initial capital.** Drawn from a Pareto (power-law) distribution, or optionally a
  normal distribution. Rescaled so the total is exactly 1,000,000 EUR.
- **When an agent trades.** Each agent has an internal clock. Pressure builds every tick;
  when it crosses the agent's threshold, the agent opens a position. An agent cannot
  open a new position while holding one.
- **How much.** Order size is proportional to the agent's capital.
- **How positions close.** Each position has a take-profit level (+10%) and a
  stop-loss level (−10%). Take-profits rest in the order book. Stop-losses fire as
  market orders when touched.
- **The venue.** A central limit order book. It matches orders; it does not trade.

Money is conserved exactly. Profits sum to zero across all agents. Both are asserted
on every tick and have never failed.

---

## 3. What we established

These are measured, with the evidence.

**(a) The price level carries no information.**
The market has no outside anchor, so nothing pulls the price toward any particular value.
It wanders. Its *direction* of drift depends on which currency you quote in: EUR/BTC
falling *is* BTC/EUR rising. The size of the drift comes from two bookkeeping conventions:

  1. A +10% move followed by a −10% move does not return to the start
     (100 → 110 → 99). This is percentage arithmetic, not market behaviour.
     Measuring in logarithms removes it.
  2. Longs budget in EUR and convert to a BTC order at the current price, which
     introduces a factor of 1/p. Shorts do not.

The drift is systematic (price falls in 17 of 20 seeds, p = 0.003), and its sign and
size can be *set* by our choice of conventions. We tried to remove it by making the
model treat both currencies symmetrically. That failed, for a reason worth stating:
orders are denominated in BTC, so the trading mechanism itself picks a currency.
The drift can be tuned to zero. It cannot be derived away by symmetry.

**(b) The model is chaotic.**
A difference of one part in 10^16 in one agent's starting capital — the smallest
difference two computers can disagree by — completely rewrites a 20,000-step history.
We measured final prices of 2.45, 1.92, 3.38, 24.27 from that alone.

Cause: the Pareto draw used `pow()`, which is not required to round identically on
different processors. Fixed by computing the draw in Python's `decimal` module
(software arithmetic, identical everywhere) and summing with `math.fsum`. The rest of
the simulation is only `+ − × ÷` and comparisons, which *are* identical everywhere.
Two different machines (ARM/Python 3.13 and x86/Python 3.12) now produce bit-identical
runs. A test guards this.

**(c) Trading does not redistribute wealth.**
Measured over 20 seeds: change in Gini coefficient = **+0.0003 ± 0.0004**. It does not
grow with a longer horizon (60,000 ticks: −0.0002). It survives price collapses of
10,000× and price explosions of 10,000×.

This follows from the design. Every agent obeys the same rules, nobody has an
information advantage, and order size scales with capital. Profits and losses therefore
scale with capital too, so relative shares cannot move. Note the *mechanism* is
symmetry, not conservation: conservation fixes the total, symmetry fixes the shares.

**(d) The order book compresses the capital distribution.**
This is the one result that was not put in by hand.

Agents *request* an order size exactly proportional to their capital (measured
exponent 1.00 ± 0.02, as the formula dictates). What they actually get filled is
proportional to capital^γ, with γ well below 1. The reason is that a large order must
find counterparties, and counterparty arrival does not scale with the size of the agent
asking.

γ depends on how liquid the market is. Raising the agent firing rate `c`:

| firing rate c | filled ~ capital^γ |
|---|---|
| 0.0005 | 0.52 |
| 0.008  | 0.81 |
| 0.016  | 1.01 |
| 0.032  | 1.05 |

In a thin market a large agent gets filled roughly as the square root of its capital.
In a liquid market it gets what it asked for. Nowhere in the code is 0.5 written down.

Consequence: in a thin market the heavy tail of the capital distribution does not pass
through into profits. Tail index of capital is 1.58; of profits, 2.32 (thinner) when
illiquid and 1.62 (matching) when liquid.

**STATUS 2026-07-10, RESOLVED: qualitative claim confirmed, old numbers retired.**
The c-sweep redone with the committed instrument (filled vs requested EUR notional,
first entries only, 2–3 seeds per point):

| firing rate c | filled ~ requested^γ | frac fully filled |
|---|---|---|
| 0.0005 | 0.075 ± 0.025 | 0.38 |
| 0.001  | 0.115 ± 0.016 | 0.37 |
| 0.004  | 0.468 ± 0.016 | 0.45 |
| 0.016  | 0.888 ± 0.021 | 0.71 |
| 0.032  | 0.957 ± 0.026 | 0.72 |

Monotone γ(c) from ~0 to ~1: confirmed and now committed-instrument-backed. The old
thin-market value (0.52 at c = 0.0005) does not replicate: compression there is far
stronger — γ ≈ 0.1 means fills are nearly SIZE-INDEPENDENT, the book rationing to
counterparty flow so that a large agent receives roughly the same absolute fill as a
small one. The square-root point exists but sits mid-transition (c ≈ 0.004), so any
analogy to the empirical square-root impact law belongs there, not at the thin
endpoint. High-c points used shorter horizons (T = 3–4k), first entries only.

**(e) The model is exactly scale-invariant in the starting price — now understood
and repaired.**
The old rule ("verified at 0.25…1,048,576; breaks below 0.25; do not run x_0 < 0.25")
was wrong in both directions, because every verified point was a power of two. The
truth has two parts:

  1. *Exact bit-identity of p/x_0 holds precisely on powers of two*, where binary
     floats scale exactly. Any non-power-of-two x_0 (3.0, 0.3, …) diverges within
     ~20 ticks from representation rounding — chaotic reshuffling, benign for
     statistics, fatal only for trajectory identity. This is float arithmetic, not
     a model asymmetry.
  2. *A genuine absolute scale WAS hiding in the code*: the dust thresholds (the
     book's 1e-12 BTC size cutoffs, the 1e-9 BTC settle threshold) are fixed while
     BTC quantities scale as 1/x_0. This broke exact invariance below x_0 ≈ 2^-8
     (first divergence at tick 890 for x_0 = 2^-10). Fixed: thresholds now scale as
     1/x_0 (Book(size_eps=1e-12/x_0); settle at 1e-9/x_0). Invariance re-verified
     bit-exact from x_0 = 2^-16 to 2^6.

New rule: any power-of-two x_0 in [2^-16, 2^6] is exactly equivalent; non-powers of
two are statistically equivalent but not bit-comparable.

**(f) Stop-losses carry a systematic long→short transfer, tied to the currency
convention.**
Measured over 20 seeds at committed defaults: mean final pnl_long = −3,432 ± 1,132 EUR
(positive in only 7 of 20 seeds), and the loss scales with activity — correlation of
pnl_long with total matched volume is −0.81. Normalised, longs lose roughly 2–3% of
round-trip notional. Decomposing 22,000 round trips by exit type (six active seeds):

| side | exit | count | mean realized return |
|---|---|---|---|
| long  | TP | 7,628 | +10.00% exactly |
| long  | SL | 6,033 | −15.2% |
| short | TP | 6,198 | +10.00% exactly |
| short | SL | 2,075 | −16.5% |

Take-profits fill at their limit price to the fourth decimal, for both sides. Stops
cost the stop level plus ~5–6 points of slippage, roughly the same per event for both
sides. The entire transfer is in *frequency*: longs stop out three times as often
(44% of their round trips vs 25%). This asymmetry is NOT the percentage gauge — with
log-symmetric bands (log_thresholds=True) the transfer persists at the same size
(−4,073 ± 1,006 over the same seeds). It is NOT the realized price direction — the
0.55 / 0.75 TP-rate split holds even in seeds whose price ends higher. It DOES flip
under mirror=True, which moves the 1/p conversion to the other tribe: there the shorts
stop out more and the longs collect. So the transfer is real EUR, moves through the
stop-loss channel, and is ultimately another expression of the residual currency-
convention asymmetry of §(a) — the same asymmetry, read off the PnL ledger instead of
the price.

Micro-channel tests (all realized-only, via trade_log; predictions stated first):

  * *Local drift is ruled out.* Bootstrap paths built from each run's own per-tick
    log-returns predict TP-first probabilities of 0.50/0.50 for both bands. The
    observed 0.56/0.75 split therefore requires microstructure correlations — who is
    resting on which side of the book — not the path statistics.
  * *Stop cascades are real and large.* 33% of stop events occur in same-tick,
    same-side clusters against a 3% Poisson expectation; the largest single-tick
    avalanche was 23 stops. A stop is a market order that moves the trigger price for
    every other stop on its side.
  * *The sizing convention sets the sign, but there is no clean dial.* Realized long
    edge per EUR of round-trip notional: −1.8% under the default (current-eur budget,
    1/p conversion), +1.3% under frozen sizing (K0-fixed, no price factor), +2.1%
    under invariant sizing (K0-fixed, p^(−1/2)). The last falsified the stated
    prediction that the covariant exponent would zero the transfer. The arms confound
    two things — the price exponent and the wealth-feedback source (current balance
    vs frozen K0) — so the exponent alone does not order the outcomes. The clean next
    cut is symmetric_sizing=True, which keeps the current-eur budget and changes only
    the conversion (/x_0 for /p), isolating the exponent within the feedback family.

What is established: the transfer is real EUR, flows through stop frequency, is
amplified by cascades, is independent of the path's own drift and of the TP/SL gauge,
and its sign is a function of the sizing convention. What is open: a predictive map
from convention to sign and size.

**(g) Convention mixing and evolution: machinery built, first results, three
cautions.**
Since no neutral convention exists, symmetry can be constructed (or discovered) at
the population level. conv_mode="mixed" gives each agent a per-agent trait — convert
at the live price vs at x_0 — with conv_mix setting the init fraction per tribe, and
evolve=True adds within-tribe imitation on a dimensionless fitness (window realized
PnL per EUR of entry notional; a currency-denominated fitness would privilege that
currency). First measurements, all on 2 seeds only:

  * The diagonal mix sweep (same fraction in both tribes, 0.1→0.9) shows a positive
    long edge everywhere and does NOT interpolate the legacy and mirror corners —
    because it cannot: legacy (longs live, shorts ref) is off the diagonal. The
    convention space is a 2-D square (mix_long, mix_short), not a line. Map the
    square, not the diagonal.
  * The within-tribe conditionals show a frequency-INDEPENDENT preference in 8–9 of
    10 rows: longs do better live, shorts do better ref — which is precisely the
    legacy corner, where the long tribe collectively bleeds. If this survives more
    seeds, individually rational convention choice is collectively self-defeating
    for the longs: a commons problem inside the null model. Tentative; 2 seeds.
  * The evolution runs (T=40k, epochs of 2k) went nowhere: mix pinned at ~0.5,
    switch counts decaying to zero — as PREDICTED BY THE NOISE BUDGET, not by any
    equilibrium. An agent settles ~1.3 round trips per epoch; one ±10–15% outcome
    against a ~2% selection signal is luck, not fitness. Selection needs ~36 settled
    trades per agent per window: evolve_every ≈ 50k ticks, horizons ≈ 10^6, or a
    cumulative (lifetime) fitness instead of a windowed one. The stated prediction
    P3 (drift toward an interior equilibrium) is therefore UNTESTED, not falsified —
    the test lacked power, which is a different failure and was diagnosed as such.
  * The 2-D map (corners + center, 3 seeds each; conv_mix_long/short now in config)
    overturns the blend recipe. Realized long edge per EUR notional:
    (1,0) legacy −2.2% [tight]; (0,1) mirror-corner +4.4% [price explodes, regime-
    contaminated]; (0,0) both-reference +1.5% [wide, crosses zero]; (0.5,0.5) center
    +4.7% [unstable, one seed at +11%]; **(1,1) both-live −0.4% [tightest, straddles
    zero]**. The zero-transfer locus runs near the both-live corner, NOT the center:
    matching the convexity across tribes beats averaging it within them. Constructed
    symmetry should therefore be sought at the symmetric corners (both-live
    preferred), and the 50/50-blend recommendation is retired. 3 seeds; the corner
    ranking needs ≥10 before anything is built on it.

---

## 4. What we retracted

This section matters as much as the previous one.

**"Trading concentrates wealth."** Reported with confidence, built on for several hours,
then found to be a bug in the measurement script. It compared each agent's *final*
holdings valued at the starting price against the *same final holdings* valued at the
ending price. That is not a comparison of before and after. It measures the price move.

The mechanism is an identity: an agent holding mostly EUR has a wealth that scales as
1/√p; one holding mostly BTC scales as √p. Since longs hold EUR and shorts hold BTC,
*any* price move separates the two groups — with no trading at all. The false effect was
100× larger than the real one and correlated 0.91 with the size of the price move.
It also "confirmed" itself: in runs where the market froze, the false effect vanished,
which read as "no trading, no concentration" but actually meant "no trading, no price move."

**"The Pareto tail supplies the market's liquidity."** The firing threshold had been
defined as capital ÷ *smallest* capital. The smallest capital is the least stable
statistic in a sample. Raising the spread of capital drove the smallest agent down,
which slowed the entire population's clock, which looked like heterogeneity destroying
trading. With the threshold defined against the *mean* — which is fixed exactly by
construction — the effect reverses: more spread means more trading, not less.

**"PnL is always normally distributed."** Based on single-seed kurtosis readings of 0.24
and 0.31. Kurtosis of 300 samples is extremely noisy. Averaged properly, it is ~2.5, and
a normality test rejects in every configuration. Profits are unimodal and centred but
mildly heavy-tailed with negative skew.

**"Volume falls as the price collapses."** The dashboard plotted volume in EUR. EUR volume
is BTC volume × price. The price fell 10,000×. Trading activity was in fact constant —
about 400 clearing events per 5,000 ticks, from start to finish. Same class of error as
the wealth bug: a quantity read through a unit that was itself moving. The dashboard now
plots both.

**"The tail index of profits equals α/γ."** A clean-looking prediction that fits only at
the liquid endpoint, where it is trivially true. The error: total volume is size × number
of trades, but profit dispersion goes as size × √(number of trades). A first moment was
used where a second moment was needed.

**"Longs systematically profit."** Read off a single seed (42: pnl_long +1,235 in a
falling market) and taken as the phenomenon to explain. Across 20 seeds the mean is
−3,432 and the sign is negative in 13 of them. The one-seed reading had the wrong sign
and was an order of magnitude too small. §9's rule — the model is chaotic, compare
distributions across seeds, never trajectories — applies to PnL as much as to price.

**"The side asymmetry is the arithmetic TP/SL gauge."** Proposed with a clean mechanism
(±10% arithmetic bands are asymmetric in log space: ln 1.1 = 0.0953 up vs |ln 0.9| =
0.1054 down, giving the long a +0.5%-of-notional edge per round trip) and a magnitude
that matched the single seed to within 40%. Stated as a prediction, then falsified the
same session: the log-symmetric arm (log_thresholds=True) shows the same transfer at
the same size, and the transfer has the opposite sign to the prediction. The paired
arithmetic-minus-log difference (+641 ± 715) is consistent with the barrier effect
existing at its predicted size — but as a subdominant correction riding on a mechanism
five times larger. A fluent story with correct arithmetic and a supporting data point
is still just a hypothesis until something can falsify it.

---

## 5. What the mismatches tell us

Nearly every wrong prediction fell into one of two kinds, and the difference is the
useful part.

**Kind one — measurement errors dressed as findings.** The wealth-concentration bug, the
min-statistic clock, the volume collapse. In each case a quantity was compared against
something that was itself changing, and the result looked like economics. These were not
the model surprising anyone. They were mistakes that survived because they were plausible.
Every one was caught by a measurement that *could have* contradicted it. None were caught
by thinking harder.

**Kind two — real consequences of rule interactions.** Predicting that decoupling firing
rate from size would let big agents dominate: wrong, because agents cannot fire while
holding a position, so a faster clock buys them nothing. Predicting that the fill
exponent would approach 1 with more agents: wrong, because adding agents also shrinks
each agent. These were cases where two rules we had written down interacted in a way
that verbal reasoning did not reach.

The second kind is the argument for building the model bottom-up. Individual rules are
easy to reason about. Their interactions are not, and they are where the behaviour lives.

The first kind is the argument for distrusting fluent explanations, including — especially —
the ones an LLM produces. The bugs above were all in analysis code written by the LLM,
described in confident language, and accepted because the story sounded like a market.
The correct posture is: state the prediction before running, then run something that can
falsify it.

---

## 6. Where we are

The null model is nearly complete. The committed defaults are paper-faithful:
Pareto capital, `clock_beta = 1.0`, `phase_jitter = True`, take-profit and stop-loss
both at 10%.

In this baseline: money is conserved, profits sum to zero, all agents survive, all seven
internal consistency checks pass, and runs reproduce bit-for-bit on any machine.
The price wanders chaotically with a convention-driven downward drift. The wealth
distribution is unchanged by trading. One measured departure from "trading has no
consequence" is now on the books: the stop-loss channel carries a systematic
long→short transfer of order 0.1–1% of capital per 20,000 ticks (§3f), and it is
convention-tied (it flips under mirror). Until its micro-channel is isolated, any
heterogeneous-agent result that shows one side out-trading the other must first be
checked against this baseline transfer.

---

## 7. What comes next

Two things, in order.

**First, hand-validation.** Everything above rests on analysis code an LLM wrote. Section 4
is the reason that matters. Priority order, highest risk first:

1. `Analyser.wealth_concentration()` — the exact place a false headline was produced.
   Check by hand on a three-agent toy where the answer is known.
2. The fill exponent γ — the only genuinely emergent result, and the least verified.
   Rests on a monkeypatched instrument that was never written to a file, and on a
   `c`-sweep that changes liquidity and activity together.
3. Conservation and zero-sum — already asserted every tick; cheapest to trust.
4. The scale-invariance in x_0 — exact, bit-level, verifiable by inspection.
   The strongest result we have.

**Second — DONE, partially (§3f).** Micro-channel tests ran 2026-07-10: drift ruled
out, cascades confirmed, sizing convention shown to set the sign without a monotone
dial. Remaining: the symmetric_sizing=True cut (exponent isolated within the
wealth-feedback family), a cascade-strength measurement (transfer vs a
counterfactual with per-tick stop batching disabled), and — from §3(g) — the 2-D
(mix_long, mix_short) map at ≥10 seeds per point, plus a properly powered evolution
run (cumulative fitness or epochs ≥ 50k ticks) to test P3 for real.

**Third — the γ replication FAILED; redo the sweep.** The committed trade_log now
records requested and filled notional per entry, so γ(c) can be measured properly:
rerun the c-sweep {0.0005, 0.001, 0.008, 0.016, 0.032} with ≥10 seeds each, both
estimands (filled~requested and filled~K0), sides separated. The clock_beta=0
dispersion cross-check from the earlier plan still applies once the sweep exists.

**Fourth, break the symmetry.** Wealth can only concentrate if some agents systematically
out-trade others. At present every long is a scaled copy of every other long. The intended
step is heterogeneous agents — some following trends, some betting on reversal, with a
single parameter mixing them — which would also give the price something to revert toward.

One constraint carries over from the covariance work: any such rule must be written in
quantities that do not depend on which currency we quote in, and any reversion target must
be produced by the agents themselves rather than fixed from outside. Otherwise the result
is another convention wearing a costume.

---

## 8. Do not re-break these

1. **Never use `rng.pareto()` or `np.sum()` in the capital draw.** `pow()` is not
   bit-identical across processors and `np.sum()`'s order varies by library version.
   The model is chaotic; one bit rewrites everything. Use `decimal` and `math.fsum`.
   `tests/test_portable_init.py` guards this.

2. **Never define the firing threshold as capital ÷ minimum capital.** It makes the whole
   market's pace depend on the single unluckiest draw. Use the mean, which is fixed at
   K/(2n) exactly because the draw is rescaled.

3. **Never compare wealth at two different prices.** Use `Analyser.wealth_concentration()`,
   which fixes the price. The docstring explains why.

4. **Never read EUR volume as market activity.** Use BTC volume or the number of clearing
   events.

5. **Do not add a restoring force that pulls the price toward a fixed level.** It would
   privilege the currency in which that level is defined.

6. **Never read total PnL at the final price as side performance while positions are
   open.** The unrealized mark of open inventory scales with the price move and swamps
   the realized transfer (the sl_enabled=False and mirror=True runs produced "PnL" of
   10^5 and 10^13 EUR this way — both pure valuation). Decompose realized vs
   unrealized; the trade_log holds the realized side.

7. **Never characterise side PnL from one seed.** Seed 42 says longs win +1,235; twenty
   seeds say longs lose −3,432 ± 1,132. Same rule as §9 for prices, now with a scar of
   its own.

8. **Never compare trajectories across x_0 values that are not both powers of two,
   and never reintroduce absolute dust thresholds.** Bit-identity in p/x_0 exists
   only where binary scaling is exact; and any epsilon denominated in BTC or EUR
   must be expressed in model units (scaled by 1/x_0 for BTC), or it becomes an
   invisible absolute scale — that was the §3(e) leak.

---

## 10. Code changes, this session (2026-07-10)

All behavioural claims above §3(f) were re-verified after these changes.

- **market.py is retired.** The Dutch auction has not run since the CLOB landed;
  nothing imports it. It now carries a deprecation banner and warns on import. The
  simulation.py header, which still narrated the auction loop, now describes the
  actual CLOB tick.
- **Per-tick conservation checks are on by default** (run_checks=True). The previous
  entry point ran with them off, so "asserted on every tick" was not true of the runs
  that produced the standard plots. It is now.
- **Residual market-order submission is shuffled per tick** (SL closes keep priority;
  entries shuffle among themselves). Previously agents were submitted in id order,
  giving agent 0 a standing price-priority advantage over agent 299 — a fixed symmetry
  break in a model whose headline is that no agent has one. The shuffle stream is its
  own SeedSequence((seed, 0xA1FA, tick)): integer arithmetic, bit-identical across
  platforms, independent of the capital-draw and jitter streams. CONSEQUENCE: all
  stored reference trajectories change (seed 42's p_final moves from 0.084 to 0.042).
  Determinism per seed and across machines is preserved and was re-verified;
  tests/test_portable_init.py (init-only) is unaffected.
- **Committed trade_log instrumentation** (simulation.py): one record per settled
  round trip — tick, agent, side, TP/SL exit, realized PnL, entry notional. This is
  what §3(f) was measured with, and it replaces the never-committed monkeypatch that
  §7 flagged as the weakest link under the γ result.
- **Recorder keys book_bids / book_asks replace queue_long / queue_short.** The old
  names inverted the tribes: the bids are shorts' TP buybacks and the asks are longs'
  TP sells. The dashboard panel now says so.
- **pnl_house is recorded from the house's actual position tally** instead of a
  hardcoded 0.0, so the zero-sum check stays honest the day bailouts or spread income
  turn on.
- **cfg.W is vestigial and no longer called.** Entries are IOC and TP limits never
  expire, so book.expire() was a structural no-op. The field remains for config-file
  compatibility, marked as such.
- Stale artifacts fixed: agents.py's self-check called a method that no longer exists
  (would have crashed); the q docstring described an all-in/baseline regime split that
  open_btc does not implement; the sizing_power comment contradicted its value; the
  capital-distribution plot drew its baseline at the pre-rescale Pareto floor rather
  than the actual post-rescale minimum; the dashboard legend still said "auction
  cleared".
- New: exp_side_asymmetry.py / exp_chunk.py (the §3(f) experiment, predictions in the
  header) and exp_side_asymmetry.jsonl (the 40-run results).
- trade_log extended with entry_tick, K0, and req_q (requested EUR notional at fire),
  making γ measurable from committed code — which is how the §3(d) dispute surfaced.
- New: exp_microchannel.py (tests A–D, predictions in the header) and the
  microchannel_{arm}_{seed}.json artifacts (trade logs + full price series for the
  baseline, frozen, and invariant arms, six seeds each).
- Scale-aware dust thresholds: Book(size_eps=1e-12/x_0), settle at 1e-9/x_0 —
  closes the §3(e) scale break; x_0=1 trajectories unchanged (eps identical there).
- conv_mix_long / conv_mix_short config fields (per-tribe mix; the 2-D convention
  square). Corner (1,0) verified bit-identical to the legacy sizing path.
- New artifacts: convmap.jsonl (the 2-D map runs) and gamma_sweep.jsonl (the redone
  γ(c) sweep behind the §3(d) resolution).
- New: conv_mode / conv_mix / evolve* config fields, the per-agent conv_live trait,
  within-tribe imitation in the loop (own SeedSequence stream, determinism verified),
  per-tick conv_live_long/short recorder fields, exp_evolution.py, and the
  evolution_sweep.jsonl / evolution_run_{seed}.json artifacts. conv_mode="legacy"
  (default) leaves every prior code path byte-identical.

---

## 9. Cautions on the numbers above

- The `c`-sweep for γ used 2–3 seeds at short horizons. The direction and the endpoints
  are solid; intermediate values are not precise.
- `c` changes liquidity and firing frequency together. The separation is not surgical.
- Kurtosis is the wrong statistic for a Pareto(1.5) tail, which has no finite fourth
  moment. Use a tail-index estimator.
- The instrumentation that measured fills was a temporary patch, not committed code.
- Any comparison of single trajectories across machines or parameter settings is
  meaningless. The model is chaotic. Compare distributions across seeds.
- The three sizing arms in §3(f) differ in TWO respects at once (price exponent AND
  wealth-feedback source); conclusions drawn from comparing them are correspondingly
  coarse. The frozen and invariant arms also destabilise the price violently
  (|ln p_final| up to 13), so their realized edges come from very different price
  regimes than the baseline's.
- The §3(f) decomposition table pools six deliberately-active seeds (chosen because
  the transfer scales with activity); the 20-seed means are the population-level
  numbers. The mirror=True flip is qualitative (rates and signs), not quantitative —
  mirror runs drift so violently (|ln p| ≈ 25–28) that their magnitudes measure the
  valuation channel, not the transfer.
