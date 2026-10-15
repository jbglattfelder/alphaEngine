"""
venue_wrapper.py — the thin layer between the frozen null model and the
trading-venue front end.

The engine (simulation_mvp.py at the repo root, byte-identical to tag
v1.0-paper, sha256 in ../FROZEN.sha256) is imported UNCHANGED. Everything the venue
needs is added here by subclassing:

  VenueSim(Simulation)
    - a human trader "YOU" whose orders go through the SAME Book.submit
      (via Simulation._submit) as the crowd's, so they rest in the same
      book and agents can hit them
    - _apply_trades: also moves the human's wallet (the engine only knows
      its 2n agents)
    - _submit: attributes passive fills to the human's resting orders
    - _step_record: the per-tick conservation assert is kept, now over
      agents + human (the market is still closed: the human's coins are
      in it from t=0)

  Venue
    - the facade the browser worker calls: configure, step, place / cancel
      orders, read state. Every call returns plain JSON-able dicts.

Time: one tick = one engine step. Human orders are applied BETWEEN ticks
(the browser is single-threaded; a message handler can only run between
two steps). Right after a human order, the step-6 housekeeping the engine
would have done within the tick (drop a filled TP's ref, settle a delivered
round trip) is run for every agent the order traded with, so no agent ever
enters a tick carrying a stale, already-delivered position.

PnL: Glattfelder & Houweling 2024, "Calculating Profits and Losses for
Algorithmic Trading Strategies: A Short Guide", arXiv:2411.14068 — the
balance-sheet tally the engine itself uses for its agents (see
Agent.__doc__): Eq. 1 (b, q), Eq. 2 (average price), Eq. 3/9 (PnL against the no-trading
benchmark, marked at x' = the opposite side of the book), Eq. 8 (wealth).
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # the repo root: simulation_mvp.py
for _p in (ROOT, HERE):                                 # (in the browser both sit in /venue)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from simulation_mvp import Config, Order, Simulation, Trade  # noqa: E402  (frozen)

USER_ID = "YOU"            # never collides with agent ids "L<i>" / "S<i>"
MAX_USER_FRACTION = 0.75   # the human's endowment (EUR + RCC*x_0) is at most 0.75 K
X0 = 100.0                 # RCC/EUR opens at 100
T_OPEN_ENDED = 10 ** 12    # Config.T is only read by Simulation.run(); the venue steps itself
BUY_MKT = 1e18             # the engine's marketable limits (see Order.__doc__)
SELL_MKT = 1e-15

ARMS = {
    # capital_dist, band_dist, closing, size_dist
    "NNNN": dict(capital_dist="normal", band_dist="normal", closing="normal", size_dist="normal"),
    "PFCF": dict(capital_dist="pareto", band_dist="fixed", closing="clock", size_dist="fixed"),
}


# ═════════════════════════════════════════════════════════════════════════════
# PnL — arXiv:2411.14068, single-price form
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class PaperPnL:
    """The human's PnL ledger, arXiv:2411.14068.

    Endowment B (RCC), Q (EUR). The trading tally (Eq. 1): b = sum u_j,
    q = -sum x_j u_j (u > 0 bought), at the price x_j each fill traded at.
    Average price x̄ = -q/b (Eq. 2).

    x' is "the opposite of the bid/ask pair": the side of the book an open
    position would be closed against, i.e. the best BID for a long (b > 0) and
    the best ASK for a short (b < 0). With the position flat (b = 0), the paper's
    worked example converts the banked quote profit at the ask when q > 0 and at
    the bid when q < 0 (Eq. 3's closing case; the example's 260/170.25 =
    1.527165 SOL and its Eq. 8 wealth rows). An empty side falls back to the
    last price, the engine's own definition of "the price".

        p^q = x' b + q                      Eq. 9b  (EUR)
        p^b = b + q / x'                    Eq. 9a  (RCC; = Eq. 3)
        W^q = x' (B + b) + Q + q            Eq. 8b
        W^b = W^q / x'                      Eq. 8a
        p~  = p^b / (B + Q / x_0)           Sec. 3  (performance, 1.0 = 100 %)

    Realised / unrealised: when the position returns to b = 0 its tally q is
    the realised profit of that round trip and is banked (the engine banks its
    agents the same way, Simulation._settle_if_flat); the open tally's
    x' b + q is unrealised. A fill that flips the position through zero is
    split at zero. Realised + unrealised = p^q."""
    B: float
    Q: float
    b: float = 0.0              # open tally, base (RCC)
    q: float = 0.0              # open tally, quote (EUR, signed)
    realised: float = 0.0       # banked q of closed round trips (EUR)
    b_tot: float = 0.0          # all-time tally, Eq. 1
    q_tot: float = 0.0
    volume_rcc: float = 0.0
    n_fills: int = 0
    dust: float = 1e-12

    def fill(self, u: float, x: float) -> float:
        """Book one fill of u RCC (u > 0 bought) at x. Returns the PnL
        realised by this fill (EUR)."""
        self.b_tot += u
        self.q_tot -= x * u
        self.volume_rcc += abs(u)
        self.n_fills += 1
        banked = 0.0
        if self.b != 0.0 and (self.b > 0) != (u > 0) and abs(u) >= abs(self.b) - self.dust:
            # closes (and possibly flips) the open position
            u_close = -self.b
            self.q -= x * u_close
            banked = self.q
            self.realised += banked
            self.b, self.q = 0.0, 0.0
            u_rest = u - u_close
            if abs(u_rest) > self.dust:
                self.b = u_rest
                self.q = -x * u_rest
        else:
            self.b += u
            self.q -= x * u
            if abs(self.b) <= self.dust:     # float residue of an exact close
                banked = self.q + x * self.b
                self.realised += banked
                self.b, self.q = 0.0, 0.0
        return banked

    # ── the paper's prices ──────────────────────────────────────────────────
    def x_prime(self, last: float, bid: Optional[float], ask: Optional[float]) -> float:
        """x': bid for a long, ask for a short; flat: ask if q > 0, bid if q < 0."""
        if self.b > 0:
            side = bid
        elif self.b < 0:
            side = ask
        else:
            side = ask if self.q_tot > 0 else bid
        return side if (side is not None and side > 0) else last

    def avg_price(self) -> Optional[float]:
        """Eq. 2, x̄ = -q/b of the open position (None when flat)."""
        if self.b == 0.0:
            return None
        return -self.q / self.b

    def unrealised(self, xp: float) -> float:
        return xp * self.b + self.q

    def total_q(self, xp: float) -> float:
        """Eq. 9b, p^q in EUR, at x'."""
        return xp * self.b_tot + self.q_tot

    def total_b(self, xp: float) -> float:
        """Eq. 9a, p^b in RCC, at x'."""
        return self.b_tot + self.q_tot / xp

    def wealth_q(self, xp: float) -> float:
        """Eq. 8b, W^q in EUR, at x'."""
        return xp * (self.B + self.b_tot) + self.Q + self.q_tot

    def view(self, last: float, bid: Optional[float] = None,
             ask: Optional[float] = None) -> dict:
        xp = self.x_prime(last, bid, ask)
        pb = self.total_b(xp)
        w0b = self.B + self.Q / X0
        return dict(realised=self.realised, unrealised=self.unrealised(xp),
                    total=self.total_q(xp), total_rcc=pb, wealth=self.wealth_q(xp),
                    wealth_rcc=self.wealth_q(xp) / xp, x_prime=xp,
                    avg_price=self.avg_price(), position=self.b,
                    perf=(pb / w0b if w0b > 0 else 0.0),
                    volume=self.volume_rcc, n_fills=self.n_fills)


# ═════════════════════════════════════════════════════════════════════════════
# The human's account and orders
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class UserWallet:
    """Duck-types the four Agent fields Simulation._apply_trades moves."""
    eur: float
    btc: float               # RCC (the engine calls the base coin BTC)
    pos_b: float = 0.0
    pos_q: float = 0.0


@dataclass
class UserOrder:
    id: int
    side: str                # "buy" | "sell"
    kind: str                # "market" | "limit"
    price: Optional[float]   # limit price; None for market
    qty: Optional[float]     # RCC; None for a market buy by EUR amount
    eur_amount: Optional[float]
    tick: int
    wall: float
    status: str = "open"     # open | partial | filled | cancelled | rejected
    filled: float = 0.0      # RCC
    notional: float = 0.0    # EUR
    reason: str = ""
    resting: Optional[Order] = None    # the engine Order resting in the book
    rest_qty: float = 0.0              # last seen resting RCC (fill attribution)

    def avg_fill(self) -> Optional[float]:
        return self.notional / self.filled if self.filled > 0 else None

    def remaining(self) -> float:
        if self.resting is None or not self.resting.active:
            return 0.0
        return _rest_rcc(self.resting)

    def view(self) -> dict:
        return dict(id=self.id, side=self.side, kind=self.kind, price=self.price,
                    qty=self.qty, eur_amount=self.eur_amount, tick=self.tick,
                    wall=self.wall, status=self.status, filled=self.filled,
                    avg=self.avg_fill(), remaining=self.remaining(),
                    reason=self.reason)


def _rest_rcc(o: Order) -> float:
    """RCC still wanted / offered by a resting order."""
    return o.give_amt / o.price if o.is_buy else o.give_amt


# ═════════════════════════════════════════════════════════════════════════════
# The engine, plus one human
# ═════════════════════════════════════════════════════════════════════════════

class VenueSim(Simulation):
    """The frozen Simulation with a human trader in its book."""

    def __init__(self, cfg: Config, user_eur: float, user_rcc: float) -> None:
        super().__init__(cfg)
        self.user = UserWallet(eur=float(user_eur), btc=float(user_rcc))
        self.pnl = PaperPnL(B=float(user_rcc), Q=float(user_eur))
        self._by_id: dict[str, Any] = {a.id: a for a in self.agents}
        self._by_id[USER_ID] = self.user
        # the closed market now holds the agents' coins AND the human's
        self._grand_eur0 = self._eur_total0 + self.user.eur
        self._grand_btc0 = self._btc_total0 + self.user.btc
        self.user_orders: dict[int, UserOrder] = {}
        self._user_resting: dict[int, UserOrder] = {}   # engine oref -> order
        self._next_user_id = 1
        self._user_taker: Optional[UserOrder] = None
        self.user_fills: list[dict] = []                # drained by Venue
        self.user_events: list[dict] = []               # order status changes
        self.volume = 0.0                               # session RCC volume, every print
        self.hi = self.lo = cfg.x_0                     # session high / low print

    # ── hooks into the frozen engine ─────────────────────────────────────────
    def _apply_trades(self, trades: list[Trade]) -> None:
        """Same wallet + tally moves as Simulation._apply_trades (verbatim
        arithmetic), over agents AND the human."""
        by_id = self._by_id
        for tr in trades:
            eur = tr.size * tr.price
            buyer = by_id[tr.buy_agent]
            buyer.eur += -eur
            buyer.btc += +tr.size
            buyer.pos_q += -eur
            buyer.pos_b += +tr.size
            seller = by_id[tr.sell_agent]
            seller.eur += +eur
            seller.btc += -tr.size
            seller.pos_q += +eur
            seller.pos_b += -tr.size
            self.volume += tr.size
            if tr.price > self.hi:
                self.hi = tr.price
            if tr.price < self.lo:
                self.lo = tr.price

    def _submit(self, o: Order, eur_budget: Optional[float] = None,
                btc_budget: Optional[float] = None,
                rest_residual: bool = True) -> None:
        n0 = len(self._trades_this_tick)
        super()._submit(o, eur_budget=eur_budget, btc_budget=btc_budget,
                        rest_residual=rest_residual)
        new = self._trades_this_tick[n0:]
        if not new and not self._user_resting:
            return
        mine = [tr for tr in new if USER_ID in (tr.buy_agent, tr.sell_agent)]
        if o.agent_id == USER_ID:
            uo = self._user_taker
            for tr in mine:
                self._record_user_fill(uo, tr, role="taker")
            self._scan_resting(stp=True)       # STP may have cancelled own quotes
        elif mine:
            self._scan_resting(stp=False, trades=mine)

    def _step_record(self, t: int) -> None:
        """Keep the engine's every-tick conservation assert, over the whole
        closed market (agents + human)."""
        self._eur_total0 = self._grand_eur0 - self.user.eur
        self._btc_total0 = self._grand_btc0 - self.user.btc
        super()._step_record(t)

    # ── fill bookkeeping ────────────────────────────────────────────────────
    def _record_user_fill(self, uo: Optional[UserOrder], tr: Trade, role: str) -> None:
        u = tr.size if tr.buy_agent == USER_ID else -tr.size
        realised = self.pnl.fill(u, tr.price)
        if uo is not None:
            uo.filled += tr.size
            uo.notional += tr.size * tr.price
        cp = tr.sell_agent if u > 0 else tr.buy_agent
        self.user_fills.append(dict(
            order=(uo.id if uo else None), tick=self.t, wall=time.time(),
            side=("buy" if u > 0 else "sell"), size=tr.size, price=tr.price,
            role=role, counterparty=cp, realised=realised))

    def _scan_resting(self, stp: bool, trades: Optional[list[Trade]] = None) -> None:
        """Attribute passive fills to the human's resting orders by the change
        in each order's remaining size (makers trade at their own price), and
        retire orders that left the book."""
        pending = list(trades or [])
        for oref, uo in list(self._user_resting.items()):
            o = uo.resting
            assert o is not None
            now = _rest_rcc(o) if o.active else 0.0
            filled = uo.rest_qty - now
            consumed_dust = (not o.active) and o.give_amt <= self.book.eps_of(o)
            if not o.active and not consumed_dust:
                filled = 0.0                   # dropped with size left: STP cancel
            if filled > 1e-15:
                # split the matching prints of this order (price = its limit)
                left = filled
                for tr in list(pending):
                    if tr.price == o.price and left > 1e-15 and \
                            (tr.buy_agent == USER_ID) == o.is_buy:
                        self._record_user_fill(uo, tr, role="maker")
                        left -= tr.size
                        pending.remove(tr)
            uo.rest_qty = now
            if not o.active:
                del self._user_resting[oref]
                uo.resting = None
                if consumed_dust:
                    uo.status = "filled"
                else:
                    uo.status = "cancelled"
                    uo.reason = "self-trade prevention" if stp else uo.reason
                self.user_events.append(uo.view())
            elif filled > 1e-15:
                uo.status = "partial"
                self.user_events.append(uo.view())
        for tr in pending:                     # should not happen; never lose a fill
            self._record_user_fill(None, tr, role="maker")

    # ── the human acts (between ticks) ──────────────────────────────────────
    def locked(self) -> tuple[float, float]:
        """EUR in resting bids, RCC in resting asks."""
        eur = rcc = 0.0
        for uo in self._user_resting.values():
            o = uo.resting
            assert o is not None
            if o.is_buy:
                eur += o.give_amt
            else:
                rcc += o.give_amt
        return eur, rcc

    def available(self) -> tuple[float, float]:
        le, lr = self.locked()
        return max(self.user.eur - le, 0.0), max(self.user.btc - lr, 0.0)

    def _buy_cost(self, qty: float, limit: float) -> tuple[float, float]:
        """EUR needed to buy `qty` RCC from asks at <= limit, walking the book
        exactly as Book.submit would (maker prices, dust levels skipped, own
        asks skipped — STP cancels them). Returns (eur, rcc fillable)."""
        eur = 0.0
        got = 0.0
        for o in self.book.asks:
            if o.price > limit or got >= qty:
                break
            if o.agent_id == USER_ID or o.give_amt <= self.book.btc_eps:
                continue
            take = min(qty - got, o.give_amt)
            eur += take * o.price
            got += take
        return eur, got

    def user_order(self, side: str, kind: str, qty: Optional[float] = None,
                   price: Optional[float] = None,
                   eur_amount: Optional[float] = None) -> UserOrder:
        """Place a market or limit order for the human. Market: buy by RCC
        qty or by EUR amount, sell by RCC qty; fills what the book offers,
        the rest is dropped (IOC). Limit: fills what crosses, the rest rests
        at the limit (GTC). Spot only: never spends coins it does not have
        (resting orders lock their coins)."""
        uo = UserOrder(id=self._next_user_id, side=side, kind=kind, price=price,
                       qty=qty, eur_amount=eur_amount, tick=self.t, wall=time.time())
        self._next_user_id += 1
        self.user_orders[uo.id] = uo
        try:
            self._place(uo)
        finally:
            self._user_taker = None
        self._housekeep_counterparties()
        if uo.status not in ("rejected", "cancelled") and uo.resting is None:
            if uo.qty is not None:
                complete = uo.filled >= uo.qty * (1 - 1e-9)
            else:
                complete = uo.notional >= (uo.eur_amount or 0.0) * (1 - 1e-9)
            if complete:
                uo.status = "filled"
            else:
                # IOC: what the book could not fill is dropped
                uo.status = "cancelled"
                uo.reason = uo.reason or ("rest unfilled: book ran dry" if uo.filled > 0
                                          else "no liquidity")
        elif uo.resting is not None:
            uo.status = "partial" if uo.filled > 0 else "open"
        self.user_events.append(uo.view())
        return uo

    def _reject(self, uo: UserOrder, why: str) -> None:
        uo.status = "rejected"
        uo.reason = why

    def _place(self, uo: UserOrder) -> None:
        avail_eur, avail_rcc = self.available()
        eps = self.book.btc_eps
        if uo.kind == "limit" and not (uo.price and uo.price > 0 and math.isfinite(uo.price)):
            return self._reject(uo, "limit price must be > 0")
        if uo.qty is not None and not (uo.qty > eps and math.isfinite(uo.qty)):
            return self._reject(uo, "amount must be > 0")
        self._user_taker = uo

        if uo.side == "sell":
            if uo.qty is None:
                return self._reject(uo, "amount must be > 0")
            if uo.qty > avail_rcc * (1 + 1e-12):
                return self._reject(uo, "insufficient RCC")
            qty = min(uo.qty, avail_rcc)
            if uo.kind == "market":
                o = Order(USER_ID, is_buy=False, price=SELL_MKT, size=qty, tick=self.t)
                self._submit(o, btc_budget=qty, rest_residual=False)
            else:
                assert uo.price is not None
                o = Order(USER_ID, is_buy=False, price=uo.price, size=qty, tick=self.t)
                self._submit(o, btc_budget=qty, rest_residual=True)
                self._adopt_resting(uo, o)
            return

        # ── buys: the book denominates bids in EUR, the human in RCC ──
        if uo.kind == "market":
            if uo.eur_amount is not None:
                if not (uo.eur_amount > self.book.eur_eps):
                    return self._reject(uo, "amount must be > 0")
                if uo.eur_amount > avail_eur * (1 + 1e-12):
                    return self._reject(uo, "insufficient EUR")
                budget = min(uo.eur_amount, avail_eur)
            else:
                assert uo.qty is not None
                cost, got = self._buy_cost(uo.qty, math.inf)
                if got <= eps:
                    return self._reject(uo, "no asks in the book")
                if cost > avail_eur * (1 + 1e-12):
                    return self._reject(uo, "insufficient EUR")
                budget = min(cost, avail_eur)
            o = Order(USER_ID, is_buy=True, price=BUY_MKT, size=budget / max(self.p, 1e-300),
                      tick=self.t)
            self._submit(o, eur_budget=budget, rest_residual=False)
            return

        assert uo.qty is not None and uo.price is not None
        cost, got = self._buy_cost(uo.qty, uo.price)
        rest = uo.qty - got
        need = cost + max(rest, 0.0) * uo.price
        if need > avail_eur * (1 + 1e-12):
            return self._reject(uo, "insufficient EUR")
        if got > eps:
            # the crossing part, spending exactly what it costs at maker prices
            o = Order(USER_ID, is_buy=True, price=uo.price, size=got, tick=self.t)
            self._submit(o, eur_budget=min(cost, avail_eur), rest_residual=False)
        rest = uo.qty - uo.filled
        if rest > eps:
            avail_eur, _ = self.available()
            o = Order(USER_ID, is_buy=True, price=uo.price, size=rest, tick=self.t)
            self._submit(o, eur_budget=min(rest * uo.price, avail_eur), rest_residual=True)
            self._adopt_resting(uo, o)

    def _adopt_resting(self, uo: UserOrder, o: Order) -> None:
        if o.active and o.oref in self.book._by_ref:
            uo.resting = o
            uo.rest_qty = _rest_rcc(o)
            self._user_resting[o.oref] = uo

    def user_cancel(self, order_id: int) -> Optional[UserOrder]:
        uo = self.user_orders.get(order_id)
        if uo is None or uo.resting is None:
            return None
        o = uo.resting
        self.book.cancel(o.oref)
        self._user_resting.pop(o.oref, None)
        uo.resting = None
        uo.rest_qty = 0.0
        uo.status = "cancelled"
        uo.reason = "by you"
        self.user_events.append(uo.view())
        return uo

    def _housekeep_counterparties(self) -> None:
        """The step-6 housekeeping (Simulation._step_refire_and_settle minus
        the re-fire, which only concerns agents that have no resting orders)
        for every agent the human just traded with."""
        touched = set()
        for f in self.user_fills:
            if f["tick"] == self.t:
                touched.add(f["counterparty"])
        for aid in touched:
            a = self._by_id.get(aid)
            if a is None or a is self.user:
                continue
            if a.tp_ref is not None and a.tp_ref not in self.book._by_ref:
                a.tp_ref = None
            self._settle_if_flat(a)

    # ── memory: the session runs open-ended ─────────────────────────────────
    def trim_records(self) -> None:
        """The engine appends every tick to its rec_* series and trades_log
        and only ever reads the last element back (step(): rec_alive_*[-1]).
        The venue keeps its own windows, so the engine's lists are cut to
        their last element."""
        for name, val in vars(self).items():
            if name.startswith("rec_") and isinstance(val, list) and len(val) > 1:
                del val[:-1]
        self.trades_log.clear()


# ═════════════════════════════════════════════════════════════════════════════
# The facade the browser talks to
# ═════════════════════════════════════════════════════════════════════════════

def make_config(n: int, K: float, tp: float, sl: float, c: float, q: int,
                seed: int, arm: str) -> Config:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {sorted(ARMS)}")
    return Config(n=int(n), T=T_OPEN_ENDED, seed=int(seed), K=float(K), x_0=X0,
                  c=float(c), q=int(q), tp=float(tp), sl=float(sl),
                  save_csv=False, save_book=False, save_tapes=False, print_log=False,
                  **ARMS[arm])


class Venue:
    """One session's market. Reset = a new Venue."""

    TRIM_EVERY = 5_000

    def __init__(self, n: int = 150, K: float = 1_000_000.0, tp: float = 0.01,
                 sl: float = 0.01, c: float = 0.004, q: int = 8, seed: int = 9,
                 arm: str = "NNNN", user_eur: float = 0.0, user_rcc: float = 0.0) -> None:
        if user_eur < 0 or user_rcc < 0:
            raise ValueError("allocation must be non-negative")
        if user_eur + user_rcc * X0 > MAX_USER_FRACTION * K * (1 + 1e-12):
            raise ValueError(f"allocation exceeds {MAX_USER_FRACTION:.0%} of K")
        self.cfg = make_config(n, K, tp, sl, c, q, seed, arm)
        self.arm = arm
        self.sim = VenueSim(self.cfg, user_eur, user_rcc)
        self.t = 0
        self.alive = True
        self._log_pos = 0

    # ── time ────────────────────────────────────────────────────────────────
    def step(self, k: int = 1, max_prints: int = 300) -> dict:
        """Run k ticks. Returns the per-tick price tape, the prints (newest
        last, at most max_prints), the human's fills and order updates."""
        sim = self.sim
        ticks: list[list[float]] = []
        prints: list[list] = []
        for _ in range(int(k)):
            if not self.alive:
                break
            self.t += 1
            keep = sim.step(self.t)
            ticks.append([self.t, sim.p])
            self.alive = keep
            if self.t % self.TRIM_EVERY == 0:
                self._collect_prints(prints, max_prints)
                sim.trim_records()
                self._log_pos = 0
        self._collect_prints(prints, max_prints)
        return dict(t=self.t, ticks=ticks, prints=prints[-max_prints:],
                    fills=self._drain_fills(), orders=self._drain_events(),
                    alive=self.alive, stopped=sim.stopped_reason)

    def _collect_prints(self, out: list, cap: int) -> None:
        log = self.sim.trades_log
        start = max(self._log_pos, len(log) - cap)
        for row in log[start:]:
            tick, tid, taker, side, size, price, ba, sa = row
            out.append([tick, tid, float(price), float(size), side,
                        int(USER_ID in (ba, sa))])
        self._log_pos = len(log)
        if len(out) > cap:
            del out[:-cap]

    def _drain_fills(self) -> list[dict]:
        f = self.sim.user_fills
        self.sim.user_fills = []
        return f

    def _drain_events(self) -> list[dict]:
        e = self.sim.user_events
        self.sim.user_events = []
        return e

    # ── the human ───────────────────────────────────────────────────────────
    def place(self, side: str, kind: str, qty: Optional[float] = None,
              price: Optional[float] = None, eur_amount: Optional[float] = None) -> dict:
        if side not in ("buy", "sell") or kind not in ("market", "limit"):
            raise ValueError("bad order")
        n0 = len(self.sim.trades_log)
        self._log_pos = min(self._log_pos, n0)
        uo = self.sim.user_order(side, kind, qty=qty, price=price, eur_amount=eur_amount)
        prints: list[list] = []
        self._collect_prints(prints, 300)
        return dict(order=uo.view(), prints=prints, fills=self._drain_fills(),
                    orders=self._drain_events(), price=self.sim.p)

    def cancel(self, order_id: int) -> dict:
        uo = self.sim.user_cancel(int(order_id))
        return dict(order=(uo.view() if uo else None), orders=self._drain_events())

    # ── views ───────────────────────────────────────────────────────────────
    def book(self, levels: int = 18, group: float = 0.0) -> dict:
        """Aggregated price levels best-first, with the human's share.
        group > 0 buckets prices (bids down, asks up to the grid) like an
        exchange's price-increment selector; 0 = every distinct price."""
        out = {}
        for side, queue in (("bids", self.sim.book.bids), ("asks", self.sim.book.asks)):
            lv: list[list] = []
            for o in queue:
                sz = _rest_rcc(o)
                mine = sz if o.agent_id == USER_ID else 0.0
                px = float(o.price)
                if group > 0:
                    k = px / group
                    px = (math.floor(k + 1e-9) if side == "bids" else math.ceil(k - 1e-9)) * group
                if lv and lv[-1][0] == px:
                    lv[-1][1] += sz
                    lv[-1][2] += mine
                    lv[-1][3] += 1
                else:
                    if len(lv) >= levels:
                        break
                    lv.append([px, sz, mine, 1])
            out[side] = lv
        b = self.sim.book
        out["best_bid"] = b.best_bid
        out["best_ask"] = b.best_ask
        out["n_bids"], out["n_asks"] = b.depth_counts()
        return out

    def depth(self, band: float = 0.05) -> dict:
        """Cumulative depth within last*(1 +/- band) for the depth chart."""
        p = self.sim.p
        res = {}
        for side, queue, inside in (
                ("bids", self.sim.book.bids, lambda x: x >= p * (1 - band)),
                ("asks", self.sim.book.asks, lambda x: x <= p * (1 + band))):
            cum = 0.0
            pts = []
            for o in queue:
                if not inside(o.price):
                    break
                cum += _rest_rcc(o)
                pts.append([o.price, cum])
            res[side] = pts
        return res

    def account(self) -> dict:
        sim = self.sim
        le, lr = sim.locked()
        ae, ar = sim.available()
        return dict(eur=sim.user.eur, rcc=sim.user.btc, locked_eur=le, locked_rcc=lr,
                    avail_eur=ae, avail_rcc=ar, B=sim.pnl.B, Q=sim.pnl.Q,
                    pnl=sim.pnl.view(sim.p, sim.book.best_bid, sim.book.best_ask))

    def open_orders(self) -> list[dict]:
        return [uo.view() for uo in self.sim.user_orders.values() if uo.resting is not None]

    def market(self) -> dict:
        sim = self.sim
        alive = sum(1 for a in sim.agents if a.alive)
        bb, ba = sim.book.best_bid, sim.book.best_ask
        return dict(t=self.t, price=sim.p, x0=X0, alive=alive, population=2 * self.cfg.n,
                    arm=self.arm, stopped=sim.stopped_reason, volume=sim.volume,
                    hi=sim.hi, lo=sim.lo, best_bid=bb, best_ask=ba)

    def snapshot(self, levels: int = 18, group: float = 0.0) -> dict:
        return dict(market=self.market(), book=self.book(levels, group),
                    account=self.account(), open_orders=self.open_orders())

    def config(self) -> dict:
        c = self.cfg
        return dict(n=c.n, K=c.K, tp=c.tp, sl=c.sl, c=c.c, q=c.q, seed=c.seed,
                    arm=self.arm, x_0=c.x_0, capital_dist=c.capital_dist,
                    band_dist=c.band_dist, closing=c.closing, size_dist=c.size_dist,
                    band_cv=c.band_cv)
