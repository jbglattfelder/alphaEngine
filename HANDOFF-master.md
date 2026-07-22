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

> **THERE ARE TWO DEFAULT-ISH ARMS, AND MOST CLAIMS ARE ARM-CONDITIONAL.**
> `config.py` defaults `entry_mode="ioc"` (the batch hybrid), but **`run_single.py`
> ships `entry_mode="rest"` + `hold_fires_close=True`** — the pure-CLOB impatience
> engine — at **n=500, tp=0.01, sl=0.02**. So the dashboard a person sees by
> default is the CLOB arm, *not* the batch arm the older prose describes. Every
> scorecard row below now names which arm it holds on. The two arms differ on the
> headline results (compact support, fat tails, the price's stability), so
> "the null model does X" is ambiguous until the arm is stated.

Scorecard of the bare mechanism (**batch** = ioc/home; **CLOB** = rest+impatience):

| Stylized fact | Result |
|---|---|
| Unpredictability, ACF(r) ≈ 0 | **PASS** (n=500: +0.01) — for the opposite reason to a real market |
| DC count N(δ) ~ δ⁻² | **batch n=150: E_N ≈ −2**; **CLOB default: E_N ≈ −1.6, NOT −2** (§4.3); moves with n/close_mode |
| Volatility clustering (physical time) | **FAIL** — but see the intrinsic-time duration result (§5.2) |
| Fat tails (**batch**) | **absent** — P(\|r\|>4sd)=0 exactly (§4.5) |
| Fat tails (**CLOB, default**) | **PRESENT** — genuine, drift-independent, 2 seeds: P(\|r\|>4sd) ≈ 0.5% (sl=tp) to 1.2% (sl=2tp) (§5.4) |
| Fat tails (**batch + level-0.5 roundness**) | **PRESENT** — P(\|r\|>4sd) ≈ 2.1% (§5.1) |
| ⟨ω⟩ = δ (overshoot law) | **FAIL as a mean** (mean is drift-inflated); **median-ω/δ ≈ 0.7 ≈ BM** on both arms (§4.4) |
| Price direction (**CLOB**) | **UNSTABLE** — symmetry-breaking, not a drift; runs away up *or* down, direction noise-seeded (§4.9) |

The unpredictability pass carries an asterisk: a real market is unpredictable
because information is incorporated and arbitrage scrubs the residue; ours is
unpredictable because **there is nothing to predict**. The engine achieves *the
signature of efficiency without the mechanism of efficiency*.

**Four independent arguments converge on one conclusion — what is missing is not a
parameter, it is an actor:**

1. ⟨ω⟩=δ (as a mean law) needs depth that survives a price move (§4.4).
2. A pure CLOB cannot form a price with taker-only agents — no spread (§4.6).
3. A pure CLOB deadlocks two ways; only a both-sides maker fixes the "side" half,
   and the price is directionally *unstable* — nothing pins it (§4.7, §4.9).
4. The overshoot law's remnant dies under every depth *geometry* tried (§5.1);
   and no symmetric knob stabilises the price-direction (§4.9, whack-a-mole).

**Fat tails are NO LONGER on this list** — the CLOB arm produces them for free
(§5.4), and the roundness hierarchy produces them at level 0.5 (§5.1). Fat tails
are *reachable* at level 0; they are not evidence for the actor. (This is a
correction: the earlier draft listed "fat tails need a mixture of depth scales"
as an actor-argument. Measurement overturned it.)

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

### The tick loop — two paths, and the shipped default is `rest`

**`rest` (the `run_single` default, pure CLOB):** pressure → rest TPs / arm SLs →
SL closes fire as **market orders walking the book** → firing agents submit
**marketable-to-touch entries** (fill what crosses, rest the remainder;
cancel-and-replace on re-fire) → settle → bankruptcy → record. **No balanced-flow
auction** — entries meet the book directly (`_step_rest`).

**`ioc` (the `config.py` bare default, batch hybrid):** same up to entries, then an
**entry auction** — balanced flow nets at `p_prev` impact-free; only the *net*
imbalance walks the book. **The scaling-law, compact-support, and lattice results
in §4 were mostly measured on THIS arm, not the shipped default** — see the
per-claim arm tags.

Conservation and zero-sum are asserted each tick. Runs are bit-identical across
machines (the capital draw uses `decimal` + `math.fsum`; the model is chaotic —
one bit rewrites a run).

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

### 4.1 The lattice — the MODAL band is tp on both arms; the WALL is batch-only

The price's **modal step is the tp band on both arms**: `sd(r) ≈ 0.78·tp` and
`median|log-step| = tp` **exactly** across tp ∈ {0.005…0.04} (measured, ioc *and*
rest). Fraction landing on one band: n=2 → 98.7%, n=150 → 48.7% (the mode never
leaves the band). **But "the price is walled in at ±2·tp" is a BATCH claim only** —
on the CLOB arm, 5–11% of steps exceed 2·tp (the fat tail, §5.4), so the median is
tp while the tail is heavy. So: lattice *spacing* = tp (general); compact *support*
(no steps past ~2·tp) = batch-only. A δ grid pinned to tick-sd holds δ/tp fixed, so
**any tp-sweep is confounded three ways** (lattice, volatility, excursion) unless
`tp·√T` is held constant.

### 4.2 `q`, continuation probability — the exit mix, scale-dependent

`q` = fraction of steps continuing direction (BM = 0.5 at all scales). Measured
n=150: q(m=1) ≈ 0.70, decaying to ≈ 0.46 by m≈32. **SLs are the momentum**
(`sl_enabled=False` → q≈0.36 at tp=sl=0.01, ioc — *anti*-persistent, not BM-like;
an earlier "0.516" was a different config); tightening sl raises q, widening lowers
it — monotone, brackets 0.5. **But q=0.5 is not tunable in any transferable way**:
`sl=2·tp` fixes n=150 and over-corrects at n=500 (momentum already diluted by
m=2). q is a function of scale *and* n, and — critically — **path-conditional**:
a trending run shows elevated q at every scale (FINDINGS §1). The single-seed q
table's *levels* are therefore entangled with realized drift; the qualitative
claims are safe. n_open (= n·c·holding-time) sets the momentum's *decay length*,
not its *tick-level strength*, which floors at ~0.65–0.69 and never reaches 0.5.

### 4.3 DC count N(δ) ~ δ⁻² — batch n=150 ≈ −2, CLOB default ≈ −1.6

**Batch arm, n=150:** E_N ≈ −2 ± 0.2 across seven configurations (both engines,
both sl, seeds 1–3). **At n=500/T=100k, `close_mode` moves it**: quantity → −2.709,
home → −1.805, *same n/T/seed/tp/sl*.

**CLOB default arm (rest+impatience, n=500, tp=sl=0.01), measured E_N ≈ −1.6**
(−1.606 at sl=tp seed 42; ~−1.66 seen on the default figure) — clearly **not −2**.
So the δ⁻² volatility law is a **batch-n=150 result, not a property of the default
engine.** The DC count on the CLOB arm rises more slowly with δ (the price trends,
so large-δ excursions are over-represented relative to BM). Do **not** state
"N(δ)~δ⁻² holds" for the shipped default; it holds at n=150 batch. The n- and
arm-dependence of E_N is **UNEXPLAINED** beyond "the trending CLOB price
over-counts large excursions."

### 4.4 Overshoot law ⟨ω⟩ = δ — the MEAN is drift-inflated; the MEDIAN ≈ BM

**The mean ⟨ω⟩/δ is not a clean liquidity read on a trending price** — a few long
one-directional runs inflate it. Measured mean/δ ranges from ~1 (batch hump) to 8
(CLOB sl=2tp) to 4.66 to 3.79 across arms/seeds; **none of these are the liquidity
signal.** The tell: on BM, mean/δ ≈ 1.0 but **median/δ ≈ 0.70** (overshoots are
right-skewed even for BM, so mean/median ≈ 1.5 is the healthy baseline). Across
*every* engine arm measured, **median-ω/δ sits at ~0.6–0.9 ≈ the BM value**, while
the mean balloons — i.e. mean/median ≫ 1.5 signals the price TRENDS, not that it
is illiquid. `dc_analysis.measure` now returns `os_median`; `scaling_law.py` plots
both series and prints mean/median. **Use the median; the mean law is a
driftometer.**

Consequences: retire every fitted `E_os` (a slope on a drift-inflated mean means
nothing); the "hump" seen earlier was a mean artifact at δ where events are sparse
(12–24). A clean-looking mean power law (e.g. the sl=tp CLOB run, ⟨ω⟩/δ=1.38
R²=0.996) is *lower-drift*, not necessarily *more BM-like* — check its median. A
finite-range explanation was tested and does **not** hold (max usable δ is 14% of
the range). The **mean** overshoot law is FAIL; the **median** is BM-like on both
arms — the honest statement is "the typical overshoot is normal; the mean reports
the ratchet."

### 4.5 Compact support (BATCH arm only) & the quantity-arm tether

**Compact support is a property of the BATCH (ioc) entry mechanism, NOT of "the
mechanism."** On the batch arm: `P(|r|>4sd) = exactly zero`, `|step|>2·tp` =
0.0–0.2% at every inventory level, c, and n. Because balanced entry flow nets at
`p_prev` and only the imbalance walks the book against TPs one band away, the price
is walled in — **the batch engine makes excursions but never jumps** (the runaway
travels ~14 e-folds in thousands of tp-sized steps). **This breaks on the CLOB
(rest) arm** — marketable-to-touch entries walk the book directly and produce
genuine large steps (§5.4). So "excursions but never jumps" is an **ioc** claim,
now known to be arm-specific.

Compact support (where it holds) does **not** explain the overshoot law: the batch
home arm has compact support *and* a large mean ⟨ω⟩/δ in the same run. Tails =
single-step size; overshoots = runs of steps. Separate questions. *(Broken by
level-0.5 roundness, §5.1; and by the CLOB entry mechanism, §5.4.)*

**The quantity arm is tethered** (sub-diffusive, not confined — corrected from an
earlier single-seed "range-invariant" claim): its price range grows ~1.2× for 4×
the horizon vs ~2× for a free walk, because stranded shorts' forced covers are
the only counter-flow, hence the only anchor. The home arm has no such channel
and diffuses freely. This unifies "recycling keeps the price bounded" and "the
drift is the cover mechanics": the cover flow is what pins the level.

### 4.6 The batch auction is the price-formation mechanism, not a scaffold

~60% of entry BTC flow self-crosses at `p_prev` and never touches the book (measured
n=500 ioc: 61% balanced / 39% imbalance; an earlier "47%" was a different config); only the
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
(bit-reproducible fixture). **REQUIRES `hold_fires_close=False`** — this fixture
was recorded on the pre-impatience engine; under the current default
(`hold_fires_close=True`) the same config gives p_final=0.439. State the flag or
the number is a lie. 84.5% up-steps; sum of log-steps = ln p_final exactly; the
two longs ratchet the price up by serially filling each other's TPs. Closes the
population sweep: n=2 → 84.5%-up ratchet, n=150 → ACF(r)=+0.17, n=500 → ~0.01.
**Symmetry is a large-n property, not a property of the mechanism** — the "5:1
tribe asymmetry at n=2" is the same "symmetric" home engine.

### 4.9 The CLOB price is a SYMMETRY-BREAKING INSTABILITY, not a drift (NEW)

**"Prices always fall" is RETRACTED.** It was a two-seed artifact. Same config
(n=500, tp=0.01, sl=0.02, rest+impatience): seeds 1 and 42 ran *down* (p→0.03),
but another seed ran *up* (p→~10–20, peaking near 20) — all checks pass, all
conserve. **Both directions occur under identical rules, so the direction is not
structural.** The price starts at x_0, wanders quietly, then breaks one way and
runs away — a pencil on its tip. The correct statement: the CLOB price is
**unpinned in level AND unstable in direction** (strictly stronger than the old
zero-mode result), with the direction seeded by early noise and locked in by
feedback.

**The feedback, measured by drift decomposition** (`exp_drift_decomp.py`, which
tags every price-moving order by direction × tribe × role and sums signed Δln p;
attribution is exact — the category sums reconstruct the total ln-drift). Full
150k, seed 42, sl=2tp, the run went down and: by role, **SL covers = −243.5**
(the amplifier), entries a near-perfect wash (+223 gross both sides, net ≈ 0),
impatience +16. Within SL: long-covers (sell) net −307 on 30k events, short-covers
(buy) net +78 on 48k — long-covers hit ~6× harder per event.

**But the asymmetry is EMERGENT, not structural** (the key control, binning
per-event SL impact by time-quarter as the price falls):

| quarter | lnp | Lstop/evt | Sstop/evt | ratio |
|---|---|---|---|---|
| 1 (early) | −1.11 | −0.0067 | +0.0060 | **1.1** |
| 4 (late) | −3.25 | −0.0097 | +0.0024 | **4.1** |

Early, the stops are **symmetric** (ratio 1.1); the 6× asymmetry *grows as the
price falls*. So it is the depth-dies-with-the-move feedback (a falling price thins
the down-side depth, so long-covers walk further, which thins it more), and it
only picks a direction once noise breaks the symmetry. In an up-run the mirror
holds (short-covers become the amplifier; open positions are mostly *shorts*).

**Whack-a-mole (why no symmetric knob restores it):** at sl=tp the SL net *flips
positive* (+16.7) but *impatience* takes over as the down-driver (−21.4) — the
price still runs. The instability regenerates in whatever close-channel is not
pinned, because every close-channel is reactive to the price it moves through.
Restoring symmetry needs *restoring depth* (an unconditional maker), not a knob;
"flipping" needs a designed bias. For a **null** model the finding is that
direction is a free, unstable degree of freedom — not that any direction is
achievable. **Open confirmation: a ≥10-seed sign tally at n=500 to distinguish
pure 5/5 instability from a small residual bias + amplifier.** (Current: down,
down, up on 3 seeds — consistent with ~50/50, underpowered.)

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
the tail was exactly zero. Measure P(|r|>k·sd) directly; (5) **on a trending arm,
P(|r|>k·sd) and constant-mean-detrend BOTH lie** — subtracting a constant from a
trending-then-reverting series manufactures fake persistence (raw q1≈0.47 →
mean-detrended q1≈0.88, an artifact). Use a **local (rolling-median) detrend** and
read the **residual sign-ACF**: q1→~0.5 means the trend is gone; a tail that
survives *that* is real. This is what `exp_detrend_tail.py` does, and it is how
§5.4 was established.

### 5.4 The CLOB entry mechanism is a second route to fat tails (NEW)

The pure-CLOB (rest+impatience) arm has **genuine, drift-independent fat tails** —
a second level-0 route distinct from the level-0.5 roundness hierarchy (§5.1).
`exp_detrend_tail.py`, full 150k, **two seeds each**, local-detrend at windows
25–751:

| arm | seed 1 P(\|r\|>4sd) | seed 42 P(\|r\|>4sd) | residual sign-q1 |
|---|---|---|---|
| CLOB, **sl=2tp** | 1.22–1.26e-2 | 1.26–1.30e-2 | ~0.34–0.36 |
| CLOB, **sl=tp** | 0.43–0.47e-2 | 0.54–0.56e-2 | ~0.42–0.48 |

The tail **survives every local-detrend window** with the residual sign-ACF driven
to ~0.5 (trend removed), and P(|r|>5sd) ≈ P(|r|>4sd) (a genuinely heavy tail, not a
fattened Gaussian) — so it is not the ratchet. Mechanism, partially decomposed:
**the CLOB entry (marketable-to-touch, walking the book) is the baseline (~0.5% at
sl=tp); the sl=2tp cover cascade roughly DOUBLES it (~1.2%).** Both contribute; they
add. Caveat: at sl=tp the tail is mildly window-dependent (falls a little as the
window grows), so ~0.5% is an upper-ish estimate of the truly drift-free tail — the
sl=2tp tail is cleaner (flat across windows).

**Open: the last attribution cell.** ioc × {sl=tp, sl=2tp}. If ioc stays at exactly
zero tail regardless of sl, the tail *requires* the CLOB entry and sl only
amplifies. If ioc at sl=2tp also develops a tail, the wide-stop cascade can make
tails alone. Cheap; run it before the entry-vs-stop split is stated as final.

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

**Level 1 is an actor, not a parameter** — four independent arguments (§0) point
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
sub-diffusive, not confined); **"prices always fall" on the CLOB arm** (two-seed
artifact — an up-run occurs under identical settings; it is a symmetry-breaking
*instability*, not a drift, §4.9); **"SL covers cause a downward drift"** (wrong
framing — the rules are symmetric; the SL feedback only amplifies a noise-seeded
direction, and the asymmetry is emergent not structural, §4.9); **"compact support
is a mechanism property / the engine never jumps"** (batch-only; the CLOB entry
makes genuine fat tails, §5.4); **"fat tails need an actor / are unreachable at
level 0"** (the CLOB arm produces them free, §5.4); **the mean ⟨ω⟩/δ as a liquidity
read** (drift-inflated; use the median, §4.4). **All E_os values retired.**

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

Bit-reproducibility guards: `test_benchmarks.py` / `benchmarks.json` (10
benchmarks, bit-exact — verified green on current code this session; ioc/batch
bit-identical), portable-init test, BM-control test. `.json`/`.jsonl` files are
**run artifacts**, not sources of truth — parameters live in `config.py`.

Instruments added this session (all validated, all committed-clean):
`exp_detrend_tail.py` (drift-vs-fat-tails via local detrend + sign-ACF, §5.4);
`exp_drift_decomp.py` (signed Δln p by aggressor type — who pushes the price, §4.9;
diagnostic wrapper, bit-neutral); `os_median` in `dc_analysis.measure` +
mean/median dual series in `scaling_law.py` (§4.4, drift-robust overshoot read);
`entry_mode` switch in `config.py`/`simulation.py` (batch default bit-identical;
`clob`/`rest` variants — see §4.6/§4.7). Open runs registered against these:
ioc×sl 2×2 tail cell (§5.4), ≥10-seed n=500 sign tally (§4.9),
`exp_oscillator_phase` on the full feed.
