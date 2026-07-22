# The Alpha Engine — Master Findings

The detailed experiment records. Absorbs `FINDINGS_stranding.md`,
`FINDINGS_tpcluster.md`, and `FINDINGS_nopen_durations.md`. For state, direction,
and the scorecard, read `HANDOFF-master.md`; this holds the tables and the
prediction-by-prediction scoring.

**Standing caveat: nearly every number here is 1–3 seeds unless a row says
otherwise — direction and order of magnitude, not levels.** Predictions were
stated in the experiment headers *before* running; each is quoted then scored.

Contents: §T TP-clustering (compact support breaks) · §N n_open collapse ·
§D duration laws · §S stranding (P1/P2/P3, sl_mode arms, home resolution).

---

# §T — TP clustering: compact support breaks, and only heterogeneity breaks it

HANDOFF-master §5.1. The "cluster the take-profits, not the stops" experiment.
Home arm, n=150, c=0.004, T=16k, tp=sl=0.01. **Seeds 1–2.** Artifact:
`tpcluster.jsonl`; predictions in `exp_tpcluster.py`.

| arm | tp_eff | >2·tp | max/tp | P>3sd | P>4sd | P>5sd | os(δ=8sd) |
|---|---|---|---|---|---|---|---|
| off | 0.0100 | 0.2% | 2.0 | 0 | 0 | 0 | 0.99 |
| k=3 | 0.0099 | 0.9% | 3.0 | 0 | 0 | 0 | 0.86 |
| k=2 | 0.0291 | 45.2% | 13.4 | 0.0003 | 0 | 0 | 1.12 |
| k=1 | 0.2227 | 100% | 69.3 | 0 | 0 | 0 | 1.00 |
| **hier** | 0.0485 | 47.4% | **70.3** | **0.031** | **0.021** | 0 | 0.47 |
| hier (seed 2) | 0.0476 | 43.2% | **70.3** | **0.030** | **0.022** | 0 | 0.49 |
| ctrl: off, tp=.029 | 0.0290 | 74.2%* | 3.9* | 0 | 0 | 0 | — |

\* vs the *nominal* 0.01 band, for comparability with the k=2 row.

**P2 — CONFIRMED; the first break of compact support in the project.** The
hierarchy arm (per-agent roundness: 20% k=1, 40% k=2, 30% k=3, 10% unsnapped)
gives **P(|r|>4·sd) = 2.1–2.2%** against a Gaussian 0.006% and against the
measured *exact zero* everywhere else — replicated to the second decimal on both
seeds, single steps of 70 bands.

**The controls make it clean.** Two ways it could have been fake, both excluded:
(a) *band inflation* — the entry-side guard widens effective tp when grid spacing
exceeds it (the tp_eff column; the confound gauge specified in advance). The
band-matched control (no snap, tp=0.029 = k2's realized band) keeps P>4sd at
exactly zero *in its own sd units*: a wider uniform band just re-lattices, and
compact support scales with the band exactly as the structural argument requires.
(b) *any single grid* — k=1, with 22× band inflation and 100% multi-band steps,
also has zero tail. **A single characteristic scale cannot make tails, no matter
how coarse.**

What does: **heterogeneous roundness.** Depth piles onto shared coarse levels
while the typical band (hence tick sd) stays fine; a traversal across an empty
coarse gap is a jump that is large *in the arm's own volatility units*. Fat tails
are a property of the *mixture*, not any grid — Osler's hierarchy (00 beats 50)
doing exactly the job assigned it.

**P1 — confirmed only in the confounded sense.** The single-k `>2·tp` explosions
are mostly band inflation (the control reproduces them). The honest multi-band
claim rests on the hier arm's max/tp = 70 at tp_eff only 4.8×.

**P3 — HALF-FALSIFIED.** Predicted: tails *while preserving* scale structure. Got
the tails and **damaged the overshoot ratio worst of all arms** (0.47–0.49 vs
0.99). At level 0.5 you can have fat tails or the overshoot remnant, not both —
consistent with the verdict that the overshoot law needs the actor; no depth
*geometry* substitutes.

**Consequences for the scorecard.** "Fat tails — unreachable" becomes conditional:
unreachable under homogeneous bands (re-proved twice by the controls), reachable
at **level 0.5 — agents with round fingers** (one cognitive quirk, no actor, no
strategy). The compact-support structural argument survives intact — it was always
about a *single* wall spacing. Theorem-shaped version: **max |step| is set by the
largest empty interval in the resting-TP level set**; homogeneous bands bound it
at ~2·tp; a roundness hierarchy makes the interval distribution itself
heterogeneous. The bound didn't break; the geometry it bounds changed.

**Caveats + confound-free follow-up.** Two seeds; tp_eff confound *reduced* to
4.8×, not eliminated (k=1 carries 22× inflation into the mixture). Fix: drop k=1
(weights over {2,3,none}) and/or pre-compensate the snap (aim raw at tp − E[shift],
the sl_grid fix). *Prediction:* the 4sd tail survives both at reduced magnitude;
if it vanishes, the tail was k=1's wide bands — retract. Then ≥10 seeds before the
scorecard edit is load-bearing.

---

# §N — the n_open collapse (level-0 closing test)

HANDOFF-master §4.2. Predictions in `exp_nopen.py`; artifact `nopen.jsonl`.
Home arm, tp=sl=0.01, seed 1 unless noted.

> *P1: q(m=1) decreases in mean n_open, and points from different n at similar
> n_open coincide. P2: a common q=0.5 crossing in n_open.*

| n | c | n_open | q1 | q2 | q8 | lnp |
|---|---|---|---|---|---|---|
| 50 | 0.01 | 2.7 | 0.755 | 0.711 | 0.629 | +2.78 |
| 150 | 0.004 | 4.2 | 0.719 | 0.675 | 0.607 | −3.82 |
| 150 | 0.01 | 12.6 | 0.664 | 0.541 | 0.478 | −1.50 |
| 150 | 0.01 (seed 2) | 10.4 | 0.658 | 0.538 | 0.482 | +0.61 |
| 50 | 0.05 | 14.3 | 0.648 | 0.536 | 0.465 | +1.63 |
| 500 | 0.004 | 19.5 | 0.685 | 0.546 | 0.478 | −0.31 |
| 150 | 0.02 | 27.7 | 0.683 | 0.534 | 0.435 | +0.97 |
| 500 | 0.004 (seed 2) | 23.5 | **0.730** | **0.646** | **0.579** | **+4.10** |
| 150 | 0.05 | 67.3 | 0.690 | 0.521 | 0.464 | −1.44 |
| 500 | 0.02 | 127.0 | 0.746 | 0.592 | 0.391 | +0.08 |

**What held.** The designed cross-n matched pair collapses beautifully:
(n=50, c=0.05, n_open=14.3) and (n=150, c=0.01, n_open=12.6) have near-identical
*full q(m) profiles* (0.648/0.536/0.465 vs 0.664/0.541/0.478), replicated at seed
2 for the n=150 cell to three decimals. **At low-to-moderate inventory, n and c
are interchangeable through n_open** — the mechanistic variable is depth.

**What sharpened.** q1 does **not** go to 0.5 — it *floors* at ~0.65–0.69 from
n_open ≈ 12 onward, to n_open = 127. n_open controls the **decay scale of the
momentum** (q2, q8 fall toward/below 0.5), not the tick-level continuation, which
is a fixed property of the SL-cover mechanism. *Inventory sets the persistence
length, not strength.* This refines the "momentum gone by m=2 at n=500" claim —
q1 was never gone.

**What broke, and the confound it exposed.** The high-inventory region does not
collapse: (n=500, c=0.004) seed 2 sits far off seed 1 at the same config
(q1 0.730 vs 0.685) and trended hard (lnp +4.10). **q(m) is entangled with the
realized path** — a trending run shows elevated continuation at every scale,
mechanically. So: (1) P1/P2 are **UNRESOLVED at high inventory** (deviation tracks
lnp, not n-at-fixed-inventory — neither confirmed nor falsified; needs
trend-stratified q + ≥5 seeds/cell); (2) **the confound applies retroactively to
HANDOFF-master §4.2's single-seed q table** — those levels are path-conditional;
the qualitative claims (SLs are momentum; q decays with scale) are safe.

---

# §D — the duration laws (level-0 closing test)

HANDOFF-master §5.2. Predictions in `exp_durations.py`. Engine (home, n=150,
c=0.004, T=32k, seed 1) vs BM matched in nonzero-step sd, zero-step density, and
length; log gauge; durations = `DCEvent.n_ticks_tm`.

> *P1: engine total-move durations thinner-tailed than BM at matched δ/sd. P2:
> engine duration CV < BM. Falsifier: engine tail ≥ BM at any δ → the clock does
> not regularise waiting; retract the "structurally unreachable" framing for the
> time laws.*

| δ/sd | arm | events | median | CV | P(τ>5·med) | max/med |
|---|---|---|---|---|---|---|
| 8 | engine | 420 | 61 | 0.72 | 0.005 | 5.1 |
| 8 | BM | 225 | 115 | 0.69 | 0.000 | 4.6 |
| 16 | engine | 166 | 157 | 0.77 | 0.012 | 5.9 |
| 16 | BM | 62 | 294 | 0.93 | 0.048 | 6.9 |
| 32 | engine | 42 | 421 | **2.27** | 0.024 | **26.9** |
| 32 | BM | 14 | 1628 | 0.81 | 0.000 | 4.1 |

**The falsifier fired at δ=32·sd.** Engine durations are *fatter*-tailed than BM's
— CV 2.27 vs 0.81, one traversal 27× the median. The threshold clock does **not**
regularise intrinsic-time waiting; the proposed third "structurally unreachable"
entry does not exist. Retracted as specified.

**Why (conjecture — untested).** The engine mixes two regimes BM lacks: ratchety
trending episodes cross δ fast; range-bound episodes (momentum at tick scale,
reversion at coarse scale) trap the price and take an order of magnitude longer. A
fast/slow mixture *is* heavy-tailed durations. *Prediction:* conditioning
durations on the episode's net drift splits the distribution into two narrow
components.

**The reframe this buys.** The scorecard scores volatility clustering FAIL —
measured as ACF(|r|) in *physical* time. Duration mixing at large δ is what
volatility clustering *looks like in intrinsic time*. If it survives seeds and a
drift-stratified control, level 0 contains a seed of temporal clustering the
physical-time statistic cannot see — softening one FAIL and sharpening what the
level-1 actor must add (jumps and depth, yes; temporal heterogeneity, apparently
not entirely). **Caveats:** 42-vs-14 events at the interesting δ; single seed; feed
drifted (lnp −4.03); ≥10 seeds + drift-stratified control before leaning on it.

**Score this session (§N + §D):** n_open — 1 supported (moderate inventory,
replicated), 1 unresolved-with-cause (path confound, named); durations — 2
falsified by their own registered falsifier, 1 reframe gained.

---

# §S — the short-stranding asymmetry (P1/P2/P3, arms, resolution)

HANDOFF-master §8. The full arc: phenomenon → cause confirmed → bug-vs-feature
split → impossibility triangle → home-close resolution. Base arm unless noted:
`n=150, T=40k, c=0.004, f=0.5, x_accounting=True, log_thresholds=True,
symmetric_solvency=True`, seeds 1–10. Instrumentation bit-verified against the
unmodified engine.

## S.1 The phenomenon

Under quantity-close, shorts strand in un-closeable open positions ~20:1 vs longs
(counts scale with n, ratio does not). Distinguish **open** (any |pos| > 0) from
**stuck** (`closing=True` and unfillable) — the distinction carries the story.

## S.2 P1 — cause confirmation: CONFIRMED and sharpened (10 seeds)

> *Stuck agents are almost entirely shorts, each with price ≫ entry x̄ and held
> EUR below the cover cost.*

Across seeds: stuck L = 0.7 ± 0.8, stuck S = 19.3 ± 14.8, pooled ratio **≈ 28:1**.
**0 of 193 stuck shorts could afford their cover at p_final.** Sharper than
predicted: stuck shorts hold **machine-zero EUR** (max 1.4e-14), and 167/193 have
*negative* residual x̄ (they laid out more EUR in partial covers than the entry
brought in). Recruitment rides upward price excursions.

## S.3 P2 — long self-funding: CONFIRMED (exactly zero)

`L_funding = 0` in 10/10 seeds. A long's BTC balance can never fall below its open
position, so the sell-side clamp cannot bite. **P2b:** stuck shorts fail closes
~50/50 funding/liquidity by attempt, *same agents in both sets* — once EUR is gone
they alternate "asks exist but I can't pay" and "no asks". Long close-failures are
ubiquitous but 100% liquidity-type and transient (droughts self-heal; funding
exhaustion does not). This is why the asymmetry is **persistent**: the long failure
mode mean-reverts, the short one is absorbing.

## S.4 Stranding is an absorbing state

**`stuck_short` never decrements in 10 × 40k ticks.** The oscillation earlier seen
was in the *open* count (healthy positions cycling through TP); the stuck subset
only ratchets up. On the first SL breach where cover cost > held EUR, `_fire_close`
spends the agent's **entire** EUR balance on a partial cover at run-up prices, then
re-fires every tick — EUR ≈ 0 forever, so even a full price collapse can't unstick
it. The open-not-stuck counts are side-symmetric (L 1.2 vs S 1.0): **the entire
open-position asymmetry is the stuck subset.**

## S.5 Mirror caveat & P3 (deferred)

`mirror=True` is dead code in the X-accounting config (open_btc returns before the
mirror branch); run with `x_accounting=False`. The mirror world is *broken, not
mirrored* (fails `system_x0`, collapses to lnp ≈ −34, the §7 cap exists only in
the X branch). The **legacy arm** (valid) keeps stranding on the shorts —
consistent with the mechanism living in *close direction*, independent of sizing.
**P3 (deferred):** analytic argument — under a genuine relabel (EUR↔BTC, p→1/p,
long↔short) the agent that must *acquire the matched quantity* to close is again
the relabeled "short". The structural suspect is **BTC-quantity matching**;
decisive test is an EUR-quantity-matched variant. *Prediction:* stranding moves to
the longs. Not run.

## S.6 Bug or feature — the evidence splits it cleanly

- **Constraint = feature.** A margin-free spot short genuinely cannot buy back what
  it cannot pay for; 193/193 unaffordable covers confirm the one-sided funding
  constraint. No sizing/gauge flag reaches it.
- **Absorbing character = rule-induced.** Manufactured by the "market-buy with your
  whole EUR balance every tick" spend policy, which converts a *temporary*
  affordability shortfall into *permanent* stranding by burning all EUR at the
  worst prices. Signature: EUR ≡ 0, residual x̄ < 0, zero recoveries. Conservative
  alternatives (wait for full affordability; rest a reduce-only limit) leave the
  constraint intact and remove the ratchet — characterized, not patched.

## S.7 sl_mode arms — the impossibility triangle (10 seeds × 4 arms)

| arm | stuckS | stuckL | drainage/run | lnp | 10-seed sign | x-share |
|---|---|---|---|---|---|---|
| market (v2) | 20.2±16.3 | 0.4±0.9 | 0.5 | −1.80±0.96 | 9/10 neg | 0.5045±0.021 |
| wait | 19.0±15.8 | 0.6±1.3 | 1.5 | −2.20±0.99 | 10/10 neg | 0.5152±0.025 |
| slimit | 105±69* | 47±68* | **384** | −6.0±14.3 | 3/10 neg | 0.5005±0.064 |
| nosl | 117±27 | 149±2 | — | −7.9±8.8 | 9/10 neg | 0.3908±0.060 |

\* bimodal: 7 seeds end all-shorts-stuck, 3 all-longs-stuck.

- **wait: not a fix** — occupancy unchanged, the burn merely gated (affordability
  checked at pre-walk price, the walk pays more). F4/F5 falsified for this arm.
- **slimit: fixes what it aimed at, reveals the trade-off** — EUR burn gone (stuck
  shorts hold 396–753 EUR), stranding recoverable (~384 drainage/run),
  **symmetry restored** (corr +0.93; up-runs strand shorts, down-runs strand longs;
  x-share 0.5005). *But* committed closers park on resting limits, cannot re-enter
  (pressure accrues only when flat), the population drains, and whole tribes lock
  at 150/150 while the price runs unbounded. The non-collapsed slimit paths are
  *calmer* — the SL market cascades were most of the volatility.
- **nosl: identifies the stabiliser** — with no SL, everyone soaks into underwater
  opens waiting for TP, activity dies, price runs to lnp −30. Worse on every metric.
  **Forced SL exits recycle agents into flow; recycling bounds the price.**

**The triangle.** A committed close can have at most two of: (1) forced execution
(recycles, bounds price — but the buyer of last resort is the agent's own wallet:
one-sided burn) = market; (2) spend-boundedness (solvent, symmetric — but parked
agents destabilise) = slimit; (3) tribe symmetry. market picks 1+solvency, gives
up 3; slimit picks 2+3, gives up 1; nosl gives up forced exits and is dominated.
The missing corner (forced execution *and* symmetry) needs an external balance
sheet — the house maker.

## S.8 V4 resolution — home-quantity closes (10 seeds)

`close_mode="home"`: each tribe closes by delivering what it holds (long surrenders
coins; short spends entry-EUR as a spend order). Load-bearing implementation notes:
coins must be banked as coins (new `realized_base` in BTC, marked at live price —
a frozen-EUR mark desyncs zero-sum when p moves); even dust coins dropped at settle
break zero-sum once p wanders 20+ e-folds; the zero-sum check itself was rewritten
in the X gauge (`|net|/√p ≤ 1e-9·K`) — same "read in X, never EUR" lesson applied
to the test battery.

Results (H1–H3 confirmed): **stranding gone** (stuck 0–3 both sides, pure transient
churn, no lockups, no EUR burn); **drift dead** (lnp +3.1 ± 2.9 SE, 4/10 neg vs
market −1.80, 9/10); **x-share = 0.50008 ± 0.00027** (two orders tighter than
market's ±0.02). Trade-off moved not hidden: with no forced-loss channel the price
walks freely (|lnp| to 20+), so the level is unanchored and diffuses — that is what
parameter choice must now control.

## S.9 Cont (2001) scorecard on the home arm & the parameter gradient

Baseline (n=150, c=0.004) fails most: ACF(r) lag-1 = +0.17 (momentum), no |r|
clustering, zero excess kurtosis. The flow-dominated corner (n=500, c=0.02) is
closest to real: ACF(r) L1 ≈ +0.01, genuine |r| clustering, kurtosis growing under
aggregation to ~3. Two honest gaps: medium-lag momentum (SL-cascade trend-following
— a feature to study, not remove) and sub-Gaussian tails at tick scale (the "tick"
is a matching cycle, not a trade tick; market-like scale is m≈25–125). q cancels out
under q-scaling (impact = flow/depth, both ∝ 1/q). Symmetry is parameter-robust
(x-share 0.500 and direction-covariant transient stranding in every arm).

## S.10 The final bug-or-feature verdict

The stranding asymmetry was a **modeling convention** (coin-quantity-fixed exits),
not a bug and not an intrinsic property of spot markets. The home-close world is
the defensible symmetric null; the quantity-close world is a **treatment** — switch
`close_mode="quantity"` back on to study squeezes, stranding, and cover-driven
drift against a clean baseline. Reintroducing quantity as a continuous dial
(fraction of quantity-obligated shorts) is the way to watch stranding/drift turn on
continuously.

---

# §V — the CLOB arm (rest+impatience): instability, drift, fat tails

The `run_single` default arm (n=500, tp=0.01, sl=0.02, entry=rest,
hold_fires_close=True, close=home). Detailed records behind HANDOFF-master §4.9
and §5.4. All runs pass every sanity check; all conserve.

## V.1 Direction is an unstable degree of freedom (not a drift)

Same config, three seeds: p_final = 0.031 (s1), 0.029 (s42), **and ~10–20 (a
third seed, up-run)**. Both directions under identical rules → not structural. The
price wanders near x_0 then breaks and runs away (flat-then-break on every seed,
either sign). "Prices always fall" RETRACTED — two-seed artifact. It is a
symmetry-breaking instability: unpinned in level *and* unstable in direction.

## V.2 Drift decomposition — who pushes (`exp_drift_decomp.py`)

Exact attribution (category sums = total ln-drift to the digit). Full 150k, s42
(down), sl=2tp, by role: **SL −243.5**, entry +223.5 (near-perfect wash, net/gross
≈ 0.98 each side), impatience +16.4. SL detail: long-cover (sell) net −307 / 30k
events; short-cover (buy) net +78 / 48k — long-covers ~6× harder per event.

**Emergent, not structural** — per-event SL impact by time-quarter as price falls:
ratio |L/S| = 1.1 (early) → 4.1 (late). Stops start *symmetric*; the asymmetry
grows with the fall. Depth-dies-with-the-move feedback amplifies a noise-seeded
break. Whack-a-mole: at sl=tp the SL net flips +16.7 but impatience takes over
(−21.4) — no symmetric knob restores it (the instability regenerates in the
unpinned channel). Confirmation pending: ≥10-seed sign tally.

## V.3 Genuine drift-independent fat tails (`exp_detrend_tail.py`)

Two seeds each, full 150k, local rolling-median detrend (windows 25–751), tail
survives with residual sign-ACF → ~0.5:

| arm | s1 P(\|r\|>4sd) | s42 P(\|r\|>4sd) | resid q1 |
|---|---|---|---|
| sl=2tp | 1.22–1.26e-2 | 1.26–1.30e-2 | 0.34–0.36 |
| sl=tp  | 0.43–0.47e-2 | 0.54–0.56e-2 | 0.42–0.48 |

P(|r|>5sd) ≈ P(|r|>4sd) (heavy, not fattened-Gaussian). Second route to fat tails,
distinct from §T's roundness hierarchy. Mechanism partially split: CLOB entry
(marketable-to-touch) is the ~0.5% baseline; sl=2tp cover cascade ~doubles it to
~1.2%. **Method note that flipped the earlier read:** constant-mean detrend
manufactures fake persistence on a trending-then-reverting series (raw q1≈0.47 →
0.88); only the *local* detrend is trustworthy. Open: ioc×{sl,2tp} tail cell to
finish the entry-vs-stop attribution.

## V.4 Overshoot: mean is drift, median is BM (`os_median`)

Across arms the mean ⟨ω⟩/δ runs 1–8; the **median-ω/δ sits at ~0.6–0.9 ≈ BM's
0.70** everywhere. BM baseline mean/median ≈ 1.5; the engine's mean/median ≫ 1.5
is the trend, not illiquidity. sl=tp CLOB gives a clean-looking mean law
(⟨ω⟩/δ=1.38, R²=0.996) but that is *lower drift*, not more BM-like — its median is
the check. Retire fitted E_os; report the median.

---

## Files & artifacts

Experiments (predictions in headers): `exp_tpcluster.py`, `exp_nopen.py`,
`exp_durations.py`, `exp_stranding.py`, `exp_inventory.py`,
`exp_oscillator_phase.py` (registered), `exp_detrend_tail.py` (§V.3),
`exp_drift_decomp.py` (§V.2).
Artifacts: `tpcluster.jsonl`, `nopen.jsonl`, `stranding_*` JSON (base 1–10,
legacy, mirror; `stranding_v2/`, `_v3/`, `_v4/`), `stranding_seeds.jsonl`.
Instrument + guards: `dc_analysis.py` (now with `os_median`),
`test_benchmarks.py` / `benchmarks.json` (10 benchmarks, green this session),
`test_bm.py`, portable-init test.
