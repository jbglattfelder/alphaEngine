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

# EVALUATION of scan results

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
  (this number is set by how widely the bands are SPREAD, not by the
  bands themselves — see section 3 below)
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

## 2. Tilting the exit rules (the bands scan)

Every agent leaves a trade either happy (price moved 1% in its favor —
the "take-profit") or sad (1% against — the "stop-loss"). What if those
two distances are not equal? Six variants, all in the calm NFNN world:

- **How jumpy the market is depends on the happy exit only.** Per-tick
  wiggle = 1.44 × the take-profit distance, almost exactly, whatever the
  stop is set to. Reason: happy exits are *waiting* orders — they sit in
  the book and form the rungs of a ladder the price climbs; the rung
  spacing IS the take-profit distance. Sad exits fire and vanish; they
  leave no rungs.
- **Patient losers make calm markets.** Stops wider than take-profits
  (leave sad only after −2%, leave happy at +1%): no run ever locked,
  and the jumpiness statistics came out almost bell-curve normal — the
  tamest, most "healthy-looking" market the model has produced.
- **Twitchy losers make wild markets.** Stops tighter than take-profits
  — the textbook advice "cut your losses early, let profits run" — never
  calmed anything: fewer full lock-ins than the symmetric case, but the
  most violent jumps of all (rare-event measures 500–1000× a bell
  curve), because tight stops mean panic exits fire constantly, each one
  shoving the price.
- The amusing inversion: the famous investor "mistake" (take profits
  quickly, let losses ride) is exactly what *stabilizes* this market,
  and the famous "discipline" destabilizes it. In a world with no
  information, patience with losses is a public good.

## 3. Sliding each dial to zero (the peaky scan)

Each "normal" dial adds person-to-person variety with an adjustable
spread. Shrink the spread toward zero and each dial should smoothly
become its no-variety sibling. Does it?

- **Timing and bite-size: yes.** Shrunk to near-zero spread, both are
  statistically indistinguishable from their siblings. Smooth, boring,
  as designed.
- **Money: the everyone-equal world has a pulse.** With all wallets
  (nearly) identical, all internal clocks are identical too — so the
  whole population acts *in unison*, and the price moves in visible
  staircase steps with the most extreme jump statistics of the family.
  No lock-ins, though: equality means no whales, and no whales means no
  walls.
- **Bands: NO — and this is the family's discovery.** Shrinking the
  band spread does *not* recreate the everyone-identical market. With
  exactly equal bands, all the waiting exit orders stack at the same
  price: one thick rung, and the price jumps rung to rung. Give the
  bands ANY spread at all — even ±0.03% around 1% — and the single rung
  splits into a fine staircase that the price creeps through in
  microscopic steps. Measured: the per-tick wiggle equals the *spread*
  of the bands, not the bands (spread 0.0001 → wiggle 0.00008). The
  identical-bands market is a knife's edge: an infinitely sharp special
  case that any real-world variety, however tiny, tips over into a
  completely different market. Since no real market has perfectly
  identical participants, the creeping kind is the realistic kind.

## 4. Bite size (the q scan)

Each agent bets 1/q of its wealth per trade. Sweeping q from 2 (half
your wealth per bite) to 32 (slivers):

- **Jumpiness does not care.** Per-tick wiggle identical to three
  decimal places across the whole sweep — more proof that the exit
  ladder, not the order size, sets the market's texture.
- **Lock-ins peak in the middle.** Giant bites (q=2) gouge visible
  teeth in the price but never fully pin the market — a huge order
  swallows the opposing wall and thereby spends itself. Slivers (q=32)
  are a harmless stream. The dangerous zone is between (q≈8–16, 40% of
  runs locked): bites big enough to push, small enough not to
  self-destruct. Moderation, it turns out, is what pins markets.

## The one-sentence summary of all three scans

WHERE the waiting exit orders sit sets the market's texture (and
identical-for-everyone is a razor-thin special case); HOW BIG the bites
are sets whether it locks (with the danger in the middle, not the
extremes); WHEN people act, as long as it is blind to the market,
sets nothing at all.

---

# EVALUATION of the big runs (total of 10,000 and 15,000 agents)

We then ran the model at serious size — up to 15,000 agents for 400,000
ticks — in two flavors. In the first, every agent has the SAME exit
rules (take profit at +1%, bail at -1%): the simplest possible world,
and the one all the scans grew from. In the second, every agent gets its
OWN personal exit rules, drawn around 1%: the realistic world — recall
from the scans that "identical for everyone" is a knife's edge no real
market sits on. The shift between the two turned out to be one of the
biggest stories of the whole project. Findings in order of surprise.

## 1. Crashes are not a small-market problem

The sawtooth (the slow-bleed-and-snap cycle) disappears in big markets,
as expected: it needs one big player's wall, and a crowd has no walls.
But big markets found a new failure: **sudden cliff crashes** — the
price falling off a step in moments. The mechanism is a chain reaction:
people who bought at similar times have their panic exits at similar
prices, so one dip triggers a batch of panic selling, which triggers the
next batch, like dominoes. And adding more agents just adds more
dominoes. So the two classic disasters split cleanly: **the sawtooth is
a small-market disease; the crash is not.** Even a market of thousands
of mindless, uncoordinated agents crashes — no panic psychology
required, just exit rules standing too close together.

## 2. A market can shrink without losing anyone

One big run in the same-rules world (15,000 agents) collapsed
88% and then settled into a narrow range — and in that range, the little
sawtooth came BACK, in a market of thousands. The resolution: what
matters is not how many agents exist but how many still have meaningful
money. After the collapse, wealth was so concentrated that the market
effectively contained only a handful of players again. **The effective
size of a market is set by its wealth distribution, not its head count —
and it can shrink during the run.** A market that grinds its losers down
eventually behaves like a small market, whatever its population.

## 3. Variety keeps markets alive

Then the big switch: the same market, but with every agent's exit rules
drawn individually. The change of character was dramatic. The same-rules
big market moves in fixed 1% hops — the price climbs a ladder whose
rungs are everyone's identical exit orders, and at some sizes it locks
into that ladder entirely. The varied market has no rungs: it creeps in
microscopic steps, its extreme-jump statistics calm from astronomical to
merely large, and it never locked and never sawtoothed — it trended,
corrected, crashed once and recovered, and was still going strong when
time ran out, at both 10,000 and 15,000 agents. The small-market scans
had suggested varied exit rules cause MORE locking; at scale the
opposite holds. **Diversity of behavior is what keeps a big market from
getting stuck.** These varied-rules runs also redistribute wealth far
more dramatically: the spread of individual outcomes is several times
wider, and it is always the LOSING side that redistributes internally —
lucky losers profit hugely from unlucky ones, while the winning side's
gains stay modest and even.

## 4. Big calm markets damp their own moves

In every big, healthy run, price moves systematically travel LESS beyond
any threshold than a coin-flip price would — roughly half as far. The
deep pile of waiting orders absorbs momentum: push the price, and the
book pushes back. Small print: real currency markets do NOT show this —
their moves carry through in full. So the mindless market is actually
*calmer* than the real thing, and whatever real markets have that keeps
their moves carrying (herding, trend-chasing, news) is precisely what
this model leaves out — by design. The one place our model DID match the
real-market pattern was the collapsed, concentrated market of finding 2:
the pattern real markets show appeared here only in the dying state.

## 5. The market writes its own price tag

Nobody in this model is paid to quote prices — there is no market maker.
The gap between the best buyer and the best seller (the "spread", the
cost of trading right now) simply emerges from whatever orders happen to
be resting. In the big runs it emerges remarkably well: both sides are
quoted about 98% of the time, and the typical gap is about 0.05% of the
price — a twentieth of the 1% exit bands, because the resting orders of
thousands of agents, anchored to thousands of different past prices,
pave the price axis almost continuously. The paving is a crowd product:
run the same market with 1,000 agents instead of 10,000 and both sides
are present only ~78% of the time, with a gap eight times wider. **A
tight, always-open market is not something someone provides — it is
something a crowd secretes.**

## 6. The calm is worth money — and that is a design question

If moves reliably fall short, betting against every move is profitable.
We tested this: a simple rule — whenever the price reverses by 1%, bet
that the reversal fizzles — wins 87% of the time and clears realistic
trading costs several times over on the big-run data. Nobody inside the
model can exploit this (they cannot see the market), but an outside
agent could, and its profits would drain the internal agents' wealth —
shrinking the market's effective size (finding 2) until it dies. So the
plan to use this market as a substrate for smarter agents has a
condition attached: either the internal agents' losses must be
replenished (retire the bankrupt, admit fresh participants), or the
predictability must be priced in as the cost of the liquidity the
substrate provides. That decision — not more simulation — is the next
step.

## Where this leaves the project

The mindless market is a good shock absorber: deep, almost always
quoted on both sides, self-damping, and hard to get stuck when its
participants are varied. It is NOT a copy of real markets — it is
calmer, and exploitably so. For its intended role — the always-humming
internal engine that smarter agents will one day trade against — that
may be exactly right: let the substrate be simple and absorbing, and
let realism emerge from the smart agents plugged into it. Then anything
the composite market does that this null does not is, by construction,
the measurable contribution of intelligence.

---

# EVALUATION of the seed battery (five runs of 15,000 agents)

The same big, varied market (all four dials normal, 7,500 agents per
side, 400,000 ticks) was then run with five different random seeds.
Five is a small number, but it is enough to answer the questions the
first big runs raised — and to correct two things we had said.

## 1. Chaotic in detail, lawful in shape

The model is as path-dependent as a system can be. We ran one world
twice with only a single floating-point bit of difference between them
(the last digit of one order's size): the two runs are identical for
eleven ticks and then part ways for good. Every run is a separate,
unrepeatable history — the textbook signature of chaos.

And yet the five runs rhyme. Each traces the same kind of arc: a long
excursion away from the starting price — up or down — followed by a
pull back toward it, with the return often arriving late. The reason
is a genuine restoring force: the further the price travels, the
thinner the book becomes in the units that matter for the trip back
(at low prices the resting euros lift many coins; at high prices the
resting coins absorb many euros), so returning is always cheaper than
continuing. Which way any run goes, and how far, is a coin toss; that
it eventually turns is physics. Like weather: no two days alike, all of
them seasons.

## 2. Direction is symmetric — measured, then proven

The first big runs all happened to end up. Five seeds later the tally is
three up, one flat (a 70% fall and a full recovery to the start), and
one down — and archived scans of the same world at small size split
eight up to nine down over seventeen runs. The bit-level test settled
it: the rules treat the two sides as exact mirror images; only the
floating-point arithmetic differs in the last digit, and that has no
direction. The similarity you see across runs is the arc, not a hidden
tilt.

Two corrections on record. Earlier we suggested big runs were
"compressed" into a narrow range of outcomes; five seeds show
excursions vary widely — one run fell 95% — so that was three-sample
luck. And we had counted the returning "late rally" as a systematic
event; it is systematic only as a return, and only when the prior
excursion went down.

## 3. A market can survive a 95% crash without stopping

One seed rose to 264 and then fell, over 200,000 ticks, to 9 — a 95%
drawdown. It never stopped. Trading continued at the same rate as
before, both sides were still quoted most of the time, the spread
stayed tight, and in the final stretch the price bounced 35% off its
low: the restoring force engaging. It was the most volatile phase of
any run, not the quietest. A dead market pins; this one thrashed and
turned. In this model, size plus variety buys resilience even to a
near-total collapse.

## 4. Nobody ever goes broke — the market dies of exclusion, not
## bankruptcy

The engine has a bankruptcy rule. Across every archived run — well over
a hundred — it has never fired: not one agent has gone broke, ever.
Sizing is a fixed fraction of wealth, so losses shrink with the loser
and never reach zero. What actually happens to a heavy loser is that
its wealth falls below the smallest tradable order and it can no longer
participate: alive, but excluded. This is the individual's view of the
"shrinking market" finding above, and it changes the design of any
recycling mechanism: there is no corpse to replace. The right rule is to
retire the poorest participant and seed a fresh one — and the right
health measure is not "how many are alive" (always all) but "how many
can still place an order."

## 5. The book shows its moves coming — the bow-wave

With the order book recorded every few ticks (new in this batch), the
depth chart revealed something the price alone never could. Depth is
almost never on both sides at once: there is a mountain on one side, and
it sits on the side the price is moving TOWARD. The mechanism is the
model's deepest result made visible. When the price rises, everyone who
bought on the way up parks a take-profit one band above their entry —
so an advance continuously lays a wall of its own profit-taking just
ahead of itself, and then climbs by eating it. Reverse the move and the
wall flips sides within a few dozen ticks. A market that builds its own
resistance out of its participants' optimism, one band ahead, is why
moves fizzle, why the market damps itself, and where the fizzle-bet's
profit comes from — all in one picture.

## 6. Two things the eye gets wrong about depth

First, resting volume measured in coins rises as the price falls and
falls as it rises — not because liquidity drains, but because the same
euros buy fewer coins at a higher price. Measured in value, the book's
resting capital stays roughly constant through a threefold price swing.
Second, a bigger crowd does not make a heavier book: total capital is
fixed, so more agents just slice the same wall into more, smaller
orders. More agents buy quality (tighter spread, smoother trading,
more continuous quoting); only more capital buys the ability to absorb
big orders. For a real venue that is a convenient separation: the
quality is already demonstrated; the capacity is a funding decision.
