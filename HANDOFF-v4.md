# The Alpha Engine — Handoff v4: the mechanism inventory, the scaling laws, and why level 0 closes

Written as a handoff. Readable by a person or by an LLM picking up the work.
Every claim is either measured or marked unverified. Predictions are stated
before the run that would test them. Distributions, not trajectories.

Scope: what the price process *is*, and what it structurally cannot be. For
stranding read `HANDOFF_stranding-v2.md`; for the broader state `HANDOFF.md`;
for strategy `DIRECTION.md`.

---

## 0. The verdict

**Level 0 closes** — not because everything is explained, but because the null
model has done the only job it was for: it can now say, with a mechanism
attached, exactly which market phenomena *require* level 1.

Scorecard of the mechanism alone:

| Stylized fact | Result |
|---|---|
| Unpredictability, ACF(r) ≈ 0 | **PASS** (n=500: +0.01) — but for the opposite reason to a real market |
| DC count, N(δ) ~ δ⁻² | **PASS** — stable across seeds, engines, sl |
| Volatility clustering | **FAIL** |
| Fat tails | **FAIL — and provably unreachable** (§2.5) |
| ⟨ω⟩ = δ (overshoot law) | **FAIL — unreachable for a different reason** (§2.4) |

The unpredictability pass deserves its asterisk: a real market is unpredictable
because information is incorporated and arbitrage scrubs the residue; ours is
unpredictable because **there is nothing there to predict**. The engine achieves
*the signature of efficiency without the mechanism of efficiency*.

**The two failures are the yield, because they are structural, not parametric,
and they share one root:**

> **In this market, liquidity is other agents' unrealized profit.** Every resting
> order is a take-profit, and a take-profit exists only because someone holds an
> open position. Depth is destroyed by the move that would need to resist it and
> is replaced only by new positioning. There is nobody whose willingness to quote
> survives a price move.
>
> **What is missing is not a parameter. It is an actor.**

Glosten & Milgrom (1985) is the formal statement of why tuning could never have
worked: a real market's martingale is *derived* from a maker pricing to its own
conditional expectation. You install that; you do not balance two mechanical
channels into it. Every attempt this session to tune q to 0.5 was scale- and
n-dependent (§2.2).

---

## 1. The mechanism inventory

Three mechanisms: agents **open**, **take profit**, **stop out**. Nothing else.
Sorted by *role* rather than name:

- **Aggressive flow** — the entry imbalance (the balanced crossing matches long
  buys against short sells at `p_prev` with no impact; only the *net* walks the
  book) plus **SL covers**, which are market orders.
- **Passive depth** — **TP limits, and nothing else.**

**The split is forced by geometry, not chosen.** A TP is an order to exit at a
*better* price than the market (sell higher than you bought, or buy lower than
you sold). Nobody will give you that yet, so it rests. An SL is an order to exit
at a *worse* price (sell lower, buy higher). Everyone will take that instantly,
so it cannot rest — it must be a conditional trigger firing a market order. This
is tribe-symmetric: a long's TP rests as an **ask** at 110, a short's TP rests as
a **bid** at 90; a long's SL (sell at 90) and a short's SL (buy at 110) are both
immediately marketable. Price *level* is the red herring; **direction** is the
whole of it.

So **the book can only ever contain winning positions.** Losing ones are
structurally incapable of resting.

*(Caveat: this is a property of a **CLOB**. In wholesale FX, Osler notes both
stops and take-profits are conditional *market* orders given to a dealer, so her
TPs consume liquidity rather than provide it. The feedback *sign* transfers — it
comes from trade direction relative to the move — but the liquidity consequence
does not. §1 should read "in a CLOB", not as a law of markets.)*

Consequences, each measured below: the tick volatility cannot be anything but the
TP band (§2.1); q is the exit mix, mechanically (§2.2); the step size is capped,
so fat tails are unreachable (§2.5); the forced SL cover is the only counter-flow
and therefore the only anchor (§2.6).

---

## 2. What is measured

Engine: v4 (`close_mode`, `sl_mode`), `x_accounting=True`, `log_thresholds=True`,
`symmetric_solvency=True`, `f=0.5`. All runs pass conservation + solvency unless
noted. **Seeds are 1–3 throughout: direction and order of magnitude only.**

### 2.1 The lattice — SOLID (8× tp range, all n)

`sd(r) = 0.78·tp` and `median|log-step| = tp` **exactly**:

| tp | sd/tp | median\|log-step\|/tp |
|---|---|---|
| 0.005 | 0.794 | **1.000** |
| 0.01 | 0.787 | **1.000** |
| 0.02 | 0.780 | **1.000** |
| 0.04 | 0.762 | **1.000** |

Fraction of steps landing exactly on one band: n=2 → 98.7%, n=20 → 93.4%,
n=150 → 48.7%. The mode never leaves the band at any n.

**Consequence:** a δ grid pinned to tick-sd holds δ/tp fixed, and at fixed T you
cannot move tp without moving the total excursion (ln p ran −2.26 → −18.26 as tp
went 0.005 → 0.04). **Any tp-sweep is confounded three ways.** To separate them,
hold `tp·√T` constant — needing T ≈ 240k at tp=0.01, ~10⁶ at tp=0.005.

### 2.2 `q`, the continuation probability — the exit mix, scale-dependent

q = fraction of price steps continuing the previous direction. BM = 0.5 at every
scale; that *is* scale-freeness. Coarse-graining scale m in ticks, n=150, T=12k:

| config | m=1 | 2 | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|---|
| BM control | 0.496 | 0.484 | 0.494 | 0.471 | 0.500 | 0.485 | 0.581 |
| tp=.01 sl=.01 | **0.701** | 0.642 | 0.604 | 0.552 | 0.507 | 0.448 | 0.462 |
| tp=.01 sl=.02 | 0.518 | 0.484 | 0.450 | 0.474 | 0.467 | 0.505 | 0.435 |
| tp=.01 sl=.04 | 0.424 | 0.436 | 0.443 | 0.413 | 0.440 | 0.381 | 0.473 |
| **n=500** tp=.01 sl=.01 | 0.656 | **0.510** | **0.458** | 0.463 | 0.480 | 0.454 | 0.452 |

- **The engine is persistent at the tick scale** (q=0.70), not anti-persistent.
  Earlier claims of mean-reversion from `ACF|r|` read a statistic diluted by zeros.
- **SLs are the momentum.** `sl_enabled=False` → q=0.516 (BM-like), 0/2649 SL/TP
  exits. Tightening sl raises q (0.703 → 0.779 → 0.800 at sl = .01 → .005 →
  .0025); widening lowers it (0.518 at 2·tp, 0.424 at 4·tp). Monotone, brackets 0.5.
- **q decays with scale.** This closes the tick-vs-δ gap: δ=8·sd takes ~64 ticks
  to traverse, where q≈0.46, and q/(1−q) = 0.86 matches the measured ⟨ω⟩/δ ≈
  0.66–1.08. The binomial argument was never wrong; it was fed q at the wrong scale.
- **q=0.5 is not tunable in any transferable way.** `sl=2·tp` fixes n=150 and
  over-corrects at n=500, where momentum is already gone by m=2. q is a function
  of scale **and** n, and they interact.
- **UNVERIFIED:** whether any (n, tp, sl) gives q≈0.5 flat *and* a live market.
  `sl_enabled=False` reaches BM-like q only by freezing the market (ln p = +0.17).

### 2.3 The DC count law N(δ) ~ δ⁻² — SOLID at n=150, BROKEN at n=500

n=150, seed 1, T=12k: home/sl=.01 → **−1.801** (R² .984); home/sl=.02 → −2.123;
quantity/sl=.01 → −2.030; quantity/sl=.02 → −2.060. Plus seeds 1/2/3 at home,
tp=sl=.01: −2.012, −1.843, −2.161. **E_N ≈ −2 with ±0.2 scatter across seven
configurations.** Near −2, not precisely −2.

**At n=500, T=100k, seed 1, tp=.01, sl=.02, `close_mode` moves it:**

| close_mode | E_N | R² | ⟨ω⟩/δ |
|---|---|---|---|
| quantity | **−2.709** | 0.994 | 0.82 |
| home | **−1.805** | 0.982 | **3,298,302** |

Same n/T/seed/tp/sl. **The close rule moves the volatility law**, not just the
liquidity law. Does not reproduce at n=150. Partly explained by §2.6 (the quantity
arm is tethered, so it *has* no large excursions to count) — but the n-dependence
is **UNEXPLAINED**. Do not say "DCs are stable" without this.

### 2.4 The overshoot law ⟨ω⟩ = δ — DOES NOT HOLD, and is not a power law

**RETIRE every E_os number.** A slope fitted to a non-monotone curve measures
nothing (quantity arm: R² = 0.041). The instrument is not at fault:

- **Precise at this feed length.** BM, 100k ticks, 12 seeds: **E_os = 1.005 ±
  0.056** (true 1.0); E_N = −1.902 ± 0.053. The engine's 0.6 spread across seeds
  is ~10σ of measurement noise — real variance in the engine, not the estimator.
- **Drift does not explain it.** BM fed the seed-42 collapse (μ=−6.25e-5/tick)
  still gives E_os = 0.983.
- **What governs the level: q at the δ scale** (§2.2). **Not step size** — §2.5.

**The "hump" may be substantially noise — DOWNGRADED THIS SESSION.** Quantity arm,
n=150, T=32k, ⟨ω⟩/δ vs δ with event counts:

    0.93(n=460) 0.76(n=238) 0.68(n=139) 0.60(n=88) 0.60(n=50) 0.81(n=24) 0.87(n=12)

The decline is monotone and well-sampled; **the "rise" at large δ rests on 24 and
12 events.** Underneath may be a plain monotone fall. **Re-measure with enough
events at large δ before anyone explains the peak — it may not need explaining.**

**A finite-range explanation was tested and does NOT hold:** the largest usable δ
(0.31) is only 14% of the price's log-range (2.2), so "no room left to overshoot"
cannot bite at δ≈0.19.

### 2.5 Compact support — fat tails are structurally unreachable (NEW; the headline)

**Tail probabilities vs Gaussian** (n=500, T=8k, seed 1):

| | kurt(1) | P(\|r\|>2sd) | P(>3sd) | P(>4sd) | P(>5sd) |
|---|---|---|---|---|---|
| Gaussian | 0 | 4.6e-2 | 2.7e-3 | 6.3e-5 | 5.7e-7 |
| c=0.002 (open 8) | −0.41 | 1.3× | **0** | **0** | **0** |
| c=0.02 (open 130) | **+0.35** | 1.0× | 1.3× | **0** | **0** |

**Beyond 4 sd the probability is exactly zero — not small, zero.** The step
distribution has **compact support**. `|step| > 2·tp` is **0.0–0.2% at every
inventory level, every c, every n tested.**

**Why, structurally:** agents enter at the current price, so their take-profits
rest one band away — the price is permanently walled in on both sides. No order
can walk further than ~2 bands in a tick. **Every knob lives inside that wall.**
This is not "we have not found the setting"; **no setting exists.**

**Therefore: the engine makes EXCURSIONS but never JUMPS.** The home-arm runaway
travels ~14 e-folds — in thousands of tp-sized steps, never one large one. Fat
tails need jumps. **Fat tails require gaps in the book, or orders large relative
to depth. The TP mechanism guarantees neither.**

**Compact support does NOT explain the overshoot law.** The home arm has compact
support *and* ⟨ω⟩/δ = 3.3e6 in the same run. Tails are about single-step size;
overshoots are about runs of steps. Separate questions, separate answers (§2.2).

### 2.6 The quantity arm is tethered — anchoring quantified (NEW)

Quantity arm, n=150, seed 1, tp=sl=0.01, price log-range:

| T | log-range |
|---|---|
| 8,000 | **2.208** |
| 32,000 | **2.282** |

**4× the horizon, and the range does not grow.** A free random walk's range grows
as √T (expected ≈ 4.4). It didn't move. **The quantity arm's price is confined to
~2.2 log-units regardless of horizon** — the forced SL covers of stranded shorts
are the only counter-flow in the model, and they are the anchor. This unifies
V3.1's "recycling keeps the price bounded" with V3.3's "the drift is the cover
mechanics": both say *the cover flow is what pins the level*. It also
retro-explains §2.3's E_N = −2.709: far fewer large excursions than BM because
there **are** none.

Contrast the home arm: no forced-loss channel, nothing pins the level, the price
diffuses freely and runs a millionfold. That is the bill FINDINGS §V4.2 flagged
in advance.

### 2.7 The n=2 limit — the mechanism naked

`n=2, T=100k, seed 1, c=0.004, tp=sl=0.01, close_mode=home` → p_final =
8.678493, 329 clears (bit-reproducible; a fast fixture).

316 nonzero log-steps: **267 up (84.5%)**, 49 down. Median up-step +0.01000, down
−0.01000. **Sum of steps = +2.161 = ln p_final exactly.** 274 long round trips
(TP-rate **0.974**) vs 57 short: the two longs ratchet the price up by serially
filling each other's take-profits — A's entry-buy is the only thing that can fill
B's TP-sell, at +1%; B closes green, re-enters, fills A's TP; repeat 267 times.

**Closes the population sweep:** n=2 → 84.5%-up ratchet; n=150 → ACF(r) = +0.17;
n=500 → ~0.01. Same mechanism, diluted by two-sided depth.

**CAVEAT ON "THE SYMMETRIC NULL":** this is the *home-close* engine — the one
§V4.2 calls symmetric (x-share 0.50008 ± 0.00027). At n=2 it gives ln p = +2.16
and a 5:1 tribe asymmetry. **Symmetry is a large-n property, not a property of
the mechanism.** DIRECTION.md currently reads unconditional; it should not.

### 2.8 Stop clustering — the one thing that produced multi-band steps

`cfg.sl_grid` snaps SL triggers to a shared log grid (Osler 2005: FX stops cause
cascades *because* they cluster near round numbers). n=150, T=12k:

| sl_grid | kurt(1) | ACF(r) | q | steps>2·tp | max/tp |
|---|---|---|---|---|---|
| 0 | −0.18 | +0.114 | 0.701 | 0.2% | 2.0 |
| 0.002 | −0.12 | −0.080 | 0.608 | **6.4%** | 2.7 |
| 0.005 | −0.07 | −0.117 | 0.588 | **10.1%** | 2.6 |

Kurtosis rises but never crosses zero. **But `>2·tp` goes 0.2% → 10.1% — the only
intervention all session that produced multi-band steps.** Two confounds make this
**untested rather than falsified**: the side-preserving snap adds ~g/2 to the stop
distance (so g silently widens sl, and q falls 0.701 → 0.588 — the grid killed the
momentum it was meant to amplify); and at g=0.005 there is ~0.25 agents per level,
i.e. almost no clustering. *Fix: set raw = entry·e^(−(sl − g/2)) before flooring,
so mean stop distance stays at sl and g moves only clustering.*

**Density gate (measured; it reverses the feasibility estimate):** at n=500 only
**35 of 1000 agents hold a position at any moment**, and their stops span just
**3 sl-widths** — positions close fast, so all open ones were entered recently at
nearly the same price. **The stops are already clustered.** At g=0.002 (only ~10%
distance confound) that gives 5.83 agents/level, max 13. So the experiment is
clean and cheap: ~40 min at n=500/T=20k × 4 grids × 5 seeds.

---

## 3. The instrument

`dc_analysis.py`: Glattfelder–Dupuis–Olsen (arXiv:0809.1040) algorithm 2 verbatim
+ the overshoot dissection, and the Glattfelder–Golub (arXiv:2204.02682)
volatility/liquidity bridge. **Validated on BM before use:** bridge eq (30) gives
C^T = 3.984e-6, C^τ = 4.078e-6 against σ² = 4e-6 — the variance rate to 2%;
⟨ω⟩/δ = 1.003; ⟨r(Δt)⟩₂ ~ Δt^0.982.

**Four gotchas, all load-bearing:**

1. **⟨·⟩₂ differs between the papers.** 0809.1040: ⟨x⟩ₚ = ((1/n)Σxᵖ)^(1/p).
   2204.02682: ⟨x⟩₂ = (1/n)Σx². Only the latter balances eq (23)/(30) — check on
   BM: LHS = (T/Δt)σ²Δt = σ²T; RHS = δ²(σ²T/δ²) = σ²T. The code uses 2204's for
   the bridge. **Do not "fix" this.**
2. **δ floor.** Near the tick a single step jumps the threshold and inflates ⟨ω⟩.
   Measured on 400k BM ticks (theory E_N=−2, ⟨ω⟩/δ=1): floor 1× → −1.656/1.166;
   3× → −1.792/1.086; 5× → −1.839/1.057; **10× → −1.852/1.003**. Default 8×.
3. **Gauge.** `gauge="log"` is the default; `"relative"` reproduces the papers.
   Relative is right for FX (δ≤5%; measured agreement 0.32% at δ=0.01) and wrong
   here: the home arm spans e-folds, relative measures are not scale-covariant
   **and are asymmetric** (down bounded at −1, up unbounded) while the δ grid
   reaches 0.44. Same rule as "read transfer in X, never EUR", applied to the
   analysis code. **It does not fix the runaway** — on a BM spanning e²⁴ the two
   gauges give 1.22 vs 1.03; the 10⁶ is real.
4. **Kurtosis is the wrong instrument for tails** (§2.5). It conflates peakedness
   with tail weight, and this session it said "fat tails" while the tail was
   *exactly zero*. Measure P(|r| > k·sd) directly.

Files: `dc_analysis.py`, `scaling_law.py`, `export_price.py`, `test_bm.py`,
`stylized_facts.py`, `exp_inventory.py`. `REUSE_CSV=True` re-analyses an existing
feed in seconds — **delete the CSV when the config changes.**

---

## 4. Retractions and falsifications

Filed at equal weight with results (DIRECTION.md §4). **Six hypotheses met a
measurement this session and six died.** Nearly all were the assistant's own.

- **"symmetric_sizing symmetrizes the drift."** FALSIFIED: every seed detonates
  to ln p ≈ −34. The long's 1/p was the *stabilizer*.
- **"The entry cap prices a tribe out" (cap-freeze).** FALSIFIED: `open_btc`
  returns a real order from p=1e-11 to 7e11. Each tribe's cap saturates in its
  *own* home currency — swap-symmetric.
- **"The PnL=0 clustering is a freeze."** FALSIFIED — it is the EUR lens. At p→0
  a short's order is worth 1.98e-8 EUR while trading ~1981 BTC; the market was
  98.4% active. Swap-covariant, therefore evidence **for** symmetry.
- **"Heterogeneous tp restores scale-freeness."** FALSIFIED: log-uniform tp over
  4× made ⟨ω⟩/δ **worse** (1.11/0.88/0.71 → 0.83/0.67/0.50) though the lattice
  did break. The single scale is not what suppresses overshoots.
- **"sl = 2·tp gives q = 0.5."** FALSIFIED as a general recipe: true at n=150,
  over-corrects at n=500.
- **"The relative-vs-log gauge manufactures the 10⁶ overshoot."** FALSIFIED: on a
  BM spanning e²⁴, relative gives 1.22 vs log's 1.03. The runaway is real.
- **"close_mode is not what produced E_N = −2.709."** WRONG — retracted. Argued
  from an n=150 test that lacked the regime. **Do not generalise a null result
  from a population size where the effect cannot appear.**
- **"The thin tails are inventory-limited."** DEAD, and instructively. The metric
  confirmed it — corr(open, kurt) = **+0.723**, kurt(1) −0.54 → +0.78 across a
  **35× inventory range** (open 9.5 → 292) — and the phenomenon refuted it:
  `>2·tp` stayed at 0.0–0.2% throughout, and the step histogram shows the small
  bins doubling (25% → 53%) while the large bins **shrink** (17.9% → 9.3%).
  **Kurtosis rose because the centre got peakier, not because a tail grew.**
  Direct tail measurement: P(|r|>4sd) = 0. **The metric said yes before the
  phenomenon said no.**
- **"The overshoot hump is a finite-range artifact."** UNSUPPORTED: max usable δ
  (0.31) is 14% of the range (2.2), so the range cannot bite there.
- **"Compact support explains the overshoot law."** NO — the home arm has compact
  support *and* ⟨ω⟩/δ = 3.3e6.
- **All E_os values.** RETIRED.

---

## 5. Bugs found and fixed — and the class

All are **labels that lie about what ran**. The most dangerous class here: it
silently destroys attribution.

- `run_single.py` had only N/T/SEED/F/C in its block and passed only those. A
  `TP = 0.01` added to it was **silently ignored**. FIXED.
- `Config.summary()` — printed every run under "resolved configuration" —
  **omitted tp, sl, close_mode, sl_mode, x_accounting, log_thresholds,
  symmetric_solvency.** Every switch defining the model was invisible, which is
  why the above could hide. FIXED (display-only; runs bit-identical); it now also
  surfaces silently-defaulted arithmetic bands and one-sided solvency clamps.
- `scaling_law.py` hardcoded `f"tp=sl={TP}"` (lies when tp≠sl) and **never passed
  `close_mode`**, so feeds were silently built on the `"quantity"` engine. FIXED.
- `cfg.sl_grid` with `round()` snapped stops *at or past* entry → instantly
  triggered → **market froze (zero price steps)**. FIXED with floor/ceil.

**LIVE TRAP.** `config.py` still defaults `close_mode="quantity"` while current
work passes `"home"`. Anything not passing it explicitly (`main.py`, bare
`Config()`) runs a **different model**. `REFERENCE.md`'s targets were generated on
the quantity path. Flip the default and re-baseline, or make every entry explicit.

**Do not delete `quantity`.** Per §V3.2's impossibility triangle (forced execution
/ spend-boundedness / tribe symmetry — pick two) and §2.6: home is the clean
symmetric *toy*; quantity is where the market phenomena live and is arguably the
realistic rule (a real short owes a *quantity*; that is what a squeeze is). The
runaway was only detectable **because** the quantity arm existed to compare against.

---

## 6. Open threads, in order

1. **Cluster the TAKE-PROFITS, not the stops.** The corrected Osler experiment,
   and the last shot at a stylized fact at level 0. Stops are already clustered
   (§2.8) and firing them together produced no jumps. What creates jumps is
   clustering the **depth**: pile TPs onto discrete levels and the space *between*
   levels is **empty** — and a gap is what a jump is. This is Osler's actual
   structure (Osler 2003, J. Finance 58:1791): **take-profits cluster *at* round
   numbers** → partially reflecting barriers → trends reverse; **stops cluster
   *just beyond*** → trends accelerate. Those two facts are her explanation for
   support/resistance and breakouts. Almost 10% of her orders sat at rates ending
   in 00.
   - *Scale-covariant implementation:* round numbers are absolute, our price spans
     e-folds — so snap to **k significant figures**, which is both what humans
     actually do (1.2000, 45,000) and covariant by construction.
   - *Prediction, stated now:* `>2·tp` becomes **nonzero for the first time**. If
     it stays 0.0%, compact support survives clustering and fat tails are
     unreachable at level 0 — a second confirmed instance of §0.
   - *Second-order prediction:* a **single** grid adds one characteristic scale →
     ⟨ω⟩(δ) develops a staircase → the OS law gets **worse**. A **hierarchy**
     (per-agent roundness, weighted coarse: retail says "50,000", a pro "48,750",
     a quant "48,732.5") is self-similar → scale-free → ⟨ω⟩=δ can survive *while*
     tails appear. Osler measured the hierarchy directly (00 clusters stronger
     than 50). **This is the cheapest realism available: not a strategy, a
     cognitive quirk. Call it level 0.5 — agents with round fingers.**
2. **Re-measure the hump with enough events at large δ** (§2.4) before treating it
   as a phenomenon. It may be noise over a monotone decline.
3. **The runaway** (§2.5, home arm). Characterise: how often, how long, what
   starts and ends it. *Conjecture to test:* a monotone run consumes the TPs it
   passes, so depth is destroyed by the move that would resist it — positive
   feedback in the liquidity. *Prediction:* depth ahead of the price falls
   monotonically through a runaway and does not recover until it stops. If depth
   replenishes mid-run, retract.
4. **`close_mode` moves E_N at n=500 but not n=150** (§2.3). Partly explained by
   §2.6's tethering; the n-dependence is not. The n-sweep of that pair is the test.
5. **The n=2 ↔ n=150 sign flip.** TP fills *ratchet* at n=2 (84.5% up) and *revert*
   at n=150. Same mechanism, opposite sign, depending on opposing depth.
6. **Stranding** — see `HANDOFF_stranding-v2.md`; P1/P2/P3 open.
7. **Level 1 — with a pre-registered prediction.** Add an agent supplying depth
   **independent of its own P&L**, and ⟨ω⟩/δ moves toward 1.
   - *Use Avellaneda–Stoikov (2008), not Glosten–Milgrom.* GM needs a fundamental
     value V and Bayesian learning about it. **We have no V** — the market is
     closed, so "informed" is meaningless. In GM's terms our engine is μ=0, all
     noise traders — and **GM at μ=0 gives a constant price**: nothing to learn,
     nothing moves. Our price moves anyway, mechanically. Two different
     price-formation processes wearing the same clothes. A–S quotes around a
     reservation price skewed by inventory with a risk-aversion parameter and
     needs no V.
   - *But GM still buys three things:* the martingale-by-construction theorem (§0);
     a canonical precedent for market breakdown (GM's market shuts down when
     informed traders dominate — rhymes with V3.1's `slimit` lockups); and a
     reframe of what "informed" could mean here. **In a market with no
     fundamental, information is about POSITIONING, not value.** An agent who knew
     where the resting TPs and armed SLs sat could predict the cascades exactly.
     That is stop-hunting; it is real; and Osler's dealers literally have it — they
     hold the book, and round numbers make the clusters *public*. That closes the
     loop with thread 1: **clustering is what makes positioning inferable.**

---

## 7. Invariants that must not regress

- **The three-mechanism inventory is the frame.** Open / TP / SL; the only passive
  depth is TP limits. Any new mechanism changes what liquidity *is* — say so.
- **Never quote an E_os.** The relation is not a power law.
- **Never use kurtosis to argue about tails.** It conflates peakedness with tail
  weight. Measure P(|r| > k·sd).
- **Measure in logs, not relative returns**, anywhere the price spans e-folds.
- **Validate any new instrument on Brownian motion first**, where the answer is
  known. It caught the δ-floor bias and confirmed the bridge to 2%.
- **A block that lies is worse than no block.** Every knob in an edit block must
  be passed; every run must print the switches it used.
- **Distributions across ≥10 seeds before any number is load-bearing.** Almost
  everything here is 1–3 seeds.
- **Symmetry is a large-n claim.** Restate it that way wherever it appears.
- **Do not generalise a null result from a regime where the effect cannot appear.**
