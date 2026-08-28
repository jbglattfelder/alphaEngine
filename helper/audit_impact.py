"""
audit_impact.py — the liquidity engine's product spec: price impact and decay.

Injects controlled external market orders into a live simulation and
measures what the book does to them: immediate impact, the decay of that
impact over the following ticks, and the permanent residue. This is the
curve an external (level-1) agent will actually face.

Mechanics: one extra "external" agent is endowed at init (its wealth is
ADDED to the closed economy — conservation still holds, the external is
simply a participant who trades on OUR schedule instead of a clock). Every
`spacing` ticks it fires one marketable order of a controlled size, in a
randomized direction; around each injection the price path is recorded.

Usage:
    python helper/audit_impact.py            # defaults: n=500 smoke
    (edit the block at the bottom for real sizes)
"""

from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from simulation_mvp import Agent, Config, Order, Simulation  # noqa: E402


class ImpactProbe(Simulation):
    """Simulation plus a scheduled external order flow.

    sizes are in multiples of the internal agents' median order value
    (wealth/q at x_0), so results are book-relative, not absolute."""

    def __init__(self, cfg: Config, warmup: int, spacing: int,
                 size_mults: tuple, window: int = 800) -> None:
        super().__init__(cfg)
        self.warmup = warmup
        self.spacing = spacing
        self.size_mults = tuple(size_mults)
        self.window = window
        med_k0 = float(np.median([a.K0 for a in self.agents]))
        self.unit_eur = med_k0 / cfg.q          # one "typical order" in EUR
        ext_eur = self.unit_eur * max(size_mults) * 40
        ext_btc = ext_eur / cfg.x_0
        self.ext = Agent(id="EXT", is_long=True, eur=ext_eur, btc=ext_btc,
                         K0=2 * ext_eur, d=1e18, tp_band=cfg.tp,
                         sl_band=cfg.sl)
        self.ext.e_tp_up = self.ext.e_tp_dn = 1.0
        self.ext.e_sl_up = self.ext.e_sl_dn = 1.0
        self.agents.append(self.ext)
        self._eur_total0 += ext_eur             # conservation baseline
        self._btc_total0 += ext_btc
        self.rng_inject = np.random.default_rng([cfg.seed or 0, 0xE347])
        self.injections: list[dict] = []        # tick, side, mult, p_before

    def step(self, t):
        r = super().step(t)
        if t >= self.warmup and (t - self.warmup) % self.spacing == 0:
            mult = float(self.size_mults[len(self.injections)
                                         % len(self.size_mults)])
            buy = bool(self.rng_inject.integers(0, 2))
            p0 = self.p
            eur_value = mult * self.unit_eur
            size = eur_value / max(p0, 1e-12)
            if buy:
                o = Order("EXT", is_buy=True, price=1e18, size=size, tick=t)
                self._submit(o, eur_budget=min(eur_value, max(self.ext.eur, 0.0)),
                             rest_residual=False)
            else:
                o = Order("EXT", is_buy=False, price=1e-18, size=size, tick=t)
                self._submit(o, btc_budget=min(size, max(self.ext.btc, 0.0)),
                             rest_residual=False)
            self.injections.append(dict(tick=t, side=+1 if buy else -1,
                                        mult=mult, p0=p0))
        return r


def impact_table(sim: ImpactProbe) -> None:
    p = np.asarray(sim.rec_price, float)
    lags = (0, 1, 5, 20, 100, sim.window)
    print(f"\nimpact (signed log-price move vs injection price, bp; "
          f"median over injections):")
    print(f"{'size x typical':>15} {'n':>4}" +
          "".join(f"  t+{k:<5}" for k in lags))
    for m in sorted(set(i["mult"] for i in sim.injections)):
        rows = []
        for inj in sim.injections:
            t, s, p0 = inj["tick"], inj["side"], inj["p0"]
            if inj["mult"] != m or t + sim.window >= len(p):
                continue
            rows.append([s * np.log(p[t - 1 + k] / p0) * 1e4 for k in lags])
        if not rows:
            continue
        med = np.median(np.array(rows), axis=0)
        print(f"{m:>15g} {len(rows):>4}" +
              "".join(f"  {v:+7.1f}" for v in med))
    print("\nread: t+0 = immediate impact; decaying columns = the book "
          "absorbing the shock; the far column = permanent residue.")


if __name__ == "__main__":
    cfg = Config(n=500, T=30_000, seed=9,
                 capital_dist="normal", band_dist="normal",
                 closing="normal", size_dist="normal",
                 print_log=False, save_csv=False)
    sim = ImpactProbe(cfg, warmup=5_000, spacing=1_000,
                      size_mults=(0.5, 1, 2, 5, 10))
    sim.run()
    impact_table(sim)
