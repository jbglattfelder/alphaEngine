# The Alpha Engine — Master Handoff

The single authoritative state record. Absorbs the former `CLAUDE.md`,
`DIRECTION.md`, `REFERENCE.md`, `HANDOFF.md`, `HANDOFF-v4.md`, `HANDOFF_clob.md`,
and the two `HANDOFF_stranding` docs. Measured results and their retractions are
filed at equal weight. **Almost every number here is 1–3 seeds: direction and
order of magnitude, not levels, unless it says otherwise.**

Companion: `FINDINGS-master.md` (the detailed experiment records). Read this for
state and orientation; read that for the tables.

---

## 0. The verdict

**Level 0 (the closed mechanism) is closed** — not because everything is
explained, but because the null model has done its job: it now says, with a
mechanism attached, exactly which market phenomena *require* level 1.

Scorecard of the bare mechanism:

| Stylized fact | Result |
|---|---|
| Unpredictability, ACF(r) ≈ 0 | **PASS** (n=500: +0.01) — for the opposite reason to a real market |
| DC count N(δ) ~ δ⁻² | **PASS** at n=150 across seeds/engines/sl; **moves at n=500** (§4.3) |
| Volatility clustering (physical time) | **FAIL** — but see the intrinsic-time duration result (§5.2) |
| Fat tails | **FAIL under homogeneous bands — reachable at "level 0.5"** (§5.1) |
| ⟨ω⟩ = δ (overshoot law) | **FAIL** — not even a power law; needs the actor |

The unpredictability pass carries an asterisk: a real market is unpredictable
because information is incorporated and arbitrage scrubs the residue; ours is
unpredictable because **there is nothing to predict**. The engine achieves *the
signature of efficiency without the mechanism of efficiency*.

**Five independent arguments now converge on one conclusion — what is missing is
not a parameter, it is an actor:**

1. Fat tails need a mixture of depth scales (§5.1) — geometry, not a knob.
2. ⟨ω⟩=δ needs depth that survives a price move (§4.4).
3. A pure CLOB cannot form a price with taker-only agents — no spread (§4.6).
4. A pure CLOB deadlocks two ways; only a both-sides maker fixes the "side" half
   (§4.7).
5. The overshoot law's remnant dies under every depth *geometry* tried (§5.1).

> **The one-sentence root cause.** *In this market, liquidity is other agents'
> unrealized profit.* Every resting order is a take-profit; a take-profit exists
> only because someone holds an open position; depth is destroyed by the move
> that would resist it and replaced only by new positioning. There is nobody
> whose willingness to quote survives a price move. The fix is a two-sided
> quoter (Avellaneda–Stoikov), not more tuning — see §7.

---

## 1. What the model is

A closed two-currency market (EUR / BTC), simulated bottom-up. `n` "longs" and
`n` "shorts"; an agent's side is fixed for life. Longs hold mostly EUR, shorts
mostly BTC; both hold both. No external price feed, no external money — **the
price is whatever the trades produce.** Money is conserved exactly and PnL sums
to zero, asserted every tick.

- **Capital.** Pareto-drawn, rescaled so the agent total is exactly `K` (1,000,000
  EUR). The house holds a separate reserve (§6).
- **Clock.** Pressure accrues each tick while an agent is flat; at a
  capital-scaled threshold `d` the agent opens one position (period `d/c`). It
  cannot open another while holding one. With `hold_fires_close=True` the clock
  *also* runs while holding, and a fire-while-in-position is an exit at market
  (the "impatience" mechanism, §4.7).
- **Exits.** Every position has a take-profit and a stop-loss. **The TP rests in
  the book as a passive limit; the SL fires as a market order** when touched.
- **The venue.** A central limit order book (`book.py`). It matches; it never
  takes a position (except the optional house maker, §6/§7).

### The three mechanisms, and why the split is forced

There are only three: agents **open**, **take profit**, **stop out**. By *role*:

- **Aggressive flow** = the entry imbalance + SL covers (market orders).
- **Passive depth** = **TP limits, and nothing else.**

The split is geometry, not choice. A TP is an order to exit at a *better* price
than the market (sell higher than you bought, or buy lower than you sold) —
nobody will give you that yet, so it rests. An SL exits at a *worse* price —
everyone takes it instantly, so it cannot rest; it must be a conditional trigger
firing a market order. Tribe-symmetric: a long's TP rests as an **ask** above, a
short's TP rests as a **bid** below; both SLs are immediately marketable. Price
*level* is a red herring — *direction* is the whole of it. Consequence: **the
book can only ever hold winning positions.** (This is a property of a *CLOB*; in
wholesale FX both order types are conditional market orders given to a dealer, so
the feedback *sign* transfers but the liquidity consequence does not.)

### The tick loop (ioc/batch default)

pressure → rest TPs / arm SLs → check SL triggers → gather entries → **entry
auction** (balanced flow nets at `p_prev`, impact-free; only the *net* imbalance
walks the book) → settle → bankruptcy → record. Conservation and zero-sum are
asserted each tick. Runs are bit-identical across machines (the capital draw uses
`decimal` + `math.fsum`; the model is chaotic — one bit rewrites a run).

---

## 2. Module map & working rules

| Module | Owns |
|---|---|
| `config.py` | All parameters + switches (single source of truth) |
| `agents.py` | Agent + Population: capital draw, pressure, firing, sizing; House lives here by co-location (§6) |
| `book.py` | **The CLOB**: resting limits, price-time-priority matching, the emergent price |
| `position.py` | Balance-sheet PnL (Glattfelder & Houweling 2024, arXiv:2411.14068) |
| `simulation.py` | The tick loop; wires modules; records series |
| `analysis.py` | Recorder, Analyser: dashboard + automated sanity checks |
| `dc_analysis.py` | Intrinsic-time DC/overshoot instrument + BM-validated volatility/liquidity bridge |
| `main.py` | Entry point |
| `market.py` | **RETIRED.** The Dutch-auction era. Nothing imports it; it warns on import. Read `book.py` for the live mechanism. |

Rules: change parameters in `config.py` only; dependency direction
`config <- agents <- book <- simulation`; the book returns `Fill`s and the
simulation applies them; matplotlib is imported lazily so core mechanics stay
plot-free.

---

## 3. The engine switches (what each knob selects)

Every switch below decides *which model you are running*. `Config.summary()`
prints the resolved set on every run — **check the run header names your arm.**

- **`close_mode`** — what an exit *promises*. `"home"` (default): each tribe
  delivers what it holds (symmetric toy; the defensible null). `"quantity"`: each
  tribe re-trades a fixed BTC quantity (realistic; produces stranding, squeezes,
  cover-driven drift — the treatment). *Do not delete quantity* (§4.5/§8).
- **`sl_mode`** — SL execution discipline. `"market"` (default), `"wait"`,
  `"limit"`. The stranding-fix arm (§8). `close_mode="home"` requires
  `sl_mode="market"`.
- **`entry_mode`** — how entries meet the market. `"ioc"` (default): the hybrid
  batch-auction-plus-CLOB (balanced flow nets at `p_prev`, imbalance walks the
  book). `"batch"`: alias of the same netting. `"rest"`: the **pure CLOB** —
  entries are marketable-to-touch resting limits, no self-cross (§4.6/§4.7).
- **`hold_fires_close`** — impatience. Default **True**: the clock runs while
  holding and a fire-in-position exits at market. Required to keep
  `entry_mode="rest"` alive (§4.7). *This default has silently flipped and cost
  debugging four times — the run header now names it.*
- **`x_accounting`** (default True) — size/PnL/exits in geometric-mean units
  `X` (`1 X = p^-½ EUR = p^½ BTC`); order size `(W_X/q)/√p`, identical both
  tribes. Kills drift and mark-to-market transfer artifacts.
- **`log_thresholds`** (default True) — log-symmetric bands `x·e^{±tp}`. Kills the
  percentage-gauge round-trip drift (see the standalone note, §9).
- **`symmetric_solvency`** (default True) — clamp SELLs by BTC held, mirroring the
  EUR clamp on BUYs.
- **`sl_grid`** (default 0) — snap SL triggers to a shared log grid (Osler
  clustering probe; floor/ceil snap, freeze bug documented in code).
- **`house_reserve_frac`** (0.1), **`house_bailout`** (False) — §6.

---

## 4. What is measured (the price process)

Engine defaults unless noted: `x_accounting=True`, `log_thresholds=True`,
`symmetric_solvency=True`, `close_mode="home"`, `f=0.5`, `c=0.004`. All runs pass
conservation + solvency unless stated.

### 4.1 The lattice — SOLID (8× tp range, all n)

The price is a **lattice walk whose spacing is `tp`**: `sd(r) = 0.78·tp` and
`median|log-step| = tp` **exactly** across tp ∈ {0.005…0.04}. Fraction landing
on one band: n=2 → 98.7%, n=150 → 48.7% (the mode never leaves the band). A δ
grid pinned to tick-sd holds δ/tp fixed, so **any tp-sweep is confounded three
ways** (lattice, volatility, excursion) unless `tp·√T` is held constant.

### 4.2 `q`, continuation probability — the exit mix, scale-dependent

`q` = fraction of steps continuing direction (BM = 0.5 at all scales). Measured
n=150: q(m=1) ≈ 0.70, decaying to ≈ 0.46 by m≈32. **SLs are the momentum**
(`sl_enabled=False` → q=0.516, BM-like); tightening sl raises q, widening lowers
it — monotone, brackets 0.5. **But q=0.5 is not tunable in any transferable way**:
`sl=2·tp` fixes n=150 and over-corrects at n=500 (momentum already diluted by
m=2). q is a function of scale *and* n, and — critically — **path-conditional**:
a trending run shows elevated q at every scale (FINDINGS §1). The single-seed q
table's *levels* are therefore entangled with realized drift; the qualitative
claims are safe. n_open (= n·c·holding-time) sets the momentum's *decay length*,
not its *tick-level strength*, which floors at ~0.65–0.69 and never reaches 0.5.

### 4.3 DC count N(δ) ~ δ⁻² — SOLID at n=150, MOVES at n=500

n=150: E_N ≈ −2 ± 0.2 across seven configurations (both engines, both sl, seeds
1–3). **At n=500/T=100k, `close_mode` moves it**: quantity → −2.709, home →
−1.805, *same n/T/seed/tp/sl*. Partly explained by §4.5 (the quantity arm is
tethered, so it has fewer large excursions to count); the n-dependence itself is
**UNEXPLAINED**. Do not state "DCs are stable" without this caveat.

### 4.4 Overshoot law ⟨ω⟩ = δ — DOES NOT HOLD, and is not a power law

**Retire every E_os number.** ⟨ω⟩(δ) is non-monotone (quantity arm R²=0.041 — a
line fitted to a hump). The instrument is not at fault (BM 12-seed: E_os = 1.005
± 0.056). What governs the *level* is q at the δ scale (§4.2). The apparent
"hump" may be substantially noise at large δ (rise rests on 12–24 events);
re-measure with enough events before treating the peak as real. A finite-range
explanation was tested and does **not** hold (max usable δ is 14% of the range).

### 4.5 Compact support & the quantity-arm tether

**Fat tails are structurally absent under homogeneous bands.** Measured:
`P(|r|>4sd) = exactly zero`, `|step|>2·tp` = 0.0–0.2% at every inventory level,
c, and n. Because agents enter at the current price, TPs always rest one band
away — the price is permanently walled in, so **the engine makes excursions but
never jumps** (the home-arm runaway travels ~14 e-folds in thousands of tp-sized
steps). This does **not** explain the overshoot law: the home arm has compact
support *and* ⟨ω⟩/δ = 3.3e6 in the same run. Tails = single-step size;
overshoots = runs of steps. Separate questions. *(Broken at level 0.5 — §5.1.)*

**The quantity arm is tethered** (sub-diffusive, not confined — corrected from an
earlier single-seed "range-invariant" claim): its price range grows ~1.2× for 4×
the horizon vs ~2× for a free walk, because stranded shorts' forced covers are
the only counter-flow, hence the only anchor. The home arm has no such channel
and diffuses freely. This unifies "recycling keeps the price bounded" and "the
drift is the cover mechanics": the cover flow is what pins the level.

### 4.6 The batch auction is the price-formation mechanism, not a scaffold

~47% of entry flow self-crosses at `p_prev` and never touches the book; only the
net imbalance moves the price. **This is not onboarding — it is load-bearing every
tick.** Tested by removing it: a pure CLOB with entries resting at `p_prev` pins
the price (every entry wants the same price → instant cross → no spread → no
discovery); a batch-seeded ladder handed to a marketable pure CLOB **freezes
within a few ticks** (gross flow walks both sides, consumes depth faster than
recycling replaces it: 0 nonzero steps vs 1879 in the control). A GRW feed cannot
replace the auction, because what needs replacing is the *per-tick netting into
imbalance*, not the initial prices (x_0 already bootstraps the closed market).
The only thing that lets you drop the auction and stay closed is a two-sided
quoter (§7).

### 4.7 The pure CLOB (`entry_mode="rest"`) — two ways a market dies

Entries as marketable-to-touch resting limits, cancel-and-replace on re-fire.
**Entry-at-last is a fixed point** (maximally-passive quoting kills price
formation outright; marketable-to-touch is the minimal parameter-free aggression
that keeps it alive). Two absorbing classes:

- **Class 1 — taker starvation (all-holding).** When every agent holds, all
  orders are passive exits; the only takers (new entries, triggered SLs) need a
  resource the state has exhausted (a flat agent / a price move). n=500 froze by
  tick ~1,000. The ioc hybrid survives only because *IOC failure was the taker
  supply* — discarded entries return agents to flat. **Impatience**
  (`hold_fires_close`) kills Class 1 at every n (a stale position is always a
  mintable taker).
- **Class 2 — counterparty starvation (same-side desire).** Rigid tribes align:
  at n=2 the market died in the state {2 shorts holding→BUY, 2 longs flat→BUY} —
  four buyers, zero sellers, forever. **No within-population rule fixes this**;
  aggression needs an opposite resting order. Combinatorially negligible at
  n=150, guaranteed at small n.

**The liveness statement.** Impatience buys unconditional *timing* but not
unconditional *side*. Class 2 is provably fixable only by a participant always on
both sides regardless of its own state — the house maker (§7). *Someone must act
unconditionally on market state; impatience distributes the timing half into the
population, only the maker supplies the side half.*

**The relaxation oscillator (n=500, impatience).** The system *orbits* the
Class-1 attractor instead of falling in: flat pool drains toward all-holding
(depth ~580), takers thin, price drifts one-way, stale clocks flush en masse,
pool refills — endogenous boom-flush cycle, period ~11k ticks, in nothing in the
inputs. Best liquidity venue of any arm measured (86.6% two-sided vs the hybrid's
13.9%). Carries a persistent **downward inter-cycle ratchet** — a new convention
tilt, presumably the marketable-to-touch asymmetry; UNMEASURED. The registered
next test (`exp_oscillator_phase.py`) splits DC events by cycle phase; prediction:
the super-linear overshoot concentrates in the *flush* phase, build is near-BM.

### 4.8 The n=2 limit — the mechanism naked

`n=2, home, c=0.004, tp=sl=0.01, seed 1, T=100k` → p_final = 8.678493, 329 clears
(bit-reproducible fixture). 84.5% up-steps; sum of log-steps = ln p_final exactly;
the two longs ratchet the price up by serially filling each other's TPs. Closes
the population sweep: n=2 → 84.5%-up ratchet, n=150 → ACF(r)=+0.17, n=500 → ~0.01.
**Symmetry is a large-n property, not a property of the mechanism** — the "5:1
tribe asymmetry at n=2" is the same "symmetric" home engine. State symmetry as a
large-n claim wherever it appears.

---

## 5. Level-0.5 and the intrinsic-time laws (from FINDINGS-master)

### 5.1 TP roundness hierarchy breaks compact support — the first fat tails

Clustering *take-profits* (not stops) onto a per-agent roundness hierarchy (Osler
2003: 00 beats 50) produces **P(|r|>4sd) = 2.1–2.2%** (vs Gaussian 0.006% and
§4.5's exact zero), replicated on two seeds. Controls exclude both fakes: a
band-matched wide uniform band keeps the tail at exactly zero (it just
re-lattices), and *any single grid* (even k=1, 100% multi-band) has zero tail.
**Fat tails are a property of the mixture of depth scales, not of any grid.**
Cost: the hierarchy damages the overshoot remnant worst of all arms (0.47) —
confirming §0, no depth *geometry* substitutes for the actor. So §0's "fat tails
unreachable" is now conditional: unreachable under homogeneous bands, reachable
at **level 0.5 — agents with round fingers** (a cognitive quirk, no strategy, no
actor). Caveats: 2 seeds; the k=1 subpopulation carries residual band inflation;
confound-free rerun (drop k=1, pre-compensate the snap) + ≥10 seeds before the
scorecard edit is load-bearing.

### 5.2 Durations are fatter-tailed than BM — intrinsic-time clustering

Registered prediction (durations thinner than BM) **FALSIFIED at δ=32·sd**: engine
CV 2.27 vs BM 0.81, one traversal 27× the median. The threshold clock does *not*
regularise waiting times. Conjecture: the engine mixes ratchet-fast and
range-bound traversal regimes; a fast/slow mixture *is* heavy-tailed durations.
The reframe: **duration mixing at large δ is what volatility clustering looks
like in intrinsic time** — a seed of temporal clustering the physical-time ACF(|r|)
cannot see, softening one scorecard FAIL. Caveats: 42-vs-14 events at the
interesting δ, single seed, feed drifted; ≥10 seeds + drift-stratified control
before leaning on it.

### 5.3 The instrument

`dc_analysis.py` = Glattfelder–Dupuis–Olsen (arXiv:0809.1040) algorithm 2 +
overshoot dissection + Glattfelder–Golub (arXiv:2204.02682) volatility/liquidity
bridge. **BM-validated:** bridge C^T=3.98e-6, C^τ=4.08e-6 vs σ²=4e-6 (2%);
⟨ω⟩/δ=1.003. Load-bearing gotchas: (1) ⟨·⟩₂ is *mean-square* (2204) not
quadratic-mean (0809) for the bridge — do not "fix" it; (2) δ floor ≥ 8× tick-sd
(discretization bias, measured); (3) **gauge="log" is the default** (scale-
covariant), "relative" reproduces the papers — the log gauge does *not* fix the
runaway, it makes 3.3e6 legible as ~100; (4) **kurtosis is the wrong instrument
for tails** — it conflated peakedness with tail weight and said "fat tails" while
the tail was exactly zero. Measure P(|r|>k·sd) directly.

---

## 6. The house

Not an Agent (doesn't subclass, fire, or take positions). Lives in `agents.py` by
co-location (it needs `Position` + wallet fields). Seeded with
`house_reserve_frac·K` (default 0.1) split **50/50 EUR/BTC at x_0**, so its value
is exactly `frac·K` at t=0 — currency-neutral so it can rescue either tribe. Three
roles, ascending activity, only the first live by default: (1) owns the CLOB
(passive, definitional); (2) conservation anchor — `system_x0` sums agents *plus*
house, so total money is `agents + house` (this is why the ~1.1M-vs-1M is not a
bug: every scientific quantity pairs an agents-only baseline with an agents-only
measurement, or agents+house with agents+house — the only blemish is
`tol_x = 1e-9·K` applied to the 1.1M `system_x0`, cosmetic); (3) bailout maker
(`house_bailout`, default off). **The house is the seat for the level-1 A–S
actor** (§7): its reserve becomes the maker's inventory, the 50/50 split its
neutral target. Clean refactor pending: pull it into `house.py` parallel to
`book.py`.

---

## 7. Direction — where this goes, and why

**Product goal:** an internal, reactive market that supplies price and liquidity
to external traders. **Scientific goal that gates it:** a market whose every
behaviour is derived-or-bounded, so that when external intelligence couples to
it, anything new is *attributable*. The null is the control experiment for the
whole program; level 0 must close before level 1 opens, or every level-1 result
is confounded. **It is now closed** (§0).

**Level 1 is an actor, not a parameter** — five independent arguments (§0) point
at the same missing piece: a two-sided quoter resting depth *away from* `p_prev`,
independent of its own P&L.

- **Use Avellaneda–Stoikov (2008), not Glosten–Milgrom.** GM needs a fundamental
  value V and Bayesian learning; we have no V (closed market → "informed" is
  meaningless; GM at μ=0 gives a *constant* price, ours moves mechanically). A–S
  quotes around an inventory-skewed reservation price and needs no V. The house
  is its seat (§6).
- **What GM still buys:** the martingale-by-construction theorem (why q-tuning was
  doomed); a named precedent for market breakdown (rhymes with the CLOB's
  absorbing classes, §4.7); and the reframe that *in a market with no fundamental,
  information is about positioning, not value* — an agent who knew where the TPs
  and SLs sat could predict the cascades (stop-hunting). Round-number clustering
  (§5.1) is what makes positioning inferable — closing the loop with level 0.5.
- **The registered level-1 build:** A–S quotes from house inventory; a **GRW
  zero-feedback control arm** (the null feed — structureless, so any emergent
  structure is the mechanism talking); pre-registered falsifiers, checkable at
  n=2 in seconds: **⟨ω⟩/δ → 1** and **both absorbing classes become impossible**.
  Level 1's comparison gains a third arm: null / impatience-CLOB / maker-CLOB, and
  "what unconditional liquidity is worth" splits into a *timing* component
  (impatience) and a *side* component (only the maker).
- **On the GRW as an external feed** (distinct from the control arm): couple via
  *arbitrage* (self-funding, tracking emerges) not *imposed reversion* (a
  restoring force — rule-5 violation); work in log (`log(p_int/p_ext)` is
  covariant); study the **residual** `log p_int − log p_ext`. This opens the
  market — a different research object — and belongs *after* the internal quoter,
  so endogenous price formation is separable from an imported one.

**Then:** heterogeneity where "fundamentals" enter (endogenous only — rule 5),
evolution as the organizing principle (differential fitness breaks symmetry
honestly; expect the level-0 lesson to recur — every fitness/imitation/mutation
kernel is a convention that tilts something; measure the tilt, don't hunt for the
neutral one), and a red-team adversary that tries to drain the book before any
real external couples.

---

## 8. The stranding thread (`close_mode="quantity"`) — resolved, retained as treatment

The full record is in `FINDINGS-master.md` §S. Summary of the resolved state:

- **The phenomenon:** under quantity-close, shorts strand in un-closeable open
  positions ~20–50:1 vs longs. **Cause (P1/P2 confirmed, 10 seeds):** a short
  covers by *buying* BTC, clamped by EUR it may lack; a long covers by *selling*
  BTC it always holds. Symmetric clamps, asymmetric bite. 0/193 stuck shorts could
  afford their cover.
- **Bug or feature:** the *constraint* is a real feature of margin-free spot
  shorting; the *absorbing* (never-recovers) character is a separable rule choice
  — the "market-buy with your whole EUR balance every tick" spend policy burns EUR
  to zero at the worst prices. `stuck_short` never decrements in 10×40k ticks.
- **The impossibility triangle (sl_mode arms):** forced execution / spend-
  boundedness / tribe symmetry — pick two. `market` picks 1+solvency, gives up
  symmetry; `limit` picks 2+3, gives up forced execution (agents park, tribes lock
  150/150); `nosl` gives up forced exits and is dominated. The missing corner
  needs an external balance sheet — the §7 maker.
- **V4 resolution:** `close_mode="home"` (deliver what you hold) removes the
  forced-loss channel → stranding gone, drift dead, x-share = 0.50008 ± 0.00027.
  This is the symmetric null; quantity is the **treatment** for squeezes/stranding/
  cover-drift. **Do not delete quantity** — the runaway (§4.5) was only detectable
  because the quantity arm existed to compare against.

---

## 9. Retractions and standing rules

### The retraction ledger (every false headline was caught by measurement, not reasoning)

Wealth concentration (a moving-ruler bug, 100× the real effect); Pareto-tail
liquidity (min-statistic clock); PnL normality (single-seed kurtosis); volume
collapse (EUR-denominated volume); longs systematically profit (seed 42, reversed
across 20); the arithmetic TP/SL gauge as the side asymmetry (falsified same
session); symmetric_sizing symmetrizes drift (detonates); cap-freeze prices out a
tribe (saturates in its own currency, swap-symmetric); PnL=0 clustering is a
freeze (EUR lens, swap-covariant); heterogeneous tp restores scale-freeness
(worse); sl=2·tp gives q=0.5 (n-dependent); the gauge manufactures the 10⁶
overshoot (real, not gauge); close_mode not the cause of E_N=−2.709 (wrong,
retracted); tails inventory-limited (peakedness, not tails — the metric said yes
before the phenomenon said no); the overshoot hump is a finite-range artifact
(unsupported); compact support explains the overshoot law (no); durations thinner
than BM (falsified, and the yield); quantity-arm range T-invariant (single-seed;
sub-diffusive, not confined). **All E_os values retired.**

### Standing rules (do not re-break)

- **The three-mechanism inventory is the frame.** The only passive depth is TP
  limits; any new mechanism changes what liquidity *is* — say so.
- **Read wealth/transfer in X, never EUR.** The EUR PnL panel is a moving ruler;
  the geometric-mean share is the covariant measure.
- **Measure in logs, not relative returns**, anywhere the price spans e-folds.
- **Never quote an E_os** (not a power law). **Never use kurtosis for tails**
  (measure P(|r|>k·sd)). **Validate any new instrument on BM first.**
- **Never `rng.pareto()`/`np.sum()` in the capital draw** (`decimal`+`fsum`; the
  model is chaotic). **Never define the firing threshold against min capital**
  (use the mean, fixed at K/(2n)). **Never add a restoring force to a fixed price
  level** (privileges a numeraire — rule 5). **Never read EUR volume as activity.**
  **Never scale-compare trajectories across non-power-of-two x_0; never
  reintroduce absolute dust thresholds** (scale by 1/x_0).
- **A block that lies about what ran is the worst bug class here** — every knob in
  an edit block must be passed; every run must print the switches it used
  (`cfg.summary()`). Four silent-default incidents to date.
- **Distributions across ≥10 seeds before any number is load-bearing.** Almost
  everything here is 1–3 seeds. **Symmetry is a large-n claim.** **Do not
  generalise a null result from a regime where the effect cannot appear.**
- **Predictions before runs; retractions at equal weight; instruments committed,
  never monkeypatched.** Documentation is part of the mechanism — a stale docstring
  is a bug that bites the next reader, who may be a machine that believes it.

---

## 10. Reproducibility — bit-check targets

**RE-BASELINED 2026-07-15** on `close_mode="home"`. The old quantity-path table is
retired (quantity remains as the named treatment).
Config per row: `Config(f=<f>, c=0.004, T=6000, seed=<seed>, x_accounting=True,
log_thresholds=True, symmetric_solvency=True)` (close_mode defaults "home").

| f | seed | p_final (full precision) | drift ln(p/x0) | long X-share |
|---|------|--------------------------|----------------|--------------|
| 0.3 | 1 | 3.4145279771117274e-08 | -17.192641 | 0.300000 |
| 0.3 | 2 | 1.5113000739620497 | +0.412970 | 0.540717 |
| 0.3 | 3 | 5.686853241735516 | +1.738157 | 0.640346 |
| 0.3 | 4 | 2.974382857270011e-06 | -12.725474 | 0.300001 |
| 0.5 | 1 | 0.0005895985292513698 | -7.436069 | 0.500008 |
| 0.5 | 2 | 0.08331088641502116 | -2.485176 | 0.500246 |
| 0.5 | 3 | 0.4245626718502022 | -0.856696 | 0.500135 |
| 0.5 | 4 | 2.0215660542334306→ see note | — | 0.507612 |
| 1.0 | 1 | 3.982355415776321e-06 | -12.433637 | 0.999996 |
| 1.0 | 2 | 0.22081746589221038 | -1.510419 | 0.819204 |
| 1.0 | 3 | 3.827259569156836e-09 | -19.381117 | 1.000000 |
| 1.0 | 4 | 2.117962981573481e-08 | -17.670226 | 1.000000 |

*(f=0.5/seed4 row: regenerate to refresh; the home re-baseline value supersedes
any quantity-path number. The x-share ≈ 0.50 band at f=0.5 is the load-bearing
signal — drift is a free zero-mode and varies wildly by seed, as the spread of
the drift column shows.)*

Bit-reproducibility guards: `test_benchmarks.py` / `benchmarks.json` (eight+
engine paths, bit-exact; ioc/batch bit-identical through refreezes), portable-init
test, BM-control test. `.json`/`.jsonl` files are **run artifacts**, not sources
of truth — parameters live in `config.py`.
