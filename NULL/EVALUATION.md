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
