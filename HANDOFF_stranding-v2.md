# The Alpha Engine — Handoff: the short-stranding asymmetry

Written as a handoff. Readable by a person or by an LLM picking up the work.
Every claim here is either measured or marked as unverified. Predictions are
stated before the run that would test them. Distributions, not trajectories.

Scope: this doc covers **one** open thread — shorts strand in open positions far
more than longs — and nothing else. For the broader state, read HANDOFF.md and
DIRECTION.md. For the current mechanism, read `agents.py` (the `x_accounting`
sizing branch in `open_btc`) and `simulation.py` (the tick loop).

---

## 1. Why this is the thread that matters

The X-accounting configuration — `f=0.5`, geometric-mean sizing
(`x_accounting=True`, order size `= (W_X/q)/√p` with `W_X = eur/√p + btc·√p`,
identical formula both tribes), `log_thresholds=True`, `symmetric_solvency=True`
— reduced the two headline asymmetries to non-issues:

- **Drift:** at `f=0.5` the log-price drift is statistically consistent with
  zero (measured mean ≈ −0.12 over the seeds tried, within one standard error of 0).
- **Transfer:** the EUR side-PnL that *looks* like a long→short transfer is a
  mark-to-market illusion. In the numeraire-covariant unit the long share of
  geometric-mean wealth stays pinned near 0.5 (measured band ≈ [0.499, 0.527]
  over a 40k-tick run) while EUR long-PnL swings ±17k over the same run. The EUR
  panel tracks the price move, not a wealth shift.

Against that backdrop, **one directional asymmetry survives and is unexplained:
shorts get stuck in un-closeable open positions roughly 20× more often than
longs.** It is the strongest remaining candidate for a *real* (non-lens)
asymmetry in the "symmetric null." Everything else dissolved under a better unit;
this did not. Until it is explained and shown to be swap-covariant (or not), the
claim "we have a symmetric null model" carries an asterisk.

It also actively contaminates every EUR reading: a large fraction of the −18k to
−44k EUR "short loss" on long runs is the *unrealized mark of stranded shorts*,
not realized transfer. So this asymmetry is both a scientific open question and a
measurement hazard.

---

## 2. What is measured

All runs: `n` per side as noted, `c=0.004`, `f=0.5`, `x_accounting=True`,
`log_thresholds=True`, `symmetric_solvency=True`, conservation checks passing
(`system_x0` monotone, PnL zero-sum), post cap-fix engine.

| run | open longs | open shorts | note |
|---|---|---|---|
| n=350, T=50k, seed=42 | 8 | 168 | ~20:1 |
| n=350, T=50k, seed=1  | 4 | 86  | short x̄=0.018 while p_final=0.0875 |
| n=150, T=100k, seed=42 | 1 | 31 | |
| n=150, T=40k, seed=42 (diagnostics) | 1 | peak 26, end 18 | oscillates within the run |

Established from the above:

- **Direction and magnitude of the ratio:** short-side open count exceeds
  long-side by ~20:1 across every run measured. Absolute counts scale with `n`;
  the ratio does not.
- **It is bounded and price-coupled, not runaway.** The stranded count rises when
  the price runs away from shorts' entries and falls when the price reverts (the
  n=150 diagnostic run peaks at 26 and oscillates down to 18; the queue empties
  as covers become affordable). It does **not** monotonically accumulate to
  population size.
- **UNVERIFIED:** whether the queue reliably drains to ~0 given enough time, or
  settles at a nonzero level that depends on the price path. The runs show
  oscillation, not a clean decay to zero. Do not assert "it always clears."

---

## 3. The mechanism (evidenced, then conjectured)

**Evidenced.** A short closes by **buying BTC back** (cover), which costs EUR.
Its stop-loss sits *above* entry (`sl_price` short = x̄·e^{+sl}); when the price
rises to it, `_fire_close` submits a market **BUY** capped by the agent's held
EUR (`eur_budget=max(a.eur,0)`). If the price has run well above entry, the cover
cost `size · price` exceeds held EUR, the buy fills only partially, the residual
short remains, `a.closing` stays True, and the position re-fires next tick — still
unaffordable — and stays open. The fingerprint is in the seed-1 run: stranded
shorts have average entry x̄ ≈ 0.018 against a final price ≈ 0.0875 — they sold
BTC low, the price ran up ~5×, and buying it back costs ~5× the EUR the entry
produced.

A long is the mirror in *form* but not in *funding*: it closes by **selling BTC**,
which it holds from the position, so its cover is always self-funded and never
clamped. Longs therefore do not strand for this reason.

Why `symmetric_solvency=True` does **not** remove it: that flag makes the clamps
symmetric in *form* (a `btc_budget` on sells mirroring the `eur_budget` on buys),
but the binding is asymmetric in *fact*. The short's problematic cover is a BUY,
clamped by EUR it may lack; the long's cover is a SELL, clamped by BTC it always
has. Symmetric clamps, asymmetric bite.

**Conjectured (state before testing):** the asymmetry is intrinsic to position
direction under BTC-quantity matching — "to exit a short you must acquire the
asset with the counter-currency you may not hold," whereas "to exit a long you
surrender the asset you already hold." If so, no sizing/gauge flag reaches it,
because it lives in the close mechanics, not the open.

---

## 4. The decisive tests — predictions stated first

**P1 — cause confirmation (cheap, do first).** Instrument every stranded position
at end-of-run. *Prediction:* stranded agents are almost entirely shorts, each with
`price ≫ entry x̄` (underwater on a risen price) **and** held EUR below the cover
cost `pos_size · price`. If a material fraction of stranded agents are longs, or
shorts that *can* afford their cover, the §3 mechanism is wrong — retract it.

**P2 — long self-funding.** *Prediction:* longs never strand for the mirror
reason (insufficient BTC to sell), because a long always holds the BTC its close
sells. Measure: count long closes that fill partially due to the `btc_budget`
clamp. Prediction is ~0. A nonzero count falsifies "longs are always self-funded."

**P3 — the swap test (the one that decides "symmetric or not").** Under a genuine
currency relabel (long↔short together with EUR↔BTC and p→1/p), stranding must move
to the *longs* if the mechanism is swap-covariant. *Prediction:* in the swapped
world longs strand at the rate shorts do here; if they do not, the cover-funding
asymmetry is a **real residual** the X-accounting never reached.

> **CAVEAT — the `mirror=True` flag is probably NOT this test.** `mirror=True`
> moves the sizing `1/p` conversion to the other tribe; it does **not** swap the
> *close direction* (shorts still cover by buying). Since §3 locates the asymmetry
> in the close direction, `mirror=True` likely leaves stranding on the shorts.
> Verify that expectation, but do not treat `mirror=True` as the swap test. The
> real test needs either a full relabel of which tribe opens-by-buying vs
> opens-by-selling, or direct instrumentation of cover-failure events per side
> (P1/P2), which sidesteps the relabel entirely and is the recommended route.

---

## 5. Is it a bug or a feature? (resolve deliberately, do not silently patch)

There is no borrowing or margin in this model. A "short" is an agent that sold
BTC and intends to buy it back; covering *requires* EUR it actually holds. If the
price runs away, it genuinely cannot afford to buy back — which is the correct
behaviour of a **margin-free spot short**, not a coding error. On this reading,
stranding is an irreducible property of spot shorting under BTC-quantity matching,
and the honest move is to *characterize and bound* it (how large, how long, how
price-coupled), not to "fix" it into symmetry.

The alternative reading is that it is an artifact of the specific cover rule
(market buy capped by held EUR, re-fired each tick) and that a different,
still-conservative close rule would not produce it. Both readings are live. **Do
not add a forced-liquidation or counterparty-funded cover to "remove" the
asymmetry before deciding which reading is true** — that would bury the finding
the way earlier bolt-ons buried others. Decide first, with P1–P3 in hand.

If it is a real feature of spot shorting, then "symmetric null" should be restated
precisely: symmetric in drift and in numeraire-covariant wealth, with a
measured, bounded, price-coupled short-side stranding residual that is intrinsic
to margin-free shorting. That is a defensible and interesting claim — more
interesting than a false "perfectly symmetric."

---

## 6. Tooling in place

- `run_diagnostics.py` — plots open-positions-per-side over time (the stranding
  queue) and the long X-wealth share over time against EUR long-PnL (the lens
  contrast). Edit `N/T/SEED/F/C`, Run.
- `simulation.py` records three series per tick for this: `open_long`,
  `open_short`, `long_x_share`. (Core change — additive; existing series and the
  bit-check reference are unaffected.)
- For P1/P2 you will need a per-agent end-of-run dump (side, pos size, entry x̄,
  held EUR/BTC, cover cost at final price, closing flag). Not yet written — it is
  ~15 lines over `sim.pop.agents` and is the first thing to add.

---

## 7. Invariants that must not regress

- **Two separate conservation fixes must stay.** (1) The `open_btc` entry cap
  (`min(size, eur/price)` / `min(size, btc)`) stops the *entry* crossing driving
  balances negative (~2% `system_x0` leak). (2) The **SL-cover cap at gathering**
  (cap the short cover at `eur/p_prev`) stops the *cover* crossing driving EUR
  negative on stuck shorts — a smaller leak (min ~-16 EUR) that slips past the
  `system_x0` tolerance. The per-agent solvency check in `run_sanity_checks`
  now catches either. The re-fire threshold (step 6) is scaled `1e-9/x_0`.
  ORIGINAL NOTE (kept, but note it was INCOMPLETE — it named only fix 1):
- **The `open_btc` cap must stay.** Without `min(size, self.eur/price)` for longs
  and `min(size, self.btc)` for shorts, the balanced entry crossing (which does
  not clamp) drives BTC balances negative and breaks `system_x0` conservation by
  ~2%. That leak silently inflated the long wealth share (0.542 → 0.509 once
  fixed) and hid the mirror symmetry in the share-vs-f curve. Do not remove it.
- **Read transfer in X, never in EUR.** The EUR PnL panel is a moving-ruler
  artifact; the geometric-mean wealth share is the covariant measure. Any
  stranding conclusion drawn from EUR PnL is confounded by the stranded marks
  themselves.
- **Predictions before runs; distributions across ≥10 seeds before any number is
  load-bearing.** The stranding counts above are 1–2 seeds each — solid on
  direction and order of magnitude, not on precise levels.
- **The book still matches in BTC quantity.** Untested for swap-covariance and
  possibly the irreducible floor. If P3 shows stranding is not the residual, this
  is the next suspect.
