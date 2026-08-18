"""
agent_pnl_mvp.py — per-agent PnL ledgers for the MVP, following
Glattfelder & Houweling 2024 (arXiv:2411.14068), Eqs 1-2, 8-9,
in the mid-price simplification (the book has one trade price; x' = x).

Why this reruns the simulation instead of reading the trades CSV: the CSV
logs the TAKER side only, so roughly half of every agent's fills (its
resting orders being hit) are invisible there — a ledger built from the
CSV alone is qualitatively wrong. The Trade objects carry both parties,
so a deterministic rerun recovers the full two-sided fill history, and
with exp_mode="decimal" it reproduces the original tape bit-for-bit on
any machine.

Self-trades (an agent's marketable order eating its own resting order —
they happen: longs did 43 and 47 of them in the n=2 reference run) are
wallet-neutral and are netted to u=0 in the ledgers, though they do
print on the tape.

Outputs: ledger_<AGENT>.csv per agent (tick, u, x, b, q, x_av, W_q, p_q,
perf) and one comparison figure. Validates every ledger against the
engine's final wallets and checks Sigma p^q == 0 before writing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, _ROOT)                      # simulation_mvp lives at root
OUT = os.path.join(_ROOT, "eval", "runs")
os.makedirs(OUT, exist_ok=True)

from simulation_mvp import Config, Simulation, build_agents

# ---------------- edit these ----------------
CFG = Config(n=2, x_0=100.0, seed=9, T=100_000, capital_dist="normal",
             closing="normal", size_dist="normal")
# --------------------------------------------


class FillSim(Simulation):
    """The engine, with BOTH sides of every fill captured."""

    def __init__(self, cfg, run_checks=True):
        try:
            super().__init__(cfg, run_checks=run_checks)  # type: ignore[call-arg]
        except TypeError:      # engine without the toggle: always-checked
            super().__init__(cfg)
        self.fills = []   # (tick, buy_agent, sell_agent, size, price, taker)

    def _submit(self, o, eur_budget=None, btc_budget=None, rest_residual=True):
        n0 = len(self._trades_this_tick)
        super()._submit(o, eur_budget=eur_budget, btc_budget=btc_budget,
                        rest_residual=rest_residual)
        for tr in self._trades_this_tick[n0:]:
            self.fills.append((self.t, tr.buy_agent, tr.sell_agent,
                               tr.size, tr.price, o.agent_id))


def ledger(fills, init, agent: str) -> pd.DataFrame:
    """Eqs 1-2 (b, q, x_av) and 8-9 (W^q, p^q) over the agent's full fills."""
    rows = []
    b = q = 0.0
    B, Q = init[agent]["B"], init[agent]["Q"]
    for (t, buyer, seller, size, price, _taker) in fills:
        if agent not in (buyer, seller):
            continue
        if buyer == seller:
            u = 0.0                       # self-trade: a wallet wash, netted
        else:
            u = size if buyer == agent else -size
        b += u
        q += -u * price
        xav = -q / b if abs(b) > 1e-12 else float("nan")
        Wq = price * (B + b) + Q + q                  # Eq 8b
        pq = price * b + q                            # Eq 9b
        rows.append((t, u, price, b, q, xav, Wq, pq,
                     pq / (CFG.x_0 * B + Q)))
    return pd.DataFrame(rows, columns=["tick", "u", "x", "b", "q", "x_av",
                                       "W_q", "p_q", "perf"])


def main() -> None:
    sim = FillSim(CFG, run_checks=False).run()
    init = {a.id: dict(B=a.btc, Q=a.eur) for a in build_agents(CFG)}
    final = {a.id: a for a in sim.agents}
    ids = sorted(init)

    tables = {}
    tot = 0.0
    for aid in ids:
        L = ledger(sim.fills, init, aid)
        tables[aid] = L
        dB = (init[aid]["B"] + L["b"].iloc[-1]) - final[aid].btc
        dQ = (init[aid]["Q"] + L["q"].iloc[-1]) - final[aid].eur
        assert abs(dB) < 1e-6 and abs(dQ) < 1e-4, (aid, dB, dQ)
        tot += L["p_q"].iloc[-1]
        L.to_csv(os.path.join(OUT, f"ledger_{aid}.csv"), index=False)
        print(f"{aid}: {len(L)} fills, final p^q = {L['p_q'].iloc[-1]:+12.2f} "
              f"({100 * L['perf'].iloc[-1]:+.3f}%)  [wallet check OK]")
    assert abs(tot) < 1e-4, tot
    print(f"zero-sum: Sigma p^q = {tot:+.8f}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    palette = ["#2563EB", "#7C3AED", "#C2680A", "#DB2777", "#059669", "#DC2626"]
    colors = {}
    for i, aid in enumerate(ids):
        colors[aid] = palette[i % len(palette)]
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1, 1.2]})
    fig.suptitle(f"Per-agent ledgers (2411.14068 Eqs 1-2, 8-9) — full fills, "
                 f"self-trades netted  |  n={CFG.n}, seed {CFG.seed}",
                 fontsize=11, fontweight="bold")
    axes[0].plot(np.log(np.asarray(sim.rec_price) / CFG.x_0), lw=0.6,
                 color="#111827")
    axes[0].axhline(0, ls=":", lw=0.8, color="#9CA3AF")
    axes[0].set_ylabel("ln(p/x0)")
    for aid in ids:
        L = tables[aid]
        axes[1].plot(L["tick"], L["b"], lw=0.9, color=colors[aid], label=aid,
                     drawstyle="steps-post")
        axes[2].plot(L["tick"], L["p_q"], lw=1.0, color=colors[aid], label=aid)
    axes[1].axhline(0, ls=":", lw=0.8, color="#9CA3AF")
    axes[1].set_ylabel("position b (BTC)")
    axes[1].legend(ncol=len(ids), fontsize=8, frameon=False)
    grid = np.linspace(0, CFG.T, 400)
    tot_curve = np.zeros_like(grid)
    for aid in ids:
        L = tables[aid]
        tot_curve += np.interp(grid, L["tick"], L["p_q"])
    axes[2].plot(grid, tot_curve, lw=1.4, ls="--", color="#111827",
                 label="Sigma (zero-sum)")
    axes[2].axhline(0, ls=":", lw=0.8, color="#9CA3AF")
    axes[2].set_ylabel("p^q (EUR)")
    axes[2].set_xlabel("tick")
    axes[2].legend(fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    from simulation_mvp import cfg_tag
    out = os.path.join(OUT, f"agent_pnl_{cfg_tag(CFG)}.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("wrote", out)


if __name__ == "__main__":
    main()
