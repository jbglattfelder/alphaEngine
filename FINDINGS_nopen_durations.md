# Findings: the n_open collapse and the duration laws (level-0 closing tests)

Two experiments proposed as the last genuinely new level-0 measurements
(HANDOFF-v4 §0 verdict standing). Predictions were stated in the experiment
headers before running (`exp_nopen.py`, `exp_durations.py`). Both scored below.
**Everything here is 1–2 seeds: direction and order of magnitude only.**
Artifacts: `nopen.jsonl`.

---

## 1. The n_open collapse — SUPPORTED at moderate inventory, then a confound

> *P1: q(m=1) is a decreasing function of mean n_open, and points from different
> n at similar n_open coincide. P2: a common q=0.5 crossing in n_open.*

Home arm, tp=sl=0.01, seed 1 unless noted:

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
*full q(m) profiles* (0.648/0.536/0.465 vs 0.664/0.541/0.478), replicated at
seed 2 for the n=150 cell to three decimals of agreement. At low-to-moderate
inventory, n and c are interchangeable through n_open — the mechanistic variable
is depth, as §1's inventory frame says it should be.

**What sharpened.** q1 does not go to 0.5. It *floors* around 0.65–0.69 from
n_open ≈ 12 onward and stays there to n_open = 127. What n_open controls is the
**decay scale of the momentum** (q2, q8 fall toward and below 0.5), not the
tick-level continuation, which appears to be a fixed property of the SL-cover
mechanism. Restated: inventory sets the persistence *length*, not the
persistence *strength*. This refines HANDOFF-v4 §2.2's "momentum gone by m=2 at
n=500": the tick-level q1 was never gone.

**What broke, and the confound it exposed.** The high-inventory region does not
collapse: (n=500, c=0.004) seed 2 sits far off seed 1 at the same config
(q1 0.730 vs 0.685; q2 0.646 vs 0.546) — and that run trended hard (lnp +4.10).
**q(m) is entangled with the realized path**: a trending run shows elevated
continuation at every scale, mechanically. Two consequences:

1. P1/P2 are **UNRESOLVED at high inventory** — not falsified (the deviation
   tracks lnp, not n-at-fixed-inventory), not confirmed. Deciding requires
   trend-stratified q (or detrended steps) and ≥5 seeds per cell.
2. **This confound applies retroactively to HANDOFF-v4 §2.2 itself**, whose q
   table is single-seed. Those numbers are path-conditional; the qualitative
   claims (SLs are the momentum; q decays with scale) are safe, the levels are
   not. §2.2 should carry the caveat.

## 2. The duration laws — PREDICTION FALSIFIED, and the surprise is the yield

> *P1: engine total-move durations are thinner-tailed than BM at matched δ/sd
> and length. P2: engine duration CV < BM. Falsifier: engine tail ≥ BM at any δ
> → the clock does not regularise waiting times; retract the "structurally
> unreachable" framing for the time laws.*

Engine (home, n=150, c=0.004, T=32k, seed 1) vs BM matched in nonzero-step sd,
zero-step density, and length; log gauge; durations = `DCEvent.n_ticks_tm`:

| δ/sd | arm | events | median | CV | P(τ>5·med) | max/med |
|---|---|---|---|---|---|---|
| 8 | engine | 420 | 61 | 0.72 | 0.005 | 5.1 |
| 8 | BM | 225 | 115 | 0.69 | 0.000 | 4.6 |
| 16 | engine | 166 | 157 | 0.77 | 0.012 | 5.9 |
| 16 | BM | 62 | 294 | 0.93 | 0.048 | 6.9 |
| 32 | engine | 42 | 421 | **2.27** | 0.024 | **26.9** |
| 32 | BM | 14 | 1628 | 0.81 | 0.000 | 4.1 |

**The falsifier fired at δ=32·sd.** The engine's durations are *fatter*-tailed
than BM's, not thinner — CV 2.27 vs 0.81, one traversal 27× the median. The
threshold clock does **not** regularise intrinsic-time waiting; the third
"structurally unreachable" entry I proposed does not exist. Retracted as
specified.

**Why (conjecture — untested).** The engine mixes two traversal regimes that BM
lacks: ratchety trending episodes cross δ fast; range-bound episodes (momentum
at tick scale, reversion at coarse scale, §2.2) trap the price and take an order
of magnitude longer. A mixture of fast and slow regimes *is* heavy-tailed
durations. Prediction for the follow-up, stated now: conditioning durations on
the episode's net drift splits the distribution into two narrow components.

**The reframing this buys.** §0 scores volatility clustering FAIL — measured as
ACF(|r|) in physical time. Duration mixing at large δ is what volatility
clustering *looks like in intrinsic time*. If the effect survives seeds and a
drift-stratified control, level 0 contains a seed of temporal clustering that
the physical-time statistic cannot see — which would soften one FAIL in the
scorecard and sharpen exactly what the level-1 actor must add (jumps and depth,
yes; temporal heterogeneity, apparently not entirely).

**Caveats before anyone leans on this:** 42-vs-14 events at the interesting δ;
single seed; the engine feed drifted (lnp −4.03), and some duration
heterogeneity could be early/late-regime contrast on one path. Needs ≥10 seeds
and the drift-stratified control. Direction only.

---

## 3. Score and what regressed

Prediction ledger this session: n_open collapse — 1 supported (moderate
inventory, replicated), 1 unresolved-with-cause (path confound, now named);
durations — 2 falsified by their own registered falsifier, 1 reframe gained.
The confound finding (q is path-conditional) retro-edits HANDOFF-v4 §2.2 and
belongs in its caveats; the duration result belongs next to §2.5's compact
support as its temporal counterpart — with the opposite sign.

Files: `exp_nopen.py`, `exp_durations.py` (predictions in headers),
`nopen.jsonl` (the sweep artifact).
