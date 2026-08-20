# EVALUATION of NFNN — what the null model does, and why

See results of n=150 in `bench/` and n=5,000 in `runs/`.

Agents with zero intelligence produce a market that looks remarkably like the real thing. We built a sealed toy economy — a few thousand identical robots trading two currencies through an order book, each following one dumb rule: wake on a timer (normal), open a trade with size s (N), take profit at +tp% or bail at −sl% (F), exit if nothing happens (N). No news, no beliefs, no strategy. Yet out come bubbles, short squeezes, crashes, and long trends; unpredictable prices whose calm and turbulent spells cluster the way real markets' do; rare extreme jumps at fine time scales that smooth into a bell curve when you zoom out; and, on its own trading-activity clock, the same quantitative "overshoot" law that has been measured in real foreign-exchange data. Small markets even develop their own signature pathology — the run's lucky winners become whales whose recycled wealth drives an endless slow-bleed-and-snap-back sawtooth, which melts away once the crowd is large enough. The sobering conclusion cuts both ways: none of these famous market patterns, on their own, is evidence that anyone in the market knows anything — and whatever genuine intelligence contributes to real markets, it must be found in what this mindless machine cannot do.

---

## 1. The sawtooth at small n (n≈150): made whales, leak, wall, snap

The signature price pattern of small markets in this model is a sawtooth:
a slow drift punctuated by sudden snaps back, repeating for as long as the
run lasts. The mechanism, from the very beginning:

- **Why the price moves far from 100 at all: pure luck.** Early on, one
  side's flow happens to be a bit stronger, and the price moves. That hurts
  the other side, whose own rules force it to close positions — and closing
  means trading in the *same* direction that hurt them. A self-feeding
  squeeze, until the losing side is nearly out of ammunition. The price is
  now far from where it started and stays in that region: it has **pinned**.
- **The wealth was earned, not dealt.** This happens even when every agent
  starts identical (NFNN: normal capital, no born whales). Order size in
  this model is *current* wealth ÷ q, evaluated each time an agent fires —
  so the winners' orders balloon as they win. The squeeze manufactures
  whales that the initial deal never contained. NFNN kills *born* whales;
  it does not prevent *made* ones — and at small n, made whales are enough.
- **The leak (the slow ramp of each tooth).** After the pin, both sides
  keep firing on their clocks. But the losers' orders are tiny (small
  wealth ÷ q) and arrive as a fine drip against the price, while resting
  take-profits add steady pressure the same way. The drip moves the price
  a hair every tick, always in the same direction: the price bleeds.
- **The wall.** The winners' clock-driven orders are enormous single
  bites. When such a bite does not fill immediately, it rests in the order
  book at its price — and these giant resting orders stack up ahead of the
  drifting price: a thick wall of waiting demand.
- **The snap (the vertical edge).** The leaking price eventually drifts
  into the wall. The wall's buying power swallows everything offered in
  one cascade, and with one side of the book emptied, the price jumps
  straight back. Nothing fundamental has changed — same rich winners, same
  poor losers, same clocks — so the leak resumes. Tooth after tooth.
- **The tooth period is the capital-redeployment cycle** — how long the
  winning side takes to rotate its banked profits back into the market.
  Measured: period ∝ c^−0.98 (prediction −1). Fire every clock twice as
  fast and the teeth come twice as dense. Tooth amplitudes sit in a
  universal 1.4–3.3 e-fold band across configurations.

## 2. Why the sawtooth vanishes at n = 5,000

- At n=150 the wall is a few made-whales' **lumps**: demand arrives in big
  packets, so the market charges up and discharges — a dripping bucket
  that periodically tips.
- At n=5,000 the same total redeployment is divided across ~33× more
  winners, each bite ~33× smaller relative to the book — below the size
  where one order can cross a whole side. The clocks are unsynchronized,
  so buying arrives as a **steady stream**, not lumps. The leak is refilled
  continuously; there is nothing to snap. The price settles into an
  ordinary wiggling range.
- The sawtooth is therefore a **finite-size phenomenon**: wealth
  concentration heard through a market small enough that individual
  clocks are audible.
- Inside the settled range the order book *deepens*: positions keep
  opening on schedule while exits (±1%) are rarely reached, so resting
  orders pile up on both sides. The deep book and the quiet price are one
  phenomenon — every attempted move runs into more stored volume than
  before. (Real markets build volume-at-price the same way where price
  lingers.)

## 3. The event-time laws: gate on the regime, or measure nothing

The n=5,000 tape mixes two markets: long trending stretches and a calm
range. Measured separately (25.8M prints, event time):

| segment | E_N (BM −2) | ⟨ω⟩/δ (law: 1.0) | median/δ (BM 0.70) | mean/median (BM 1.5) |
|---|---|---|---|---|
| TREND (18.1M prints) | −2.74 | 0.707 | 0.395 | 1.79 |
| RANGE (7.3M prints) | **−1.67** | **0.946** | **0.719** | **1.40** |
| full tape | −2.42 | 0.834 | 0.480 | 1.74 |

- The calm segment sits essentially **on the FX overshoot law**
  (⟨ω⟩ ≈ δ), with the median ratio at Brownian's value. The trending
  segment is steep and suppressed. The full tape is a weighted blend that
  describes neither.
- Practical rule for all future analysis: **slice by regime first.**
  Whole-tape exponents on a regime-mixed series are accounting, not
  physics. The tell is mean/median ≫ 1.5: that means trend contamination.
- Tick time cannot see these laws at all (~86 prints per tick censors the
  event structure); the event clock is the model's natural time.

## 4. Stylized facts: simulation (n=5,000) vs real markets

Matches real markets:

- No return predictability beyond one step (ACF ≈ 0 past lag 1).
- Volatility clustering: busy periods follow busy periods, at every
  resolution.
- Trade-level bounce: negative one-lag autocorrelation print-to-print,
  the model's version of bid–ask bounce.
- Fat tails at fine scales that fade under aggregation. In plain words:
  at the single-trade scale, price changes are mostly *nothing* with
  occasional *jumps* — extremes dominate. Zoom out, sum ~100 trades into
  one step, and the jumps average in with the nothing: the distribution
  approaches a bell curve. Real markets do exactly this.
- The FX overshoot law in event time (on the stationary segment).

Honest differences:

- The null's tails are **milder** than real markets' (tick-level excess
  kurtosis ~2–5 vs ~10+ in real data). It has tails, but tame ones.
- Beware granularity: kurtosis measured at the single-print scale is
  astronomical (10³–10⁴) *because most consecutive prints share a price*
  — a spike of exact zeros with rare band-jumps. Aggregated to the tape's
  natural grain (~86 prints ≈ one tick) it collapses to the tick values.
  Sub-grain kurtosis measures market microstructure, not risk.

The punchline of the whole model: **agents with zero intelligence produce
all of the above.** None of these features, observed in a real market, is
by itself evidence of information, strategy, or skill.

---

# EVAUATION of scan results

## 1. What each knob does (the 16-combination scan)

All 16 knob combinations, 8 seeds each, n=500, 150,000 ticks — 128 runs.
The four knobs are not equally important. In easy terms:

**The exit-band knob (`band_dist`) is the master dial.** It sets the
market's texture:

- *Everyone the same bands* ("fixed"): all exit orders sit exactly ±1%
  away, so the book is a sparse ladder with 1%-wide gaps — every trade
  jumps a big step. Per-tick volatility ≈ 0.0145 (the band scale itself).
- *Everyone their own bands* ("normal"): exit orders smear over a whole
  range of prices, the book becomes dense, and the price creeps through
  it in tiny steps. Per-tick volatility ≈ 0.0006 — **about 25× quieter**
  — yet these markets lock into the sawtooth far MORE often (95% vs 64%
  of runs), travel further (mean |drift| 4.0 vs 2.9), and show stronger
  volatility clustering (0.55 vs 0.30). Quiet, but more extreme.
- The band knob even changes the scaling law: fixed-band markets count
  directional changes like random walks (E_N ≈ −2.1); own-band markets
  are tooth-dominated and count them almost flat (E_N ≈ −0.8) — a third
  regime, belonging to the locked sawtooth.

**The money knob (`capital_dist`) is the second dial.** Whale wealth
("pareto") makes markets lock more often (94% vs 66%) and overshoot
harder (⟨ω⟩/δ ≈ 3.1 vs 1.5) than equal-ish wealth ("normal"). Born
whales accelerate what made whales achieve anyway — concentration is
concentration, however it arrives.

**The timer knob (`closing`) and the size knob (`size_dist`) barely
matter.** Their averages are near-identical across the board (lock 77%
vs 83%, same volatility, same scaling exponents). One careful caveat:
these knobs add RANDOM variation — timing and size jitter drawn once,
blind to the market. Timing and size that RESPOND to the market
(entering on a move, sizing to conditions) are feedback, not
heterogeneity, and are untested here — that is precisely what the
intrinsic-time clock (block 2e) and level 1 will add. What this scan
establishes is the control: since blind jitter changes nothing
systematic, any effect those additions produce will be attributable to
the feedback itself.

**And in every one of the 128 runs, direction stayed a coin flip.**
Locking arms split up and down across seeds with no lean anywhere —
the knobs set how violently a market locks, never which way.

**Rule of thumb:** heterogeneity of *wealth* or of *exit rules* drives
locking and extremes; blind randomness in *timing* and *size* is
decoration — market-responsive timing and sizing belong to the next
level of the model. And since real markets certainly have heterogeneous
wealth and heterogeneous exit rules, the null's message is that their
locking tendencies need no further explanation.
