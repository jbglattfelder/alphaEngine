# Findings: TP clustering — compact support breaks, and only heterogeneity breaks it

The HANDOFF-v4 §6.1 experiment ("cluster the take-profits, not the stops"),
executed. Predictions were stated in `exp_tpcluster.py` before running. Home
arm, n=150, c=0.004, T=16k, tp=sl=0.01. **Seeds 1–2: direction and order of
magnitude.** Artifact: `tpcluster.jsonl`.

## The table

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

## Scoring the predictions

**P2 — CONFIRMED, and it is the first break of compact support in the entire
project.** The hierarchy arm (per-agent roundness: 20% k=1, 40% k=2, 30% k=3,
10% unsnapped) produces **P(|r| > 4·sd) = 2.1–2.2%** against a Gaussian 0.006%
and against §2.5's measured *exact zero* everywhere else — replicated across
both seeds to the second decimal, with single steps of 70 bands.

**The controls make it clean.** Two ways the result could have been fake, both
excluded: (a) *band inflation* — the entry-side guard widens the effective tp
when grid spacing exceeds it (tp_eff column; the confound gauge specified in
advance). But the band-matched control (no snap, tp=0.029 = k2's realized
band) keeps P>4sd at exactly zero in its own sd units: a wider uniform band
just re-lattices; compact support scales with the band, exactly as §2.5's
structural argument requires. (b) *any single grid* — k=1, with 22× band
inflation and 100% multi-band steps, also has zero tail. **A single
characteristic scale cannot make tails, no matter how coarse.**

What does: **heterogeneous roundness.** Depth piles onto shared coarse levels
while the typical band — hence the tick sd — stays fine; a traversal across an
empty coarse gap is then a jump that is large *in the arm's own volatility
units*. Fat tails are a property of the *mixture*, not of any grid. This is
Osler's hierarchy (00 beats 50) doing exactly the job the handoff's
second-order prediction assigned it.

**P1 — confirmed only in the confounded sense.** The single-k `>2·tp`
explosions are mostly band inflation (the control reproduces them). The honest
multi-band claim rests on the hier arm's max/tp = 70 with tp_eff only 4.8×.

**P3 — HALF-FALSIFIED.** The hierarchy was predicted to produce tails *while
preserving scale structure*. It produced the tails and **damaged the overshoot
ratio worst of all arms** (os(8sd) 0.47–0.49 vs baseline 0.99). At level 0.5
you can have fat tails or the overshoot law's remnant, not both — consistent
with §0: the overshoot law needs the actor, and no depth *geometry* substitutes.

## What this changes in HANDOFF-v4

- §0's scorecard row "fat tails — FAIL, provably unreachable" is now
  conditional: **unreachable under homogeneous TP bands** (re-proved twice by
  the controls here); **reachable at level 0.5** — one cognitive quirk, no
  actor, no strategy: agents with round fingers.
- §2.5's structural argument survives intact — it was always an argument about
  a *single* wall spacing. The theorem-shaped version: max |step| is set by the
  largest empty interval in the resting-TP level set; homogeneous bands bound
  it at ~2·tp; a roundness hierarchy makes the interval distribution itself
  heterogeneous. The bound didn't break; the geometry it bounds changed.

## Caveats and the follow-up, specified

Two seeds; the tp_eff confound is *reduced* to 4.8×, not eliminated — the k=1
subpopulation carries 22× inflation into the mixture. The confound-free
implementation: drop k=1 from the hierarchy (weights over {2, 3, none}) and/or
pre-compensate the snap distance (aim the raw level at tp − E[shift], the
sl_grid §2.8 fix). *Prediction, stated now:* the 4sd tail survives both
refinements at reduced magnitude; if it vanishes, the tail was the k=1
subpopulation's wide bands after all — retract. Then ≥10 seeds before the
scorecard edit is load-bearing.
