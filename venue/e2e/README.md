# venue/e2e: GUI and UX regression tests

These tests pin how the venue looks and what it does, so a change cannot
alter the GUI or UX by accident.

| spec | what it pins |
|---|---|
| `visual.spec.js` | every screen, tab and form mode, pixel for pixel, at 0 px tolerance. Covers sign-in, configure (also PFCF selected and over the cap), loading, the trading screen on desktop, tablet and phone, the price and depth charts, the order book (exact and grouped), recent trades, the four bottom tabs, the order form in its five modes plus a filled-in limit order, and toasts. Baselines are in `__screenshots__/` |
| `behaviour.spec.js` | what the venue does: validation, play/pause/space/speed dial, seed determinism, New market, limit/market/cancel/cancel all, rejections, form helpers (book click, BID/MID/ASK, %, unit switch), PnL adding up, no phone-width scroll, no console errors (asserted in every test) |

## Why the pixels are stable

- **The market is deterministic.** The engine produces the same run for the
  same `Config`, to the bit. The tests advance it with the `?e2e` hook
  `window.__rpm.step(k)`, which runs exactly k ticks while paused. They never
  advance it by wall time.
- **The clock is frozen.** The page's `Date` is fixed (09:31:25, 15 Oct 2026,
  Europe/Zurich). The only cells that still show real time are those carrying
  the worker's wall time (the time column of the order and trade tables), and
  they are masked.
- **The rendering is pinned.** Everything runs in
  `mcr.microsoft.com/playwright:v1.56.1-noble`, pinned by digest in CI: the
  same browser build and the same fonts, locally and in CI.
- **The CDNs are replaced.** Pyodide 0.27.7 comes from `pyodide-cache/`
  (`node fetch-pyodide.js`) and Lightweight Charts 4.2.0 from `node_modules`.
- **Toasts are hidden** in the page shots (`screenshot.css`). They have a shot
  of their own.

## Running

From the repo root:

```bash
cd venue/e2e && npm ci && node fetch-pyodide.js && cd ../..
docker run --rm --ipc=host -v "$PWD":/work -w /work/venue/e2e \
  mcr.microsoft.com/playwright:v1.56.1-noble npx playwright test
```

A failure writes `test-results/` with expected, actual and diff images for each
screenshot that moved. In CI the same files are uploaded as the `e2e-report`
artifact.

## Changing the GUI on purpose

1. Make the change.
2. Run the suite. The screenshots that fail are exactly the ones the change
   touches.
3. If, and only if, every failing image is part of the change, re-baseline:
   `... npx playwright test --update-snapshots`. Then review the new images
   (`git diff --stat venue/e2e/__screenshots__` lists them).
4. Commit the new baselines with the change, naming each re-baselined image in
   the commit message.

A failing screenshot that is *not* part of the change is a regression: fix the
code, never the baseline.
