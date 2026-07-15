# The Alpha Engine — POC

Internal market-making simulation: heterogeneous agents driven by carry-cost
pressure, clearing via a Dutch auction into an emergent internal price `p_int`.

## Modules
- `config.py`      — single source of truth (all parameters + switches)
- `agents.py`      — Agent + Population (Pareto capital, pressure, firing, sizing)
- `market.py`      — Queue + Auction (expiry, unit-reconciled Dutch clearing)
- `simulation.py`  — the main loop (carry → fire → expire → auction → settle → bankruptcy → record)
- `analysis.py`    — Recorder, Analyser (dashboard + automated sanity checks)
- `main.py`        — entry point

## Setup (macOS, VS Code)
    cd alpha_engine
    python3.13 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

In VS Code: Cmd+Shift+P → "Python: Select Interpreter" → pick `.venv/bin/python`.

## Run
    python main.py          # full run with the spec defaults, saves dashboard.png

Each module also runs on its own as a self-test, e.g.:
    python agents.py        # prints invariants + saves capital_distribution.png
    python market.py        # auction self-check + saves auction_clearing.png
    python analysis.py      # livelier run + saves dashboard_demo.png

## Notes
- Edit parameters in `config.py`, not elsewhere.
- The spec defaults are deliberately sparse (the smallest agent fires every
  d_base/c = 1000 ticks). Raise `c`, lower `d_base`, or widen `W` for more flow.
- Three flagged design switches live in config.py: `carry_proportional`,
  `order_size_basis`, `baseline_metric`.
