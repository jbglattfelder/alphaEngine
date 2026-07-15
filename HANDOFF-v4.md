# The Alpha Engine — Handoff v4: the mechanism inventory and the scaling laws

Written as a handoff. Readable by a person or by an LLM picking up the work.
Every claim is either measured or marked unverified. Predictions are stated
before the run that would test them. Distributions, not trajectories.

Scope: what the price process *is*, read through intrinsic time (directional
changes / overshoots). For stranding read `HANDOFF_stranding-v2.md`; for the
broader state `HANDOFF.md`; for strategy `DIRECTION.md`.

---

## 1. The thesis: liquidity is other agents' unrealized profit

There are only three mechanisms. Agents **open**, **take profit**, **stop out**.
Nothing else exists. Sorted by *role* rather than name:

- **Aggressive flow** — the entry imbalance (the balanced crossing matches long
  buys against short sells at `p_prev` with no impact; only the *net* walks the
  book) plus **SL covers**, which are market orders.
- **Passive depth** — **TP limits, and nothing else.**

So: **every resting order in the book is a take-profit, and a take-profit exists
only because someone holds an open position.** There are no market makers, no
quotes, no inventory management. Liquidity is not provided; it is a byproduct of
positioning. That one sentence retro-explains every measurement below, and it is
the frame to carry into level 1.

Consequences, each measured in §2:

- **The tick volatility cannot be anything but the TP band.** The only price the
  book can move *to* is a resting TP level, which sits at ±tp from an entry.
  Measured: `sd(r) = 0.78·tp` and `median|log-step| = tp` **exactly**.
- **The continuation probability `q` is the exit mix, mechanically.** A TP is a
  passive limit *against* the move (reversion); an SL is a market order *with* it
  (momentum). No third channel exists, so `q` is pinned by their ratio — not by
  anyone's behaviour.
- **A monotone run consumes the TPs it passes through.** Depth is destroyed by
  the very move that would need to resist it, and nothing replaces it. Positive
  feedback *in the liquidity itself*. (CONJECTURED mechanism for §2.5; the
  runaway is measured, this explanation is not yet tested — see §6.1.)
- **The forced SL cover is the only counter-flow in the model**, and it is also
  the recycler: a forced exit returns an agent to flat, which lets it re-enter,
  which creates a new TP, which *is* new depth. This unifies V3.1's "recycling is
  what keeps the price bounded" with V3.3's "the drift is the cover mechanics":
  both are "the cover flow is what anchors the level."

---

## 2. What is measured

Engine: v4 (`close_mode`, `sl_mode`), `x_accounting=True`, `log_thresholds=True`,
`symmetric_solvency=True`, `f=0.5`, `c=0.004`. All runs pass every conservation +
solvency check unless noted. Seeds noted per result — most are 1–3, so read
direction and order of magnitude, not levels.

### 2.1 The lattice — SOLID (8× tp range, all n)

The price is not a diffusion. It is a **lattice walk whose spacing is `tp`**.

| tp | sd/tp | median\|log-step\|/tp |
|---|---|---|
| 0.005 | 0.794 | **1.000** |
| 0.01 | 0.787 | **1.000** |
| 0.02 | 0.780 | **1.000** |
| 0.04 | 0.762 | **1.000** |

Not approximately 1.000 — exactly, because `log_thresholds` puts the TP at
e^±tp. Fraction of steps landing exactly on one band: n=2 → 98.7%, n=20 → 93.4%,
n=150 → 48.7% (the mode never leaves the band at any n).

**Consequence for the scaling laws:** `tp` is a *characteristic scale*, and BM/FX
have none. `sd ≈ 0.8·tp` also means **a δ grid pinned to tick-sd holds δ/tp
fixed** — you cannot vary the lattice without varying the volatility, and at
fixed T you cannot vary the volatility without varying the total excursion
(ln p went −2.26 → −18.26 as tp went 0.005 → 0.04). Any tp-sweep is confounded
three ways. To separate them you must hold `tp·√T` constant: matching tp=0.04's
excursion at tp=0.01 needs T ≈ 240k, at tp=0.005 roughly 10⁶.

### 2.2 `q`, the continuation probability — the exit mix, and it is scale-dependent

`q` = fraction of price steps continuing the previous direction. BM = 0.5 at
every scale; that *is* scale-freeness. Measured at coarse-graining scale m
(ticks), n=150, T=12k, seed 1:

| config | m=1 | 2 | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|---|
| BM control | 0.496 | 0.484 | 0.494 | 0.471 | 0.500 | 0.485 | 0.581 |
| tp=.01 sl=.01 | **0.701** | 0.642 | 0.604 | 0.552 | 0.507 | 0.448 | 0.462 |
| tp=.01 sl=.02 | 0.518 | 0.484 | 0.450 | 0.474 | 0.467 | 0.505 | 0.435 |
| tp=.01 sl=.04 | 0.424 | 0.436 | 0.443 | 0.413 | 0.440 | 0.381 | 0.473 |
| **n=500** tp=.01 sl=.01 | 0.656 | **0.510** | **0.458** | 0.463 | 0.480 | 0.454 | 0.452 |

Established:

- **The engine is persistent at the tick scale, not anti-persistent** (q=0.70).
  Earlier session notes claiming mean-reversion from `ACF|r|` were reading a
  statistic diluted by zero-steps; on nonzero steps continuation is 70%.
- **SLs are the momentum.** `sl_enabled=False` → q = 0.516 (BM-like) with 0/2649
  SL/TP exits. Tightening sl raises q monotonically (0.703 → 0.779 → 0.800 at
  sl = 0.01 → 0.005 → 0.0025). Widening it lowers q (0.518 at 2·tp, 0.424 at
  4·tp). The knob is real, monotone, and brackets 0.5.
- **`q` decays with scale.** Momentum at 1 tick, reversion by m≈32. This closes
  the tick-vs-δ gap: δ=8·sd takes ~64 ticks to traverse, where q≈0.46, and the
  binomial argument q/(1−q) = 0.86 matches the measured ⟨ω⟩/δ ≈ 0.66–1.08. The
  formula was never wrong; it was being fed q at the wrong scale.
- **`q=0.5` is NOT tunable in any transferable way.** The n=150 recipe
  (`sl=2·tp`) fails at n=500, where the cascade is already diluted (momentum gone
  by m=2) so sl=0.02 *over*-corrects into reversion. q is a function of scale
  **and** n, and the two interact. There is no (tp, sl) pair; there is a fit to
  one population size.
- **UNVERIFIED:** whether any (n, tp, sl) gives q≈0.5 flat across scales *and* a
  live market. `sl_enabled=False` achieves BM-like q only by freezing the market
  (ln p = +0.17; too few DC events to measure) — the `nosl` corner of V3.

### 2.3 The DC count law N(δ) ~ δ⁻² — SOLID at n=150, BROKEN at n=500

At n=150 the volatility law holds across engines, sl, and seeds:

| close_mode | sl | E_N | R² |
|---|---|---|---|
| home | 0.01 | −1.801 | 0.984 |
| home | 0.02 | −2.123 | 0.968 |
| quantity | 0.01 | −2.030 | 0.959 |
| quantity | 0.02 | −2.060 | 0.994 |

Plus seeds 1/2/3 at home, tp=sl=0.01: −2.012, −1.843, −2.161. So **E_N ≈ −2 with
±0.2 scatter across seven configurations** — near −2, not precisely −2.

**But at n=500, T=100k, seed 1, tp=0.01, sl=0.02, `close_mode` moves it:**

| close_mode | E_N | R² | ⟨ω⟩/δ |
|---|---|---|---|
| quantity | **−2.709** | 0.994 | 0.82 |
| home | **−1.805** | 0.982 | **3,298,302** |

Same n/T/seed/tp/sl — only the close rule differs. **The close rule moves the
volatility law**, not just the liquidity law. This does not reproduce at n=150
(all four cells ≈ −2), so it is an n and/or T effect and is **UNEXPLAINED**.
Do not state "DCs are stable" without this caveat.

### 2.4 The overshoot law ⟨ω⟩ = δ — DOES NOT HOLD, and is not a power law

**RETRACT every E_os number produced this session.** ⟨ω⟩(δ) is **not monotone**:
on the quantity arm it rises, peaks near δ≈0.19, and collapses (R² = 0.041 —
essentially zero explanatory power). Fitting a straight line to a hump yields a
slope that depends on where the δ grid happens to sit; that is the entire
explanation for the "unstable exponent" (0.58 vs 1.18 across seeds), and it is
not seed noise:

- **The instrument is precise at this feed length.** BM at 100k ticks, matched σ,
  12 seeds: **E_os = 1.005 ± 0.056** (true value 1.0), E_N = −1.902 ± 0.053. The
  engine's 0.6 spread is ~10σ of measurement noise.
- **Drift does not explain it.** BM fed the exact collapse of the seed-42 run
  (μ = −6.25e-5/tick, ln p = −7.7) still gives E_os = 0.983.
- **The shape is the finding, not a slope.** ⟨ω⟩(δ) rises, peaks, collapses.
  Nothing yet explains the peak. `q(m)` is monotone and cannot produce a
  non-monotone ⟨ω⟩ — so there is a **second mechanism** untouched.

### 2.5 The runaway — the headline (home arm)

⟨ω⟩/δ = 3.3e6 on the home arm is **real, not a gauge artifact**. An overshoot of
10⁶ requires the price to rise a **millionfold between two directional changes** —
~14 e-folds with no 13% pullback. BM cannot do this (max overshoot 1.91 even on a
path spanning e²⁴, because BM is jagged). The home price can: it is the **n=2
ratchet at n=500** — a monotone staircase of sequential TP fills with no opposing
depth to interrupt it.

This is the bill FINDINGS §V4.2 flagged in advance ("nothing pins a level, so it
diffuses") and §V3.1 saw as tribe lockup with the price running unboundedly.
**E_N = −1.805 looks healthy precisely because counting reversals cannot see a
runaway between them.** The overshoot panel is what exposes it.

### 2.6 The n=2 limit — the mechanism naked

`n=2, T=100k, seed 1, c=0.004, tp=sl=0.01, close_mode=home` → p_final =
8.678493, 329 clears (bit-reproducible; useful as a fast fixture).

- 316 nonzero log-steps: **267 up (84.5%)**, 49 down. Median up-step +0.01000,
  down −0.01000. Sum of steps = **+2.161 = ln p_final exactly**. Net up-steps
  218 vs 217 needed. The price *is* the running sum of TP fills.
- 274 long round trips (TP-rate **0.974**) vs 57 short. The two longs ratchet the
  price upward by serially filling each other's take-profits: A's entry-buy is the
  only thing that can fill B's TP-sell, at +1%; B closes green, re-enters, fills
  A's TP. Repeat 267 times.

**This is the momentum mechanism in pure form**, and it closes the population
sweep: n=2 → an 84.5%-up ratchet; n=150 → ACF(r) = +0.17; n=500 → ~0.01. Same
mechanism, progressively diluted by two-sided depth.

**CAVEAT ON "THE SYMMETRIC NULL":** this is the *home-close* engine — the one
§V4.2 calls symmetric (x-share 0.50008 ± 0.00027, "drift is dead"). At n=2 the
same engine gives ln p = +2.16 and a 5:1 tribe asymmetry. **Symmetry is a
large-n property, not a property of the mechanism.** DIRECTION.md currently reads
unconditional; it should not.

---

## 3. The instrument

`dc_analysis.py` implements Glattfelder–Dupuis–Olsen (arXiv:0809.1040) algorithm 2
verbatim plus the overshoot dissection, and the Glattfelder–Golub
(arXiv:2204.02682) volatility/liquidity bridge. **Validated on Brownian motion
before use** (an unvalidated instrument is HANDOFF §7's weakest-link category):

- Bridge eq (30): **C^T = 3.984e-6, C^τ = 4.078e-6, against σ² = 4e-6** — the
  variance rate recovered to 2%.
- ⟨ω⟩/δ = 1.003, ⟨r(Δt)⟩₂ ~ Δt^0.982.

**Two gotchas, both load-bearing:**

1. **The two papers define ⟨·⟩₂ differently.** 0809.1040: ⟨x⟩ₚ = ((1/n)Σxᵖ)^(1/p)
   (quadratic mean). 2204.02682: ⟨x⟩₂ = (1/n)Σx² (mean square). Only the latter
   balances eq (23)/(30) — check on BM: LHS = (T/Δt)σ²Δt = σ²T; RHS = δ²(σ²T/δ²)
   = σ²T. The code uses the 2204 convention for the bridge. Do not "fix" this.
2. **δ floor.** Near the tick size a single tick jumps the threshold and inflates
   ⟨ω⟩. Measured on 400k BM ticks (theory E_N=−2, ⟨ω⟩/δ=1):

   | δ floor | E_N | ⟨ω⟩/δ |
   |---|---|---|
   | 1× tick-sd | −1.656 | 1.166 |
   | 3× | −1.792 | 1.086 |
   | 5× | −1.839 | 1.057 |
   | **10×** | **−1.852** | **1.003** |

   Default floor is 8×. The ceiling trades off against feed length (N ~ σ²T/δ²).

**TODO — switch to the log gauge.** The committed code uses the papers' *relative*
returns. That is right for FX (δ ≤ 5%, log ≈ relative) and wrong here: home mode
spans e-folds, and relative measures are not scale-covariant *and are asymmetric*
(down-moves bounded at −1, up unbounded) — while our δ grid reaches 0.44. The
log-gauge prototype (`logdc.py`) validates on BM (E_N = −1.833 R²=0.999,
E_os = +0.860 R²=0.984, ⟨ω⟩/δ = 0.987) and would report the runaway as ⟨ω⟩/δ ≈
100 rather than 3.3e6 — still catastrophic, but a number you can reason about.
This is the same "read in X, never in EUR" rule applied to the analysis code.

Files: `dc_analysis.py` (algorithm + six laws + bridge), `scaling_law.py` (edit
block → run → CSV → reload → 2-panel log-log), `export_price.py` (feed → CSV),
`test_bm.py` (the control). `REUSE_CSV=True` re-analyses an existing feed in
seconds — **delete the CSV when you change the config.**

---

## 4. Retractions and falsifications, this session

Filed at equal weight with the results, per DIRECTION.md §4. Six of these were
the assistant's own proposals, killed by measurement:

- **"symmetric_sizing symmetrizes the drift."** FALSIFIED: every seed detonates
  to ln p ≈ −34. The long's 1/p was the *stabilizer*, not just the asymmetry.
- **"The entry cap prices a tribe out at extreme prices" (cap-freeze).**
  FALSIFIED: `open_btc` returns a real order at every price from 1e-11 to 7e11;
  at p=7e11 a long still places a ~1996 EUR order. Each tribe's cap saturates in
  its *own* home currency — swap-symmetric.
- **"The PnL=0 clustering is a freeze."** FALSIFIED — it is the EUR lens. At
  p→0 a short's order is worth 1.98e-8 EUR while trading ~1981 BTC. The market
  was 98.4% active. The tribe whose home currency is worthless goes EUR-invisible;
  the pattern is *swap-covariant* and therefore evidence **for** symmetry.
- **"Heterogeneous tp restores scale-freeness."** FALSIFIED: log-uniform tp over
  4× made ⟨ω⟩/δ **worse** (1.11/0.88/0.71 → 0.83/0.67/0.50) even though the
  lattice did break. The single scale is not what suppresses overshoots.
- **"sl = 2·tp gives q = 0.5."** FALSIFIED as a general recipe: true at n=150,
  over-corrects at n=500.
- **"The relative-vs-log gauge manufactures the 10⁶ overshoot."** FALSIFIED: on a
  BM spanning e²⁴ the relative gauge gives 1.22 vs the log gauge's 1.03. The
  runaway is real. (The log gauge is still the right instrument — for a different
  reason.)
- **"close_mode is not what produced E_N = −2.709."** WRONG — retracted. Argued
  from an n=150 test that lacked the regime; the n=500/T=100k home-vs-quantity
  pair reproduces it cleanly. Do not generalise a null result from a population
  size where the effect cannot appear.
- **All E_os values.** RETIRED — a slope fitted to a hump measures nothing.

---

## 5. Bugs found and fixed — and the class they belong to

All three are **labels that lie about what ran**. This is the most dangerous bug
class in this project, because it silently invalidates attribution.

- `run_single.py` had only N/T/SEED/F/C in its edit block and passed only those.
  A `TP = 0.01` added to the block was **silently ignored**; tp/sl fell through to
  the config defaults. FIXED: every switch is in the block and passed.
- `Config.summary()` — printed on every run under the heading "resolved
  configuration" — **omitted tp, sl, close_mode, sl_mode, x_accounting,
  log_thresholds, symmetric_solvency.** Every switch that decides *which model
  you are running* was invisible, which is why the above could hide. FIXED
  (display-only; runs bit-identical). It now also surfaces silently-defaulted
  arithmetic bands and one-sided solvency clamps.
- `scaling_law.py` hardcoded `f"tp=sl={TP}"` in the title (lies when tp≠sl) and
  **never passed `close_mode`**, so feeds were silently built on the `"quantity"`
  engine. FIXED.

**LIVE TRAP — resolve deliberately.** `config.py` still defaults
`close_mode="quantity"` while every current run passes `"home"`. Any entry point
that does not pass it explicitly (`main.py`, a bare `Config()`) runs a *different
model*. `REFERENCE.md`'s bit-check targets were generated on the quantity path.
Either flip the default and re-baseline, or make every entry point explicit.

**Do not delete `quantity`.** Per §V3.2's impossibility triangle (forced
execution / spend-boundedness / tribe symmetry — pick two) and §V4.4: home is the
clean symmetric *toy* baseline; quantity is where the market phenomena live
(squeezes, stranding, cover-driven drift) and is arguably the realistic rule — a
real short owes a *quantity*. Keep home as default and quantity as a named
treatment with a bit-identity test. The runaway in §2.5 was only detectable
*because* the quantity arm existed to compare against.

---

## 6. Open threads, in order

1. **The runaway (headline).** Characterise it: how often, how long, what starts
   and ends it. CONJECTURE to test: a monotone run consumes the TPs it passes
   through, so depth is destroyed by the move that would resist it — positive
   feedback in the liquidity. *Prediction:* book depth ahead of the price falls
   monotonically through a runaway and does not recover until the run stops. If
   depth is replenished during a run, the conjecture is wrong — retract it.
2. **The hump.** ⟨ω⟩(δ) rises, peaks near δ≈0.19, collapses. `q(m)` is monotone
   and cannot produce it. Find the second mechanism. Do this in the **log gauge**.
3. **`close_mode` moves E_N at n=500 but not n=150** (−1.805 vs −2.709). Unexplained.
   The n-sweep of that pair is the experiment.
4. **The n=2 ↔ n=150 sign flip.** TP fills *ratchet* at n=2 (84.5% up) and
   *revert* at n=150. Same mechanism, opposite sign, depending on opposing depth.
   Unexplained.
5. **Stranding** — see `HANDOFF_stranding-v2.md`; P1/P2/P3 still open.
6. **Level 1, with a pre-registered prediction.** N(δ)~δ⁻² survives because
   counting reversals needs no liquidity provider. ⟨ω⟩=δ fails because how far a
   price runs is *exactly* a question about depth — and our depth is endogenous to
   the run itself. Real markets get ⟨ω⟩≈δ because someone quotes whose willingness
   does not evaporate when the price moves. **That is not a parameter we are
   missing; it is an actor.** *Prediction, stated now:* add an agent supplying
   depth independent of its own P&L, and ⟨ω⟩/δ moves toward 1. Falsifiable, and
   the instrument for it is committed and BM-validated.

---

## 7. Invariants that must not regress

- **The three-mechanism inventory is the frame.** Open / TP / SL, and the only
  passive depth is TP limits. Any new mechanism changes what liquidity *is* —
  say so explicitly.
- **Never quote an E_os.** The relation is not a power law.
- **Measure in logs, not relative returns**, anywhere the price spans e-folds.
  Same rule as "read transfer in X, never EUR", applied to the analysis code.
- **Validate any new instrument on Brownian motion first**, where the answer is
  known. It caught the δ-floor bias and confirmed the bridge to 2%.
- **A block that lies is worse than no block.** Every knob in an edit block must
  be passed; every run must print the switches it actually used.
- **Distributions across ≥10 seeds before any number is load-bearing.** Almost
  everything above is 1–3 seeds: direction and order of magnitude only.
- **Symmetry is a large-n claim.** Restate it that way wherever it appears.
