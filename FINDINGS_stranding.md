# The Alpha Engine — Findings: the short-stranding asymmetry (P1/P2 resolved)

Follow-up to `HANDOFF_stranding.md`. Every number below is measured on 10 seeds
(base arm) unless noted. Predictions from the handoff are quoted, then scored.
Engine instrumentation is additive and verified **bit-identical** to the
unmodified engine (same `p_int` series, seed 42, T=2k A/B).

Setup: base arm = `n=150, T=40_000, c=0.004, f=0.5, x_accounting=True,
log_thresholds=True, symmetric_solvency=True`, seeds 1–10. Plus `legacy`
(`x_accounting=False`) and `mirror` (`x_accounting=False, mirror=True`) arms,
seeds {42, 1}, for the mirror-caveat check. All base and legacy runs pass every
sanity check. Artifacts: `stranding_{arm}_{seed}.json` (per-agent end-of-run
dump, close-fail counters, full `p_int`/`open_*`/`stuck_*` series);
figure `stranding_p1p2.png`; analysis in `analyze_stranding.py`.

New per-tick series distinguish **open** (any |pos.b| > 0) from **stuck**
(`closing=True` and unfillable) — the handoff's counts conflated these, and the
distinction turns out to carry most of the story.

---

## 1. P1 — cause confirmation: **CONFIRMED, and sharpened**

> *Prediction: stranded agents are almost entirely shorts, each with
> price ≫ entry x̄ and held EUR below the cover cost.*

| seed | lnp | open L/S | stuck L/S | stuck shorts able to afford cover |
|---|---|---|---|---|
| 1 | −1.66 | 1/31 | 1/31 | 0/31 |
| 2 | −3.12 | 2/8 | 2/8 | 0/8 |
| 3 | −0.04 | 2/53 | 1/52 | 0/52 |
| 4 | −0.99 | 2/27 | 0/26 | 0/26 |
| 5 | −3.02 | 1/19 | 0/16 | 0/16 |
| 6 | −2.04 | 2/2 | 0/2 | 0/2 |
| 7 | −0.69 | 3/5 | 2/3 | 0/3 |
| 8 | −2.11 | 2/30 | 1/30 | 0/30 |
| 9 | −1.92 | 2/18 | 0/17 | 0/17 |
| 10 | −1.18 | 2/10 | 0/8 | 0/8 |

Across seeds: stuck L = 0.7 ± 0.8, stuck S = 19.3 ± 14.8, pooled ratio **≈ 28:1**.
**0 of 193** stuck shorts could afford their cover at `p_final`. No falsifier
fired: stuck longs are 0–2 per run (and are a different, transient phenomenon —
see §3), and not one stuck short was solvent for its buyback.

**Sharpening — the fingerprint is stronger than predicted.** Stuck shorts do not
merely hold *insufficient* EUR; they hold **machine zero** (max held EUR over
all 193 agents: 1.4e−14). And in 167/193 the residual position's x̄ is
*negative* — they have already laid out more EUR in partial covers than the
entry ever brought in. The "p ≫ x̄" part of the prediction is therefore not
directly checkable against the *residual* x̄ (it is blended with partial covers
at high prices); the recruitment panel of `stranding_p1p2.png` shows the
mechanism instead: stuck-short recruitment happens on upward price excursions
(seed 3: recruitment 0→52 rides lnp climbing from −4 to +2).

## 2. P2 — long self-funding: **CONFIRMED (exactly zero)**

> *Prediction: long closes partially filled due to the `btc_budget` clamp ~ 0.*

`L_funding = 0` in 10/10 seeds (and in both legacy seeds). Longs are never
funding-clamped on a close. The structural reading holds: a long's BTC balance
can never fall below its open position, so the clamp cannot bite.

## 3. P2b (extension) — funding vs liquidity: **both, and the split explains persistence**

Close-fail attempts were classified by *why* the walk stopped: **funding**
(budget clamp bit while opposite depth remained) vs **liquidity** (opposite
book side exhausted).

- **Stuck shorts fail both, ~50/50 by attempt count, and it is the *same*
  agents in both sets** (unique-agent sets identical, every seed). Once EUR is
  gone, a stuck short alternates between "asks exist but I can buy nothing"
  and "no asks at all".
- **Long close failures exist and are ubiquitous — but 100% liquidity-type and
  transient.** Essentially every long agent (~149/150 per run) fails at least
  one close attempt on an empty bid side, ~8–19k attempts per run. Yet only
  1–3 longs are still open at end. Liquidity droughts self-heal (depth
  returns); funding exhaustion does not.

This resolves why the asymmetry is *persistent* rather than statistical: the
long failure mode is mean-reverting, the short failure mode is absorbing.

## 4. NEW — stranding is an absorbing state (resolves §2's UNVERIFIED item)

> *Handoff §2, UNVERIFIED: whether the queue reliably drains to ~0, or settles
> at a level. "The runs show oscillation, not a clean decay."*

Measured: **`stuck_short` never decreases. Not once, in any of 10 × 40k
ticks** (0 decrements against 8–52 increments per run; all stuck shorts alive
at end, so no bankruptcy purges either). The oscillation the handoff saw was in
the *open* count — healthy positions cycling through TP — not the stuck subset.
The open-not-stuck counts are side-symmetric (L 1.2 vs S 1.0 mean): **the
entire open-position asymmetry is the stuck subset.**

The ratchet mechanism, read off the instrumented runs: on the first SL breach
where cover cost > held EUR, `_fire_close` spends the agent's **entire** EUR
balance on a partial cover at the run-up prices (`eur_budget = max(a.eur, 0)`,
re-fired every tick). After that first attempt the agent has EUR ≈ 0 *forever* —
even a full price collapse back below entry cannot unstick it, because it has
nothing left to buy with. Ten seeds ended with lnp between −0.04 and −3.12
(price *fell*, covers became cheap) and not one stranded short recovered.

## 5. Mirror caveat check: **caveat confirmed, for a sharper reason than expected**

> *Handoff §4 caveat: `mirror=True` is probably NOT the swap test; verify the
> expectation that stranding stays on the shorts.*

Two findings:

1. **In the committed X-accounting config, `mirror` is dead code.**
   `open_btc` returns from the `x_accounting` branch before the `mirror` branch
   is reached. Any mirror A/B must be run with `x_accounting=False`.
2. **The mirror world is broken, not mirrored.** Both mirror seeds **fail the
   `system_x0` monotone conservation check**, collapse to lnp ≈ −34.5, and end
   with all 150 longs open (143–145 "stuck", millions of budget-clamped close
   attempts — meaning longs' BTC balances went *below* their positions, which
   §2 showed is structurally impossible in a conserving run). Root cause: the
   §7 invariant cap (`min(size, eur/price)` / `min(size, btc)`) **exists only
   inside the `x_accounting` branch** of `open_btc`. The legacy/mirror sizing
   paths are uncapped, so the balanced entry crossing (which never clamps)
   drives balances negative — exactly the leak §7 warned about, still present
   outside the X branch.

So `mirror=True` results are uninterpretable as a symmetry probe — the caveat
was right, with prejudice. The **legacy arm** (valid: all checks pass) shows
stranding still on the shorts (stuck L/S = 0/1 and 2/11), consistent with the
mechanism living in **close direction**, independent of sizing convention.

**P3 status (deferred by agreement).** Analytic argument: under a genuine
relabel (EUR↔BTC, p→1/p, long↔short), the agent that must *acquire the matched
quantity* to close is again the relabeled "short" — stranding attaches to
whichever tribe closes by buying the quantity the book matches in. The
structural suspect is therefore **BTC-quantity matching** (handoff §7, last
bullet). The decisive empirical test is an engine variant that matches in EUR
quantity; prediction, stated now: stranding moves to the longs. Not run.

## 6. Bug or feature (handoff §5) — the evidence splits it cleanly in two

- **Intrinsic (feature):** a margin-free spot short genuinely cannot buy back
  what it cannot pay for. P1's 193/193 unaffordable covers confirm the funding
  constraint is real and one-sided. No sizing/gauge flag reaches it. This part
  is the honest property of spot shorting under base-quantity matching.
- **Rule-induced (policy choice, arguably a bug):** the *absorbing* character is
  not intrinsic. It is manufactured by the specific cover rule — "market-buy
  with your entire EUR balance, every tick, at whatever the asks charge". That
  rule converts a *temporary* affordability shortfall into *permanent*
  stranding by burning all EUR at the worst prices. Conservative alternatives
  (wait until the full cover is affordable; or rest a reduce-only limit at the
  affordable price) would leave the funding constraint intact while removing
  the ratchet. **Per §5, none of these were implemented** — the finding is
  characterized, not patched. But the decision is now sharper than "bug vs
  feature": *the constraint is a feature; the all-in drain is a separable rule
  choice with a measurable signature (EUR ≡ 0, x̄ < 0, zero recoveries).*

The "symmetric null" restatement the handoff proposed should additionally note:
the stranded mass is an **absorbing** residual under the current cover rule,
so its size is path-cumulative, not stationary.

## 7. Side-finding — the f=0.5 drift claim looks wrong at T=40k

lnp over the 10 base seeds: **mean −1.68, sd 0.98 (SE 0.31), 10/10 negative.**
That is ~5σ from zero, against the handoff §1 claim "drift statistically
consistent with zero" (measured there at other horizons/seeds, e.g. T=8k × 6
seeds). Possibly connected to this thread: every stranded short has pushed its
entire EUR into the book and then gone inert, a one-way EUR→(partial BTC)
conversion that removes future buy-side pressure. Not investigated further —
this deserves its own prediction-first thread before anything is concluded.

## 8. Contaminated-measurement note (handoff §1) — now quantifiable

The stranded shorts' unrealized mark is exactly recoverable from the dumps
(`pos_b`, `xbar`, `p_final` per agent), so the EUR "short loss" panels can now
be decomposed into realized transfer vs stranded mark per run. Not done here;
one ~10-line pass over the artifacts.

## 9. What must not regress (additions to handoff §7)

- The funding/liquidity close-fail counters and `open_*`/`stuck_*`/
  `long_x_share` series are now committed instrumentation in `simulation.py`
  (additive; bit-identity verified). Keep them.
- **The §7 cap gap:** the entry-size cap exists only in the `x_accounting`
  branch. Any run with `x_accounting=False` is exposed to the conservation
  leak (mirror arm reproduces it). Either extend the cap to all sizing
  branches or treat non-X arms as diagnostic-only.
- `stuck_*` (not `open_*`) is the stranding observable. Open counts include
  healthy positions and are side-symmetric once the stuck subset is removed.

---

# ADDENDUM — post-fix A/B (fixed engine, same 10 seeds)

The results above were run on the **pre-fix** engine (no cover-gathering cap, no
solvency check, raw re-fire threshold). The fixed engine (HANDOFF_stranding-v2
§7: SL-cover capped at `eur/p_prev` at gathering, long mirror `min(qty, btc)`,
scaled `1e-9/x_0` threshold, per-agent solvency in the sanity battery) was
re-instrumented identically (bit-checked against the unmodified fixed engine)
and re-run on the same 10 seeds. Artifacts in `stranding_v2/`.

## A1. What the fix changes — and what it doesn't

| quantity (10 seeds) | pre-fix | post-fix |
|---|---|---|
| stuck shorts, mean ± sd | 19.3 ± 14.8 | 20.2 ± 16.3 |
| stuck longs, mean ± sd | 0.7 ± 0.8 | 0.4 ± 0.9 |
| pooled ratio | 28:1 | 50:1 |
| stuck shorts able to afford cover | 0/193 | 0/202 |
| min stuck-short EUR | **−16.2** (insolvent) | −1.1e−13 (solvent) |
| sanity checks | solvency violated (9 agents) | **all pass** |
| `stuck_short` decrements in 400k ticks | 0 | 5 (all 1–2-tick transients settling, no deaths) |
| corr(stuck_short_end, lnp) across seeds | +0.43 | **+0.84** |
| lnp mean ± sd | −1.68 ± 0.98 (10/10 neg) | −1.80 ± 0.96 (9/10 neg) |

**Stranding survives the fix unchanged** — the leak was a boundary symptom, as
the parallel thread concluded. The v1 thread's headline numbers replicate on
this engine (corr +0.84 exactly; magnitude and direction of the counts).

## A2. The drainage claim does NOT replicate — reconciliation

The v1 thread's §5 verdict rested on "it drains iff the price comes back"
(corr +0.84). The correlation replicates; the *reading* of it does not. On the
fixed engine, long-stranded shorts still essentially never recover: 5
decrements of `stuck_short` in 400k ticks, every one a 1–2-tick transient
(fresh SL settling promptly), zero recoveries of long-stranded agents, zero
bankruptcy purges. The +0.84 is a **recruitment-side** correlation — runs whose
price ends higher stranded more shorts along the way — not evidence of
drainage. Likewise v2-handoff §2's "oscillates down to 18" was measured on
`open_short` (healthy positions cycling through TP), not the stuck subset;
`stuck_*` vs `open_*` resolves it.

Mechanism post-fix: the gathering cap keeps the agent *solvent* (EUR ≥ 0) but
the cover path still spends the full EUR balance — the capped balanced-crossing
slice at trigger, then `_fire_close` re-fires walking asks with
`eur_budget = all held EUR` every tick. EUR still hits zero; zero EUR with no
income is still absorbing. **§2's UNVERIFIED item is now answered on both
engines: the queue does not drain.** The absorbing character survives the
solvency fix because it lives in the *spend policy*, not the leak.

## A3. Taxonomy discrepancy with the v1 thread — classifier definitions

v1: "all short close-failures are budget-bound (100%)". This instrumentation:
~50/50 funding/liquidity *per attempt*, with **identical agent sets** in both
classes — stuck shorts alternate between "asks present, no EUR" and "no asks"
tick by tick. Both classifiers agree on the substance (every stuck short is
wallet-bound; its EUR ≈ 0); they differ on how a re-fire against a momentarily
empty ask side is labelled (budget-at-submission vs walk-stop cause). Not a
contradiction — but the 50/50 split is the finer instrument, and it shows the
short side *also* faces intermittent depth droughts on top of the funding wall.

## A4. Revised §5/§6 verdict

- **Constraint = feature** (unchanged): 202/202 stuck shorts genuinely cannot
  fund their buyback; margin-free spot shorting is one-sidedly exposed. Solvent
  now, so the statement is clean.
- **Permanence = rule-induced** (revised against v1's "bounded, price-coupled"):
  under the current all-in spend policy, stranding is absorbing on both
  engines. The honest restated null: *symmetric in numeraire-covariant wealth,
  with a one-sided, path-cumulative, absorbing short-stranding residual whose
  size is set by the price path's upward excursions (corr +0.84 with final
  lnp).* "Bounded and price-coupled" describes recruitment, not occupancy.
- The non-absorbing conservative alternatives (spend nothing until the full
  cover is affordable; rest a reduce-only limit) remain unimplemented by
  design — implementing one is now a *decision*, with the measured cost known:
  ~13% of the short tribe locked by T=40k at these parameters.
- **Drift**: robust to the fix (−1.80 ± 0.30 SE, 9/10 negative). The f=0.5
  "consistent with zero" claim does not survive 10 seeds at T=40k on either
  engine. Next thread: T-scaling (mean ∝ T vs sd ∝ √T) to separate systematic
  tilt from slow random walk, and its coupling to the stranded shorts' one-way
  EUR spend.

---

# REPLICATION NOTE — independent investigation, bit-level agreement

A separately-run investigation (`stranding_seeds.jsonl`, seeds 1–10 + 42, same
v2 fixed engine — its uploaded `simulation.py`/`analysis.py` diff against ours
shows only our instrumentation additions) was cross-checked against the
post-fix batch above. **Every shared quantity matches to the last bit on all
10 common seeds**: stranded S and L counts, lnp, x_share_end, and min-EUR
(including the exact −1.137e-13 on seed 1). Two independent instrumentation
implementations, zero divergence — the decimal/fsum portability engineering
does what it promises, and both toolchains are validated against each other.

New from that dataset:
- **Seed 42**: stranded S/L = 21/0, lnp = −1.43, consistent with the
  distribution (making it 11 seeds).
- **peak vs end open_short**: a consistent gap of 3–11 agents (e.g. 30→20,
  15→4). This quantifies the layer that misled v1's "oscillates down" reading:
  the decline from peak is the *healthy* churn (open − stuck), sitting on a
  stuck floor that never drains (the series-level decrement count above). The
  two views are now fully reconciled: open_short breathes; stuck_short
  ratchets.

# V3 — THE FIX ATTEMPT (sl_mode arms; 10 seeds × 4 arms)

Directive: fix the stranding, get symmetry back. Implemented behind
`cfg.sl_mode` (`"market"` = v2, bit-identical); predictions F1–F5 stated in
`stranding_v3/exp_stranding.py` before running. All arms pass every
conservation + solvency check. Figure: `stranding_fix_arms.png`.

Arms: **market** (v2 baseline) | **wait** (market cover only when the full
cover is affordable at the current price) | **slimit** (SL fires a reduce-only
*limit at the stop level*; fills what crosses, rests the remainder — no
book-walking, no EUR spend while waiting) | **nosl** (`sl_enabled=False`,
TP-only control).

## V3.1 Results (10 seeds each, n=150, T=40k)

| arm | stuckS | stuckL | drainage/run | lnp | 10-seed lnp sign | x-share | corr(lnp, S−L open) |
|---|---|---|---|---|---|---|---|
| market | 20.2±16.3 | 0.4±0.9 | 0.5 | −1.80±0.96 | 9/10 neg | 0.5045±0.021 | +0.84 |
| wait | 19.0±15.8 | 0.6±1.3 | 1.5 | −2.20±0.99 | 10/10 neg | 0.5152±0.025 | +0.40 |
| slimit | 105±69* | 47±68* | **384** | −6.0±14.3 | 3/10 neg | 0.5005±0.064 | **+0.93** |
| nosl (open counts) | 117±27 | 149±2 | — | −7.9±8.8 | 9/10 neg | 0.3908±0.060 | +0.94 |

\* bimodal: 7 seeds end with all 150 *shorts* stuck (price ran up), 3 with all
150 *longs* stuck (price collapsed, lnp −6/−31/−35).

**wait: not a fix.** Occupancy unchanged; the burn is merely gated — the
affordability check is at the pre-walk price, the walk pays more, and stuck
shorts still end at EUR ≈ 0 (F4/F5 falsified for this arm).

**slimit: fixes exactly what it aimed at — and reveals the real trade-off.**
- The EUR burn is gone: stuck shorts hold 396–753 EUR (F5 confirmed).
- Stranding is *recoverable*: ~384 drainage events per run vs 0.5 (real
  drainage at last).
- **Symmetry is back in the covariant sense**: stranding attaches to whichever
  tribe the price moved against (corr +0.93; 7 up-runs strand shorts, 3
  down-runs strand longs), instead of shorts-only-even-when-price-falls.
  Mean x-share dead on 0.5005.
- **But F1's occupancy collapse is falsified, and the stated degeneration
  falsifier fired**: committed closers park on resting limits, cannot re-enter
  (pressure accrues only when flat), the active population drains, flow goes
  one-sided, and whole tribes lock up at 150/150 while the price runs
  unboundedly. Also visible: the non-collapsed slimit price paths are far
  *calmer* than market's — the SL market cascades were most of the
  volatility.

**nosl (control): identifies the stabiliser.** With no SL at all, everyone
soaks into underwater open positions waiting for TP (149/150 longs open),
activity dies, and prices run to lnp −30. Worse than any SL arm on every
metric, including x-share (0.39). **Forced SL exits are what recycle agents
into the flow; recycling is what keeps the price bounded.**

## V3.2 The structural conclusion — an impossibility triangle

In a margin-free spot world with one position per agent, a committed close can
be given at most two of:

1. **Forced execution** (exit happens now, at whatever price) → recycles
   agents, bounds the price — but the buyer of last resort is the agent's own
   EUR wallet: one-sided burn, absorbing short-stranding. *(= market)*
2. **Spend-boundedness** (never pay more than the stop level / never drain
   the wallet) → solvent, symmetric — but unexecuted closes park the agent,
   and parked agents destabilise the population. *(= slimit)*
3. **Tribe symmetry** (stranding direction-covariant, not short-specific).

market picks 1+solvency and gives up 3; slimit picks 2+3 and gives up 1; nosl
gives up forced exits entirely and is dominated. The missing corner —
forced execution *and* symmetry — requires an external balance sheet (a
liquidator/house-funded cover), i.e. exactly the §5-warned bolt-on. That is
now a *characterized decision*, not a patch: its price is known (counterparty
risk at the house), and what it buys is known (the market arm's stability with
the slimit arm's symmetry).

## V3.3 Recommendation

- For the **"symmetric null" claim**: use `sl_mode="limit"`. The claim becomes
  honest: symmetric in drift-covariant stranding (corr +0.93, x-share 0.5005),
  solvent, recoverable — with the *measured* caveat that the substrate is
  metastable (tribe-lockup absorbing states; 10/10 seeds locked by T=40k at
  these parameters). Worth checking whether lockup frequency falls with n, c,
  or tighter sl.
- For a **stable trading substrate**: keep `sl_mode="market"` and carry the
  stranding residual as a quantified, one-sided cost (~13% of shorts absorbed
  by T=40k, EUR-burned, never recovering).
- The drift finding sharpens: slimit flips lnp to 3/10 negative (mean of the
  7 non-collapsed runs ≈ +1.6), so **the systematic negative drift of the
  market arm is largely produced by the SL market-cover mechanics**, not by
  the trading substrate itself. The drift thread and the stranding thread are
  the same thread.

---

# V4 — HOME-QUANTITY CLOSES: the symmetric toy model (committed direction)

Directive: adopt the design where each tribe closes by delivering the quantity
it HOLDS — long surrenders its coins, short spends its entry-EUR proceeds (a
spend order). `cfg.close_mode="home"` (`"quantity"` = v3, bit-identical).
Engine: `stranding_v4/`. Predictions H1–H4 stated in `exp_stranding.py` first.

## V4.1 Implementation notes (all load-bearing)

- Short exits are spend orders: TP rests BUY size q/p_tp at p_tp (spends
  exactly the remaining entry-EUR under partial fills); SL/market covers carry
  `eur_budget = min(eur, pos.q)` as the true terminator. Settle tests the HOME
  quantity (q≈0 for shorts), not the coin tally.
- **Coins must be banked as coins.** Two accounting bugs found and fixed en
  route: (1) a settled home-short's coin residual banked as a frozen EUR mark
  desyncs zero-sum when p moves — new `Agent.realized_base` (BTC), marked at
  the live price in `total_pnl`; (2) even DUST coins dropped at settle break
  zero-sum macroscopically once p wanders 20+ e-folds (1e-9 BTC at p=1e9 is
  macroscopic EUR) — home mode banks b and q exactly at every settle.
- **The zero-sum sanity check itself was a moving-ruler artifact.** The
  residual is float coin-dust (~1e-11 BTC, wallet conservation holds to 1e-10
  on 1e6 totals); in EUR it scales with p and false-alarms in wide-excursion
  worlds. Rewritten in the X gauge: |net|/√p ≤ 1e-9·K. Same lesson as §7's
  "read transfer in X, never EUR", now applied to the test battery.

## V4.2 Validation (10 seeds, n=150, T=40k) — H1–H3 all confirmed

- **Stranding is gone as a phenomenon**: stuck L/S at end = 0–3 both sides,
  18k up-transitions vs 15k down across the ensemble (pure transient churn,
  fully recoverable), no lockups, no EUR burn. All checks pass on all seeds.
- **Drift is dead**: lnp = +3.1 ± 2.9 SE, 4/10 negative (market arm:
  −1.80 ± 0.30, 9/10). H2 confirmed — the drift was the cover mechanics.
- **x-share = 0.50008 ± 0.00027** — pinned two orders of magnitude tighter
  than the market arm (±0.02). The symmetric null is finally symmetric.
- Trade-off moved, not hidden: with no forced-loss channel, the price walks
  freely — |lnp| excursions up to 20+ within a run (p spanned 1.6e-9…6.7e11
  in one seed). Nothing pathological (all conserving, all solvent), but the
  price scale is unanchored: nothing in the model pins a level, so it
  diffuses. That is what parameter choice must now control.

## V4.3 Stylized facts (Cont 2001 scorecard) and the parameter gradient

Baseline (n=150, c=0.004): fails most — ACF(r) lag-1 = **+0.17** (momentum,
should be ~0), no |r| clustering, zero excess kurtosis, sd(r) ≈ 7%/tick.
Sweep (3 seeds/arm, one knob each):

| arm | ACF(r) L1 | ACF\|r\| L10 | ACF\|r\| L250 | kurt m=1→125 | verdict |
|---|---|---|---|---|---|
| home n=150 c=.004 | +0.17 | +0.02 | +0.01 | 0.1 → 1.3 | AR(1) diffusion |
| home q=64 | +0.19 | +0.02 | +0.01 | 0.5 → 1.7 | **q cancels out** (impact = flow/depth, both ∝1/q) |
| home c=0.02 | −0.03 | +0.12 | +0.01 | −0.4 → 3.2 | clustering emerges |
| home n=500 | **+0.01** | **+0.16** | **+0.07** | −0.3 → 3.1 | closest to real |

The flow-dominated regime (many agents, fast clock) delivers: no lag-1 linear
autocorrelation, genuine volatility clustering with slow decay, and kurtosis
*growing* under aggregation to ~3. Two honest gaps vs real markets: (a)
medium-lag momentum ACF(r)~+0.1 at L20 (SL-cascade trend-following — possibly
a feature to study, not remove); (b) tails are sub-Gaussian at tick scale and
fatten only under aggregation — the model "tick" behaves like a matching
cycle, not a trade tick, so the market-like scale is m≈25–125 ticks. Symmetry
is parameter-robust: x-share 0.500 and direction-covariant transient stranding
in every arm (n=500 seeds: +lnp run stranded 25 shorts, −lnp run 22 longs).

## V4.4 Where this leaves the program

The v1 question "bug or feature" has its final answer: the stranding asymmetry
was a **modeling convention** (coin-quantity-fixed exits), not a bug and not
an intrinsic property of spot markets. The home-close world is the defensible
symmetric null; the quantity-close world is now a *treatment* — switch
`close_mode="quantity"` back on to study squeezes, stranding, and
cover-driven drift as phenomena against a clean baseline.

Open threads, in order: (1) tame the free diffusion (candidates: chartist/
fundamentalist anchoring, wealth-coupled sizing already present, tighter
tp/sl); (2) push the n=500/c=0.02 corner with ≥10 seeds and longer T for
load-bearing stylized-fact numbers; (3) the medium-lag momentum — measure,
don't patch; (4) reintroduce quantity-shorting as a dial (fraction of
quantity-obligated shorts) and watch stranding/drift turn back on
continuously.

## 10. Files

- `simulation.py` — instrumented engine (bit-identical dynamics)
- `exp_stranding.py` — arms/predictions/runner; `runner_ckpt.py` — sliced
  execution (bit-identical to straight runs, verified)
- `analyze_stranding.py` — the tables above; `stranding_p1p2.png` — figure
- `stranding_{base 1–10, legacy 42/1, mirror 42/1}.json` — full artifacts (pre-fix)
- `stranding_v2/` — fixed engine (v2 uploads) + same instrumentation,
  `stranding_base_{1–10}.json` post-fix artifacts
- `stranding_v3/` — sl_mode engine (config.py `sl_mode`, simulation.py step
  3/6 dispatch, agents.py `close_ref`; `"market"` bit-identical to v2),
  `stranding_{slimit,wait,nosl}_{1–10}.json`, `stranding_fix_arms.png`
- `stranding_v4/` — home-close engine (`close_mode`; quantity mode
  bit-identical to v3), X-gauge zero-sum check in analysis.py,
  `stranding_home2_{1–10}.json` (use home2, not the stale home artifacts:
  pre-exact-banking accounting, same dynamics), sweep artifacts
  `stranding_{homeq64,homec02,homen500}_*.json`, `stylized_facts.py`
