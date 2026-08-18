# EVALUATION — Block Parameter Scan

What each interchangeable block contributes to the null model's behaviour,
measured by switching every combination of the three blocks and comparing
against the frozen null.

**Engine**: `simulation_mvp.py` at commit `687e4e7` (bit-verified against
the reference engine). **Design**: full 2³ factorial over

    capital_dist : pareto | normal      (dice 1 — who gets the money)
    band_dist    : fixed  | normal      (the tp/sl price lattice)
    closing      : clock  | normal      (the timer exit)

at n = 400 per side, T = 30,000 ticks, seeds {9, 17, 23, 42} — 32 runs.
Every non-default block draws on its own RNG stream, so an arm differs from
the null *only* in the switched mechanism. The "normal" variants use the
config defaults (cv = 0.3 with floors); these define what "normal" means
throughout. Runner: `scan_mvp.py` → `scan_results.jsonl`; figures and
table: `scan_plots_mvp.py`.

**Arm code**: three letters, one per block, in the order above —
`P/N` capital, `F/N` bands, `C/N` closing. `PFC` is the frozen null;
`NNN` has all three blocks Gaussianized.

## Results

Across-seed means (4 seeds per arm; every run ended with all 800 agents
solvent):

| arm | \|ln drift\| | sd_rob | zero % | kurt m=1 | ACF\|r\| L1 | E_N | ⟨ω⟩/δ | trades |
|-----|--------:|-------:|------:|--------:|--------:|------:|-----:|------:|
| **PFC** (null) | 2.16 | 0.0105 | 30.4 | 2841 | 0.258 | −2.10 | 2.48 | 267k |
| NFC | 1.24 | 0.0139 | 25.8 | 1296 | 0.238 | −2.11 | 1.18 | 205k |
| PNC | 3.37 | 0.0005 | 20.7 |  434 | 0.467 | −1.08 | 2.33 | 209k |
| PFN | 2.08 | 0.0131 | 27.5 | 1370 | 0.258 | −1.77 | 1.75 | 275k |
| NNC | 2.23 | 0.0023 | 26.4 |  832 | 0.399 | −1.76 | 1.33 | 174k |
| NFN | 1.48 | 0.0142 | 28.5 |  999 | 0.203 | −1.84 | 1.45 | 199k |
| PNN | 3.90 | 0.0008 | 19.7 | 5737 | 0.350 | −1.44 | 2.18 | 223k |
| NNN | 2.11 | 0.0030 | 25.3 |   68 | 0.357 | −1.75 | 1.19 | 182k |

sd_rob = MAD-robust per-tick sd of returns. kurt = excess kurtosis of tick
returns (Gaussian = 0). E_N = directional-change count exponent (BM theory
−2). ⟨ω⟩/δ = mean overshoot ratio (BM ≈ 1). Figures:
`scan_prices_mvp_scan_n400_T30000.png` (price paths per arm),
`scan_stats_mvp_scan_n400_T30000.png` (per-seed measure strips).

## The headline: NNN

With Gaussian capital, Gaussian bands, and Gaussian holding times there is
**no power-law input anywhere in the model** — and the market still
produces excess kurtosis of 39–85 per seed, volatility clustering of
ACF(|r|) ≈ 0.36, and multi-e-fold price displacements. This closes the
cheapest objection to the null ("you fed in a Pareto, of course fat tails
come out"): Gaussianizing every input tames the tails roughly 40×, but
what remains is still violently non-Gaussian and can only come from the
order-book mechanics and the position lifecycle. The null's fat tails are
part inherited, part manufactured — and the manufactured part never goes
away.

## Block by block

**Capital (P→N) is the drift dial and the depth-texture dial.** Removing
the whales halves the price displacement (2.16 → 1.24 with bands fixed) —
the deck's dice-1 story, quantified. The subtler effect: it *raises* the
typical tick sd (0.0105 → 0.0139) while *lowering* kurtosis. Whales are
liquidity walls — their huge resting take-profits make most ticks small
(the market grinds against a wall) and rare ticks enormous (the wall
breaks). Gaussian capital homogenizes the book's granularity: bigger
typical moves, fewer monsters.

**Bands (F→N) is the most violent switch — it changes the dynamical
regime, not just the statistics.** The price panels show the null's noisy
wander replaced by smooth, near-deterministic ratchets: long
exponential-looking ramps punctuated by spike-and-relax events, with seeds
pairing off into committed up- and down-fates. Mechanically, heterogeneous
bands destroy the single tp-lattice (the null's "favourite step"), and the
small-band agents (floor 0.1·tp) churn micro-oscillations that collapse
the *typical* move 5–20× (sd_rob 0.0105 → 0.0005) while the large
structure persists — a scale mixture, which is exactly why clustering
jumps (0.26 → 0.47) and the DC-count exponent breaks hardest from BM
(−1.08 vs −2.10). It also *increases* drift (3.4–3.9, the largest in the
table): the lattice resonance was acting as a brake.

**Closing (C→N) is the gentlest switch.** Randomized holding times leave
drift and clustering nearly untouched (PFN ≈ PFC on both) and mildly
soften the tails and E_N (−2.10 → −1.77). The deterministic clock's
synchronization contributes to the null's character but is not
load-bearing — reassuring, since it is the most artificial-looking
ingredient.

**The blocks interact.** Capital-normal's drift-damping works only while
bands are fixed: NNC and NNN sit back at |drift| ≈ 2.2, because the
band-ratchet creates its own drift channel that homogenized capital cannot
offset.

## Caveats

Four seeds and T = 30k make the kurtosis *means* indicative rather than
conclusive: the estimator is itself heavy-tailed (the null's per-seed
values are 121 / 2954 / 3548 / 4743), so arm rankings by mean kurtosis
deserve suspicion; the robust statement is the *floor* — every one of the
32 runs stays ≥ ~39. The ⟨ω⟩/δ column is drift-inflated at this horizon
(the null's own value is 1.08 at T = 100k, not 2.48). The sd collapse
under bands-normal means the delta grids probe different absolute scales
per arm, so cross-arm E_N comparisons carry that caveat. And all arms
share the engine's known step-6 array-order asymmetry equally.

## Follow-ups

Two measurements would sharpen the picture: seeds ×10 on just PFC vs NNN
at T = 100k, to pin the manufactured-tail floor with honest statistics;
and a cv-sweep on `band_dist`, to locate where the lattice → ratchet
transition sits.

---

## Addendum: what longer runs showed (T = 200k–300k, n = 400–500)

The scan above ran for 30,000 ticks. Longer runs change the story.

**Every arm ends up in the same place.** Run long enough, and every
version of the model — the null included — stops wandering and gets stuck
far from the starting price (|ln p/x₀| ≈ 3–6). There it repeats the same
motion forever: a sudden snap, then a slow climb back, then the next snap.
A sawtooth. No one goes bankrupt; the market just rings against a wall.

**The wall is the closed economy.** There is only so much money. Once the
price has drifted far enough, one side's wallets can no longer push it
further. The sawtooth is the market bouncing off that limit: a cascade of
stop and timer exits crashes the price (the snap), then resting
take-profits and fresh entries pull it slowly back to the wall, and it
snaps again.

**So the model has two phases.** First a wandering phase, where the price
diffuses and the statistics look market-like. Then a stuck phase, where
the price is pinned at the wall and the sawtooth takes over. The short
scan mostly saw phase one; the long runs mostly see phase two.

**The blocks do not choose the destination — they choose the speed.**
This corrects the reading above. All arms reach the wall; they differ in
how fast:

- bands-normal gets stuck fastest (within ~10–25k ticks),
- the null is in the middle,
- capital-normal wanders longest (~100–150k ticks before pinning).

So "capital is the drift dial" really means "equal capital keeps the
market in the wandering phase longer".

**Which numbers to trust at long horizons.** Once a run is stuck, drift
just measures the wall (≈ 3–5 everywhere), the overshoot ratio blows up
(the slow climbs are one giant overshoot each), and the DC exponent E_N
mixes the two phases — it looks most BM-like (≈ −2) in exactly the arms
that spend the most time wandering. Tick kurtosis stops separating the
arms, because the snaps produce huge tails in every arm. None of these are
wrong; they are measuring the wall, not the market.

**What still stands.** The fat-tail floor survives: no run in either scan
comes anywhere near Gaussian, including NNN with every input Gaussian. The
inherited-vs-manufactured comparison lives in the wandering phase (the
30k table above). And which wall a run picks — top or bottom — is still
pure seed luck, in line with mirror symmetry as an ensemble property.

**Practical consequence.** Any later comparison (e.g. the level-1 market
maker) will give different answers in the two phases. Either gate the
analysis on the wandering phase, or study the wall on purpose. To make
that possible, the scan now records for every run: the lock time (when
the run gets stuck), the tooth period and size (the sawtooth's rhythm and
depth), and each side's wallet totals over time (to confirm the
wealth-wall mechanism directly).

---

## Addendum 2: the wall, understood (wall + value-wall figures)

The wall figures (`scan_wall_*.png`, `scan_wall_value_*.png`) tested the
wall mechanism directly. The result corrected it, then confirmed the
corrected version.

**The wall is made of value, not coins.** The prediction was that the
losing side runs out of coins when the price gets stuck. It does not: at
the lock tick the loser typically still holds 60–100% of its coin. But
the coins are worthless *for pushing* — a short's BTC at a crashed price
buys almost no EUR of impact. The price move devalues the loser's own
ammunition. Measured in pushing power (coin × price, in the coin it
buys), the loser hits zero exactly at the lock tick, in every arm. Lock
happens when power, not coin, runs out.

**The sawtooth is the winner's mountain, discharged at clock rate.** Once
one side is powerless, the other side holds enormous buying power in
cheap-coin terms — but can only deploy wealth/q per clock fire. Each
tooth is one slow spend of that mountain: snap, discharge, climb, repeat.
Testable prediction: the tooth period should follow the winners'
deployment rate, roughly q/(n·c).

**The stuck market is a pump.** During the sawtooth, coins flow one way —
from the losing tribe to the winning tribe, cycle after cycle, while the
aggregate EUR/BTC split barely moves. Two end states exist: with Pareto
wealth the pump stalls at ~15–20% reserves (whales fire too rarely to be
drained); with equal wallets *and* individual bands it runs to
completion — longs end holding essentially all the BTC, shorts all the
EUR. Full segregation, selected by capital homogeneity × band
heterogeneity.

**The stop/timer race (from the n=2 debugging).** A stop needs the price
to cross a full band; the timer fires after ~d/c ticks regardless. Which
exit dominates is set purely by activity: at n=2 the timer wins ~3:1
(band crossings take ~1,700 ticks vs the ~250-tick timer); at n=150 the
stop wins ~1000:1 and the timer is vestigial. The SL:timer ratio is an
activity thermometer, and the timer is confirmed as the small-n liveness
device and nothing more.

**Open items downgraded or opened today.** The Pareto+bands down-pinning
weakened: the 30k re-scan split 2 up / 2 down on the suspect arm (the
band_seed sweep will settle it, now testing a weakened suspicion). Newly
opened: the re-scanned legacy null reads tamer (|drift| 1.3 vs 2.2,
kurtosis ~700 vs ~2,800) than the same setup measured before the step-6
ordering fix — four-seed noise, or the old array-order bug was adding
drift and tail mass. A two-run A/B (PFCF vs PFCF with
`step6_order="array"`, same seeds) decides it.

**The narrative, complete.** Diffusive wandering while both sides hold
power → lock when one side's *power* (not coin) exhausts → sawtooth as
the rate-limited discharge of the survivor's mountain, pumping coin
across the tribes → reserves-floor or full segregation depending on
capital × bands. Every stage now carries a figure.


---

## Addendum 3: five experiments, one retraction, one resolution

**The step-6 ordering bug was real physics (exp1).** Same seeds, with and
without the old fixed-order close loop: the old order added roughly 50%
more drift (1.99 vs 1.31) and 3× fatter tails (kurtosis 2094 vs 701),
seed-paired 4 of 4. The fix was not cosmetic. The legacy frozen dashboards
carry some of that inflation.

**The exit promise controls the market's direction — and our rule is the
right one (exp5, with a retraction).** Swapping the short's exit rule from
"re-spend the EUR you earned" (own_coin) to "buy back exactly the BTC you
sold" (exact) flipped every single run from crashing down to shooting up
(8/8 vs 8/8) — and the exact runs then froze solid: losing shorts could
not afford their own exits, positions jammed, the market died. A third
end state: seized. RETRACTION: an earlier reading called own_coin's e^tp
over-buy an asymmetry. Wrong — own_coin is the symmetric design
(shorting BTC IS buying EUR coins; each tribe over-collects its own coin
by exactly e^tp). "Exact" is the asymmetric rule: it privileges BTC as
the thing that must be returned. The experiment injected an asymmetry and
watched it dominate; it did not remove one. Lesson kept: the fine print
of how positions close is a first-order force.

**The down-pinning mystery is resolved: it was dice 1 (capital_mirror
test).** With independent capital draws, Pareto+bands pinned down 23 of
23 times. Give the shorts the identical capital vector as the longs
(`capital_mirror=True`, one switch, dynamics untouched) and the pinning
collapses: 5 of 6 runs never lock at all in the same horizon, drifts go
mixed-sign. The direction was decided by the structure of the capital
draw — which tribe got the sharper concentration (the more-concentrated
side won in 7 of the 9 runs where we can check) — not by any coded
asymmetry. The full mirror audit of the code (stops, TPs, entries,
sizing, wallets) found every duality holding. Nothing to fix; the mirror
switch stays as the symmetrized diagnostic arm.

**Whales and gamblers fatten tails differently (exp3).** Sweeping the
bite-size spread on equal wallets: the typical tick never changes
(sd_rob flat at band scale) but kurtosis climbs sevenfold (469 → 3,330
at cv 0.5). Concentrated wealth reshapes the book's texture; concentrated
aggression just adds monster prints. Stock for the walls; stock AND bite
for the tails.

**The tooth clock is unmeasured (exp4, inconclusive).** The one-tick snap
detector caught teeth in only 3 of 15 runs — real cascades spread over
several ticks and slip under it. To be redone with a directional-change
detector on the locked segment. One oddity survived: smaller bites lock
FASTER (q=4 → 143k, q=16 → 61k), the opposite of naive intuition.

**Cross-machine bit-reproducibility is broken (~1e-13).** The same run on
Mac and Linux diverges in the 13th decimal: the maths library's exp
differs by one ulp between platforms and chaos amplifies it. The random
draws are shielded; the hot path's exp calls are not. Directions and
statistics agree across machines; exact bits did not. RESOLVED: the
fix (per-agent band multipliers precomputed in decimal at init — the hot
path becomes pure IEEE arithmetic) is now the default (`exp_mode=
"decimal"`), and it costs nothing: on Linux it is bit-identical to the
old libm arm (glibc's exp is correctly rounded on all drawn arguments),
so the frozen record is unchanged — and a Mac run of the exp5 control
config reproduced the Linux trajectory to the last bit. Cross-machine
reproducibility is restored. The libm arm remains for the legacy lineage
proof, which verify_mvp.py pins explicitly.

---

## Addendum 4: the clean market — wash trades, zombie quotes, and what survives

**The tape was talking to itself (self-trades).** Building per-agent
ledgers (arXiv:2411.14068) for the n=2 world exposed two data facts:
the trades CSV logged only the taker side (half of every agent's fills
invisible — the CSV now carries both parties), and the engine let an
agent's order fill against its OWN resting paper. Audited mechanism: a
holding-phase TP crossing the agent's stale entry residual from an
earlier cycle. Wash prints move last_price and stall closes. Fix:
`self_match="skip"` — self-trade prevention in the matching walk, with
the CANCEL-RESTING policy (the crossing own paper is canceled, never
traded, never left standing). The first attempt (skip-and-leave) stood
crossed books that later arrivals ripped apart at absurd prices — the
n=5000 order-book blow-up — and is documented here as the cautionary
half of the fix.

**The book quoted below zero (zombie asks).** A long that sells nearly
all of its position slightly above average leaves a residual whose
implied entry x_bar = -q/b is NEGATIVE; its TP then rests at a negative
price and its stop level is negative — a dead stop. In the frozen null
this happens on 272 of 10,000 ticks at n=150: never trading, but
corrupting best_ask, skipping entries, and disarming stops. Fix:
`neg_xbar_guard` — such residuals rest no TP and arm no stop; the
timer sweeps them.

**Attribution (exp6, 5 arms x 4 seeds).** `close_cancels_rest` is
bit-inert — 4/4 seeds identical to legacy; the existing ref-cancels
already cover close-time paper. `stp` and `nxg` are both real: each
diverges every trajectory and each thins the standing book by ~25-30%
— the legacy book's extra depth was the two pathologies' paper, not
liquidity. No directional or systematic statistical shift beyond seed
chaos: bug fixes, not new physics. (Method note: the first exp6 run
produced five bit-identical arms because flipped Config defaults made
the "legacy" arm clean — experiment arms now pin every switch
explicitly. Defaults are an interface contract.)

**The flagship survives (clean n=5000).** Same landmark config plus
stp+nxg: the market finds the same -2.2 wealth shoulder by a different
route, prints are unchanged (wash was 0.01% at scale), and on the
stationary segment in event time the laws reproduce: N(delta) ~
delta^-1.67 (legacy -1.70) and mean-overshoot/delta = 0.95 (legacy
1.00), kurtosis single-digit. The large-n stationary regime and the
FX overshoot law are properties of the crowd, not of the bugs.

**Recommendation.** The next frozen reference flips `self_match="skip"`
and `neg_xbar_guard=True` (each fixes a demonstrated pathology);
`close_cancels_rest` stays available but off (inert); `print_log` and
`save_tapes` are instruments, off by default. Until that re-freeze,
engine defaults remain legacy — the verify gate and every fingerprint
depend on it.

---

## Addendum 5: the tooth clock law

The sawtooth's rhythm follows the winners' deployment clock. On the
clean arm (stp+nxg), n=400, T=150k, four seeds, the DC tooth census
gives period ~ c^-0.98 over c in {0.002, 0.004, 0.008} (prediction -1;
midpoint ratios 2.18 and 1.80 against the predicted 2.0). Halve the
clock, double the tooth. RETRACTION: the earlier "saturates at fast
clocks" reading came from confounded backfill pooling (q-varied rows
inflating the c=0.004 cell) and does not survive proper measurement.
Tooth amplitudes stay in the universal 1.4-3.3 e-fold band; directions
split 7 up / 8 down across seeds, as the deal-decides resolution
requires. Open remainder: the q exponent (2 usable runs, ratio 1.23 vs
predicted 2.0) needs a dedicated q in {4, 16} job at T~250k — and the
clean arm scrambled q=16's lock times relative to legacy, a note for
the finite-size study.
