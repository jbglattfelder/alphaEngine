# Alpha Engine — Project Guide

Guidance for working in this repository. Read this before changing code.

## What this is

A proof-of-concept agent-based market simulation. Two fixed populations of agents
(longs holding EUR, shorts holding BTC — both hold both currencies) are driven by
carry-cost **pressure** that accumulates until each agent fires an order. Orders
rest in a queue and clear via a **Dutch auction** into an emergent internal price
`p_int`. No external price feed in v1. The goal is to observe emergent dynamics:
price shape, agent mortality, liquidity, pool drain.

## Run

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py            # full run on spec defaults; writes dashboard.png
```

Each module self-tests when run directly: `python agents.py` (writes
`capital_distribution.png`), `python market.py` (writes `auction_clearing.png`),
`python analysis.py` (livelier run, writes `dashboard_demo.png`).

## Architecture & conventions

| Module          | Owns                                                  | Must NOT do |
| --------------- | ----------------------------------------------------- | ----------- |
| `config.py`     | All parameters + switches (single source of truth)    | — |
| `agents.py`     | Agent + Population: capital draw, pressure, firing, sizing | import market; contain market logic |
| `market.py`     | Queue + Auction: expiry, Dutch clearing, price formation | mutate agent balances (it returns Fills) |
| `simulation.py` | The §16 main loop; wires modules                      | hold business logic |
| `analysis.py`   | Recorder, Analyser: dashboard + sanity checks         | — |
| `main.py`       | Entry point (load config, run, show results)          | — |

Rules:
- **Change parameters in `config.py` only.** Nothing else hardcodes a constant.
- Dependency direction is `config <- agents <- market <- simulation`; `market`
  imports `agents` only for the `Side` enum (a type, not behaviour).
- The auction returns `Fill`s; the simulation applies them to agents. Keep it that way.
- matplotlib is imported lazily inside plot methods so core mechanics stay plot-free.
- Reproducibility: a single `np.random.default_rng(cfg.seed)` threads through; the
  only RNG use is the Pareto capital draw. Auction tie-breaks are deterministic.

## Key terminology

- `p_int` emergent internal price; `p_ext` external price (v2, not present yet).
- `phi_i` carry pressure accumulator (the agent's clock); `d_i` firing threshold,
  scales with initial capital `K0_i` so smaller agents fire more often.
- `K_i` total capital in EUR terms (`eur + btc*p_int`); `K0_i` initial capital.
- `SE` = sum of long EUR orders; `SB` = sum of short BTC orders; clearing price
  `p* = SE/SB`.
- Lane model (agents keep their role; current code) vs Bias model (deferred).
- Option A (fixed size, reset) vs Option B (capital consumed) — A is the baseline.
- Heterogeneity Type 1 (holding time) / 2 (capital) / 3 (both); Type 1 self-organises
  to Type 3 once capital evolves.

## Open design decisions (resolve deliberately, don't silently change)

Three are config switches; defaults follow the spec's §16 loop:
- `carry_proportional` — proportional (`c*home`) vs flat carry drain.
- `order_size_basis` — `"home"` (loop) vs `"total_K"` (§9 prose). Spec is internally
  inconsistent here; we defaulted to `"home"`.
- `baseline_metric` — `"x_min"` (loop) vs `"K0_min"` (§9 prose). With `"x_min"` no
  agent starts in the all-in regime (rescaling lifts the smallest K0 above x_min).

Other resolved-but-noted points:
- **Auction sweep**: §11's literal "sweep upward, lowest crossing" ratchets the price.
  We implement the unbiased crossing `p* = SE/SB` instead. The ratchet is a one-line
  change in `Auction.clear` (`max(p_prev, SE/SB)`).
- **`c` plays two roles**: a flat pressure increment (firing timing) AND a proportional
  capital drain. Tuning `c` changes both; they cannot be tuned independently.
- **§24 monotonicity**: mark-to-market capital is NOT monotonic (it rises when `p_int`
  rises and revalues BTC). The monotonic invariant is the price-invariant
  `total_capital_x0`. Sanity checks must use that series, not the mark-to-market one.
- **`beta`** exists in config but is unused by the Dutch auction (reserved).

## Invariants (sanity checks must keep passing)

- `total_capital_x0` monotonically non-increasing (carry-only drain + departures).
- `p_int` strictly positive.
- On crossed ticks `matched_eur == matched_btc * p_int`; zero matched volume otherwise.
- `alive_long + alive_short <= 2n` every tick.
- No dead agent has a resting order in the queue.

## Gotchas

- **matplotlib first run**: the very first import builds a font cache via macOS
  `system_profiler`, which can take 30s–2min. Let it finish once; do not Ctrl+C.
- **Sparse defaults**: the smallest agent fires every `d_base/c = 1000` ticks, so the
  default run is nearly silent (~24 clears in 10k ticks). For real dynamics raise `c`
  (e.g. 0.02), lower `d_base`, or widen `W`.

## Deferred to v2 (not implemented)

External price feed `p_ext` (via a swappable `feeds.py` abstraction, see spec §25),
external traders coupling `p_int` to `p_ext`, spread / bid-ask quoting by agents,
bilateral (two-curve) yield curves, capital replenishment / wealth recycling,
soft reset / Option B capital dynamics, partial pressure reset.
