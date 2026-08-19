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
