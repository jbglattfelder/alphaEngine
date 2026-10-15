# RPM Exchange: a trading venue on the null model

A mock-up of a spot exchange (Coinbase / Kraken / Binance style) for the pair
**RCC/EUR**, opening at x₀ = 100. Everyone in the market except you is an
agent of the **frozen Alpha Engine null model**. The engine runs entirely in
the browser (Pyodide, Python compiled to WebAssembly), so there is no server.
Each browser tab owns its own market, and "New market" discards it and builds
a fresh one. Nothing persists beyond the tab.

## The frozen engine

The venue imports `simulation_mvp.py` from the repository root, unchanged. It
is the file of tag `v1.0-paper`, and `FROZEN.sha256` pins it and the root
validator. CI checks the hashes and runs `validate_simulation_mvp.py` on every
push. Everything the venue needs is in `py/venue_wrapper.py`, which subclasses
`Simulation`.

| hook | what it does |
|---|---|
| `_apply_trades` | moves the human's wallet as well as the agents' (same arithmetic as the engine's own method) |
| `_submit` | attributes passive fills to the human's resting orders |
| `_step_record` | keeps the engine's every-tick conservation assert, over agents + human |
| `_housekeep_counterparties` | after a human order, runs the engine's step-6 housekeeping (`_settle_if_flat`) for the agents it traded with |
| `trim_records` | cuts the engine's ever-growing `rec_*` lists and `trades_log` (the venue runs open-ended) |

Your orders go through the same `Book.submit` as the crowd's. A resting limit
order sits in the same book, and agents' entries and exits hit it. A test
(`test_idle_human_leaves_the_engine_bit_identical`) checks that a session
where you hold coins but never trade is bit-for-bit the engine's own run.

## Market settings

| setting | meaning |
|---|---|
| arm | **NNNN**: capital, bands, timer and order size all drawn per agent from normal distributions; tp/sl are the means, cv 0.3. **PFCF**: Pareto capital, fixed bands (every agent uses exactly tp/sl), clock timer, fixed size |
| n | agents per side (population 2n) |
| K | the crowd's total capital, EUR |
| tp, sl | take-profit / stop-loss band, log distance from entry |
| c | clock rate (pressure per tick), default 0.004 |
| q | order fraction: each open deploys wealth/q, default 8 |
| seed | same seed, same market |
| your EUR, RCC | your endowment, on top of K; its value at x₀ is at most 75% of K |

Settings cannot be changed while a market runs; open a new market instead.

## Time

A tick is one engine step, not a second. Play/pause and the ticks-per-second
dial drive a loop in a Web Worker. Your orders are applied between ticks:
JavaScript is single-threaded, so a message from the page can only be handled
between two engine steps. The header shows the tick counter and your local
clock. At n = 150 Chromium sustains about 450 ticks/s.

## Orders

- **Market**: buy by RCC amount or by EUR amount, or sell by RCC amount. The
  order fills against what the book holds, at each maker's price, and the
  rest is dropped (IOC).
- **Limit**: whatever crosses fills at once, at maker prices. The rest rests
  at your limit until it is filled or you cancel it (GTC).
- **Cancel**: one order, or all of them.
- Partial fills are allowed. There are no fees. Trading is spot only: resting
  orders lock their coins, and an order you cannot pay for is rejected.
- **Self-trade prevention** is the engine's own rule (cancel-resting): an order
  of yours that would cross your own resting order cancels that resting order.
- The engine prices bids in EUR. The wrapper converts, so a limit buy of
  u RCC fills exactly u RCC even with price improvement.

## PnL (Glattfelder & Houweling 2024, arXiv:2411.14068)

The balance-sheet tally the engine uses for its agents, with the spread.
Fills are booked at the price they traded at (Eq. 1). Positions are marked at
x′, "the opposite of the bid/ask pair", which is the side of the book the
position would close against:

- **long (b > 0)**: the best bid
- **short (b < 0)**: the best ask
- **flat (b = 0)**: the ask when q > 0, the bid when q < 0. This follows the
  paper's worked example (260 USDT → 1.527165 SOL at the ask 170.25), which
  Eq. 10 as printed does not reproduce.

An empty side falls back to the last price.

| quantity | equation |
|---|---|
| position b = Σuⱼ, q = −Σxⱼuⱼ | Eq. 1 |
| average price x̄ = −q/b | Eq. 2 |
| PnL vs not trading pᵠ = x′b + q (EUR), pᵇ = b + q/x′ (RCC) | Eqs. 3, 9 |
| wealth Wᵠ = x′(B + b) + Q + q, Wᵇ = Wᵠ/x′ | Eq. 8 |
| performance p̃ = pᵇ / (B + Q/x₀) | Sec. 3 |

- **Realised PnL** is the banked q of every round trip that returned to b = 0.
  A fill that flips the position through zero is split at zero.
- **Unrealised PnL** is x′b + q of the open position.
- Realised + unrealised = pᵠ.
- A test reproduces every row of the paper's SOL/USDT table (pᵇ, pᵠ, Wᵠ).
- At a single price (x′ = last) the agents' PnL plus yours sums to zero
  (tested).

## Running locally

```bash
python -m http.server 8000                  # from the repo root; open http://localhost:8000/venue/
python -m pytest venue/tests -q
python validate_simulation_mvp.py
```

Serve from the repository root, because the page loads the engine from
`../simulation_mvp.py`. Pyodide 0.27.7 is loaded from cdn.jsdelivr.net and
Lightweight Charts 4.2.0 from unpkg.com.

## Hosting

The site is static. `.github/workflows/venue.yml` publishes it to GitHub Pages
(free for this public repository) on every push to `main`, after the tests
pass. One-time setup:

1. Settings → Pages → Source: **GitHub Actions**
2. Settings → Secrets and variables → Actions → Variables: `VENUE_PAGES` = `true`

The site then lives at `https://<owner>.github.io/alphaEngine/venue/`.
