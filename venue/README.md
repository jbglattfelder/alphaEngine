# RPM Exchange: a trading venue on the null model

A mock-up of a spot exchange (Coinbase / Kraken / Binance style) for the pair
**RCC/EUR**, opening at x₀ = 100. Everyone in the market except you is an
agent of the **frozen Alpha Engine null model**. The engine runs entirely in
the browser (Pyodide, Python compiled to WebAssembly), so there is no server.
Each browser tab owns its own market, and "New market" discards it and builds
a fresh one. Nothing persists beyond the tab.

Sign in with username **liquidity**, password **engine**. This is a
courtesy gate, not protection (see Security).

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
| n | agents per side (population 2n), at most 10,000. Speed in Chromium falls roughly as 1/n: about 450 ticks/s at 150, 70 at 1,000, 11 at 7,500, 7 at 10,000 |
| K | the crowd's total capital, EUR |
| tp, sl | take-profit / stop-loss band, log distance from entry |
| c | clock rate (pressure per tick), default 0.004 |
| q | order fraction: each open deploys wealth/q, default 8 |
| seed | same seed, same market |
| your EUR, RCC | your endowment, on top of K; its value at x₀ is at most 75% of K |

Settings cannot be changed while a market runs; open a new market instead.

## Time

A tick is one engine step, not a second. A new market starts playing at once,
at 6 ticks/s. Play/pause (or the space bar) and the
ticks-per-second dial drive a loop in a Web Worker. Your orders are applied between ticks:
JavaScript is single-threaded, so a message from the page can only be handled
between two engine steps. The header shows the tick counter and your local
clock. At n = 150 Chromium sustains about 450 ticks/s.

The price chart draws one point per tick (the last print) and a volume bar per
tick (RCC printed since the previous tick; a trade you make between ticks
counts towards the next bar; green when the price did not fall). You can zoom
out until the whole session fits. Each of your trades gets one arrow, however
many makers it filled against. Switching to the depth chart resets the price
chart's zoom, scroll and price axis, so coming back always shows the live end
of the curve.

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

## Security

There is no server, no database and no account: everything runs in the
viewer's own browser, and nothing anyone types reaches anyone else. Nobody can
post content that other players see, so there is nothing to plant spam links
in. The only text rendered as HTML is numbers and fixed strings, and the two
free-text fields (order notes, counterparty ids) are escaped.

- **Content-Security-Policy** (in `index.html`): scripts only from this site,
  `unpkg.com` and `cdn.jsdelivr.net`, plus WebAssembly; no plugins, no
  `<base>` rewrites, no form submissions; network access only to this site
  and jsDelivr.
- **Subresource Integrity**: Lightweight Charts carries a `sha384` hash, so a
  tampered copy on unpkg is refused. CI checks that the live file still
  matches the hash.
- **Pinned versions**: Pyodide 0.27.7 from jsDelivr (versioned URLs do not
  change). Pyodide checks every package it loads (numpy) against the sha256
  in its lock file.
- **The sign-in is not security.** A static site cannot keep a secret: the
  check runs in the page and only the SHA-256 of `liquidity:engine` is
  shipped, so the password is not readable at a glance. Anyone can still
  read the source, and there is nothing behind the gate worth protecting.
- **Residual risk**: a compromise of jsDelivr itself (the Pyodide core files
  have no integrity hash). Self-hosting Pyodide next to the site would remove
  it, at the cost of about 15 MB in the deploy.

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
2. Settings → Secrets and variables → Actions → Variables tab → **Repository
   variables** → `VENUE_PAGES` = `true`. It must be a repository variable,
   not an environment variable: the deploy job's `if:` is evaluated before the
   job enters its `github-pages` environment, so an environment variable is
   not visible there.

The site then lives at `https://<owner>.github.io/alphaEngine/venue/`.

**Caching.** GitHub Pages lets browsers cache files for 10 minutes. The deploy
stamps every file URL with the commit id: `__BUILD__` in `index.html` becomes
`v=<commit>`, and `app.js` hands it on to the worker and the Python files. So
a browser never runs a new page against an old cached `venue_wrapper.py`. It
did once, which made the volume bars disappear without an error.
