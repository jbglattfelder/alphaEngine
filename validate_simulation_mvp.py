"""
validate_simulation_mvp.py — 12 tests that the frozen null is healthy.

Run from anywhere:  python validate_simulation_mvp.py      (~30 s)

This is NOT the old legacy-vs-MVP bit gate (that proof lives in
dev/null_model/verify/ and is history). These tests validate the CURRENT
engine on its own terms: determinism, the frozen fingerprints, the money
identities, the clean-market guarantees (no self-trades, no degenerate
quotes, no crossed books), ledger closure, file integrity, and the
cross-machine decimal invariant.

Exit code 0 = all 12 pass. Any failure prints what broke and exits 1.
"""

from __future__ import annotations

import os
import sys
import tempfile
from decimal import Decimal, getcontext
from typing import Any, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "helper"))

from simulation_mvp import Config, Simulation, build_agents  # noqa: E402

# ── the frozen fingerprints (defaults; update ONLY at a deliberate re-freeze) ──
FP_N150 = dict(drift=-0.1847, trades=34_998)     # n=150, T=10_000, seed=9
FP_N2 = dict(drift=-0.3864, trades=158)          # n=2,  T=10_000, seed=9 (normal cap/close/size)

PASS = 0
FAIL = 0


def check(k: int, name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    mark = "OK " if ok else "FAIL"
    print(f"[{k:>2}/12 {mark}] {name}" + (f"  — {detail}" if detail else ""))
    if ok:
        PASS += 1
    else:
        FAIL += 1


class Probe(Simulation):
    """The default engine plus read-only witnesses for the market-hygiene
    tests: every fill's two parties, any standing crossed book, any
    non-positive resting quote."""

    def __init__(self, cfg: Config) -> None:
        super().__init__(cfg)
        self.fills: list[tuple] = []       # (buy_agent, sell_agent, size, price)
        self.n_crossed_standing = 0
        self.n_bad_quotes = 0

    def _submit(self, o, eur_budget=None, btc_budget=None, rest_residual=True):
        n0 = len(self._trades_this_tick)
        super()._submit(o, eur_budget=eur_budget, btc_budget=btc_budget,
                        rest_residual=rest_residual)
        for tr in self._trades_this_tick[n0:]:
            self.fills.append((tr.buy_agent, tr.sell_agent, tr.size, tr.price))

    def step(self, t):
        r = super().step(t)
        bb, ba = self.book.best_bid, self.book.best_ask
        if bb is not None and ba is not None and bb > ba:
            self.n_crossed_standing += 1
        for q in (self.book.bids, self.book.asks):
            for o in q:
                if o.active and o.size > 1e-12 and o.price <= 0:
                    self.n_bad_quotes += 1
                    break
        return r


def main() -> int:
    quiet: dict[str, Any] = dict(print_log=False, save_csv=False)

    # ── 1. determinism: the same Config twice is the same world, bit for bit ──
    a = Simulation(Config(n=50, T=2_000, seed=9, **quiet)).run()
    b = Simulation(Config(n=50, T=2_000, seed=9, **quiet)).run()
    same = np.array_equal(np.asarray(a.rec_price), np.asarray(b.rec_price))
    check(1, "determinism (bit-repeat)", same)

    # ── the workhorse run: n=150 defaults, instrumented ──
    s = Probe(Config(n=150, T=10_000, seed=9, **quiet)).run()
    drift = float(np.log(s.p / 100.0))

    # ── 2. the frozen fingerprint ──
    ok = (abs(drift - FP_N150["drift"]) < 5e-5
          and len(s.trades_log) == FP_N150["trades"])
    check(2, "fingerprint n=150/T=10k/s9",
          ok, f"drift {drift:+.4f} / {len(s.trades_log)} trades")

    # ── 3. n=2 fingerprint (the mechanism, naked) ──
    s2 = Probe(Config(n=2, T=10_000, seed=9, x_0=100.0, capital_dist="normal",
                      closing="normal", size_dist="normal", **quiet)).run()
    d2 = float(np.log(s2.p / 100.0))
    ok = (abs(d2 - FP_N2["drift"]) < 5e-5 and len(s2.trades_log) == FP_N2["trades"])
    check(3, "fingerprint n=2/T=10k/s9", ok,
          f"drift {d2:+.4f} / {len(s2.trades_log)} trades")

    # ── 4. conservation: the market is closed ──
    init = build_agents(s.cfg)
    e0 = sum(x.eur for x in init)
    b0 = sum(x.btc for x in init)
    e1 = sum(x.eur for x in s.agents)
    b1 = sum(x.btc for x in s.agents)
    ok = (abs(e1 - e0) < 1e-6 * max(e0, 1.0)
          and abs(b1 - b0) < 1e-6 * max(b0, 1.0))
    check(4, "conservation (EUR and BTC totals)", ok,
          f"dEUR={e1 - e0:+.2e} dBTC={b1 - b0:+.2e}")

    # ── 5. zero-sum side PnL ──
    tot = s.rec_pnl_long[-1] + s.rec_pnl_short[-1]
    check(5, "zero-sum PnL (long + short)", abs(tot) < 1e-4, f"sum={tot:+.2e}")

    # ── 6. self-trade prevention holds ──
    selfies = sum(1 for (ba, sa, _sz, _px) in s.fills if ba == sa)
    check(6, "no self-trades (STP)", selfies == 0, f"{selfies} found")

    # ── 7. no degenerate prices anywhere ──
    prices = np.array([f[3] for f in s.fills])
    check(7, "no non-positive prints or resting quotes",
          bool((prices > 0).all()) and s.n_bad_quotes == 0,
          f"bad prints {(prices <= 0).sum()}, bad-quote ticks {s.n_bad_quotes}")

    # ── 8. the book never stands crossed ──
    check(8, "book never left crossed", s.n_crossed_standing == 0,
          f"{s.n_crossed_standing} crossed ticks")

    # ── 9. wallet solvency ──
    weur = min(x.eur for x in s.agents)
    wbtc = min(x.btc for x in s.agents)
    check(9, "wallet solvency (no negative balances)",
          weur > -1e-6 and wbtc > -1e-9, f"min EUR {weur:.2e}, min BTC {wbtc:.2e}")

    # ── 10. ledger closure: fills + initial wallets == final wallets (n=2) ──
    init2 = {x.id: (x.eur, x.btc) for x in build_agents(s2.cfg)}
    ok = True
    worst = 0.0
    for ag in s2.agents:
        de, db = 0.0, 0.0
        for (ba, sa, sz, px) in s2.fills:
            if ba == sa:
                continue                        # wallet-neutral wash (none expected)
            if ba == ag.id:
                de -= sz * px
                db += sz
            elif sa == ag.id:
                de += sz * px
                db -= sz
        e_err = init2[ag.id][0] + de - ag.eur
        b_err = init2[ag.id][1] + db - ag.btc
        worst = max(worst, abs(e_err), abs(b_err))
        ok = ok and abs(e_err) < 1e-4 and abs(b_err) < 1e-7
    check(10, "ledger closure to wallets (n=2, all agents)", ok,
          f"worst residual {worst:.2e}")

    # ── 11. CSV integrity: what is written is what was recorded ──
    with tempfile.TemporaryDirectory() as td:
        pp = s2.write_price_csv(os.path.join(td, "p.csv"))
        tp = s2.write_trades_csv(os.path.join(td, "t.csv"))
        import csv as _csv
        prows = list(_csv.reader(open(pp)))[1:]
        trows = list(_csv.reader(open(tp)))[1:]
        ok = (len(prows) == len(s2.rec_price)
              and len(trows) == len(s2.trades_log)
              and float(trows[0][5]) == s2.trades_log[0][5]
              and float(prows[-1][1]) == s2.rec_price[-1])
        check(11, "CSV integrity (rows and bitwise reload)", ok,
              f"{len(prows)} price rows, {len(trows)} trade rows")

    # ── 12. the decimal invariant: stored band multipliers == Decimal recompute ──
    getcontext().prec = 40
    ag = s.agents[0]
    want = float(Decimal(str(ag.tp_band)).exp())
    ok = ag.e_tp_up == want
    check(12, "decimal band-multiplier invariant (cross-machine bits)", ok,
          f"e_tp_up {ag.e_tp_up!r}")

    print(f"\n{PASS}/12 passed" + ("" if FAIL == 0 else f", {FAIL} FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
