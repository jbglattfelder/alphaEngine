# The Alpha Engine — Direction

A strategic handoff. HANDOFF.md holds the measured state; this holds the analysis
of where we are, why, and the path. Written to be read by a person or an LLM
before touching anything.

---

## 1. What the situation actually is

We set out to build a null model — a market where trading has no consequence —
and discovered that no such market can be built. That is the finding, and it is
worth stating at full strength: **a market mechanism cannot be structureless.**
Orders must be denominated in something; sizes must be converted through some
price; stops must execute against some depth. Each of those choices privileges a
side, and the privilege compounds — through stop frequency, amplified by
cascades — into a systematic wealth transfer that no symmetry argument can
remove, only relocate.

The venue is therefore not a stage. It is a participant with no account: it
holds no capital, takes no position, and still shapes who wins. Every behaviour
we have measured so far — the drift, the transfer, the cascades, the fill
compression — is the mechanism expressing itself through agents that are, by
construction, identical up to scale. That is the null model's real content:
not "nothing happens," but a complete inventory of what the *rules alone* do,
before any agent is allowed to be different from any other.

This matters because of what comes next. Everything interesting we intend to
add — strategies, heterogeneity, evolution, external traders — will produce
behaviour, and the only way to attribute that behaviour correctly is to have
the mechanism's own signature fully characterized first. The null is the
control experiment for the entire research program. Level 0 (mechanism) must be
closed before level 1 (ecology) opens, or every level-1 result is confounded.

A second asset came out of this session, and it is not code: the epistemic
ledger reads one prediction confirmed, four falsified, one under-powered. The
falsifications did all the work. Verbal reasoning about rule interactions
failed every time it was tested against a measurement; the measurements were
cheap. The method — state the prediction, run the thing that can kill it, log
the corpse — is the most valuable component of the project and must survive
every handoff.

## 2. The goal, restated precisely

**Product goal:** an internal, reactive market that supplies price and
liquidity to external traders.

**Scientific goal that gates it:** a market whose every behaviour is either
derived from its rules or measured and bounded — so that when external
intelligence couples to it, anything new that happens is *attributable*.

**Definition of done for the null:** (a) γ re-measured with the committed
instrument across the c-sweep — the fill-compression curve is the product's
impact function, its actual spec sheet; (b) the (mix_long, mix_short)
convention square mapped, the zero-transfer locus located; (c) the x_0 < 0.25
scale break traced to its guilty line — an unidentified dimensional constant in
a model whose ethos is "nothing can hide" is intolerable; (d) the
symmetric_sizing cut and the cascade counterfactual run. Each is one to two
sessions. None is optional.

## 3. The path, in order

**First, close the null** (the list above). γ leads: we currently do not know
whether the venue fills large orders at requested^0.6 or requested^0.11, which
is the difference between a usable liquidity product and a decorative one.

**Second, construct — or let the population discover — macroscopic symmetry.**
Micro-symmetry is proven impossible; and note the sharpening from the v4 work:
**symmetry, where achieved, is a large-n property, not a property of the
mechanism** — the same home-close engine whose x-share pins at 0.50008 at n=150
produces a 5:1 tribe asymmetry and ln p = +2.16 at n=2 (HANDOFF-v4 §2.7). Every
symmetry claim in this document is implicitly conditioned on population size,
and the correct control variable is open inventory, not n (FINDINGS_nopen_
durations.md). Population-level symmetry is available two ways. Engineered: pin the mix at the zero-transfer locus from the 2-D map and
monitor the residual as an operating metric. Discovered: a properly powered
evolution run (cumulative fitness or ≥50k-tick epochs) tests whether imitation
finds an interior equilibrium — and whether the tentative commons result holds:
individually optimal convention choice appears to be collectively
self-defeating for one tribe. If that survives ten seeds, it is the paper's
best sentence: a tragedy of the commons arising in a conserved market with
identical agents and no externality written anywhere.

**Third, heterogeneity — where "fundamentals" enter, and the deep constraint on
how.** A closed market has no exogenous value to anchor to; rule 5 forbids
importing one. So fundamentals here can only be *endogenous*: trend-followers
and reversal-traders whose reference points are built from the market's own
history, in numeraire-covariant quantities (log-returns, actions attached to
the asset). Price then becomes fully self-referential — expectation about
expectation — which is not a limitation but the honest version of the Keynesian
observation, implemented rather than assumed. The null's transfer must be
subtracted from every result at this level: a strategy that "wins" may merely
be sitting on the favourable side of the mechanism.

**Fourth, evolution as the organizing principle.** Once strategies exist, let
selection allocate wealth among them. This is where symmetry finally breaks
honestly — by differential fitness rather than by convention — and where the
original question (does trading concentrate wealth?) gets its real answer. The
market becomes an ecology: strategies as species, liquidity as the shared
resource, the mechanism as the geography. Expect the level-0 lesson to recur
fractally: the fitness measure, the imitation rule, the mutation kernel are
each a convention, and each will tilt something. Measure the tilt; do not hunt
for the neutral kernel — we have proven how that hunt ends.

**Fifth, the red team, then the coupling.** Before any real external touches
the substrate: harden the cascades (per-agent stop jitter; the heterogeneous
agents are themselves the two-sided depth that makes avalanches expensive), and
then write one adversarial external agent whose sole objective is to drain the
book — state the bound it should not beat, and let it try. A null market that
survives a designed predator is ready to quote prices to strangers. One that
does not has told us exactly what to fix.

## 4. Invariants — the things that do not change as everything else does

Predictions before runs. Distributions, never trajectories. Realized separated
from unrealized. Instruments committed, never monkeypatched. Quantities
numeraire-covariant or their tilt measured. Retractions filed at equal weight
with results. Documentation is part of the mechanism: a stale docstring is a
bug that bites the next reader, and the next reader may be a machine that
believes it.

The through-line, and the reason this project is more than an engineering
exercise: simple local rules do not merely *generate* the market's behaviour —
they exhaust it. Everything we have found lives in the interactions, nothing in
the rules read separately, and the interactions were opaque to reasoning and
transparent to measurement every single time. Build upward one level at a time,
and at each level, characterize the floor before furnishing the room.
