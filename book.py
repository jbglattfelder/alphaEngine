"""
book.py — Central limit order book (CLOB) and continuous matching engine.

The venue. Owned by the house (its first functional, non-counterparty role): it
holds resting limit orders, matches marketable flow against them at maker prices,
and reports the trades. It never takes a position and risks no capital.

UNITS (uniform, unlike the Dutch-auction era):
    every order is a quantity of BTC at a limit price in EUR/BTC.
    BUY  s BTC @ P : pay up to s*P EUR, receive BTC.   (bid)
    SELL s BTC @ P : give s BTC, receive s*P EUR.       (ask)
This dissolves the old EUR-vs-BTC denomination asymmetry: both sides quote the
same (size, price) object; direction is the only difference.

PRICE is emergent: last trade price. A marketable order walks the opposite side
level by level (price-time priority), trading at each resting order's price, so
the price cannot gap in one step — the book's levels are the resistance.

Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from agents import Side  # LONG/SHORT used only for Fill tagging (position bookkeeping)


class Dir(Enum):
    BUY = "buy"       # wants BTC (bid)
    SELL = "sell"     # offers BTC (ask)


_oref = itertools.count(1)


@dataclass
class LimitOrder:
    agent_id: int
    direction: Dir
    price: float           # EUR/BTC limit
    size: float            # BTC remaining
    tick_placed: int
    is_close: bool = False        # True for TP limits / triggered-SL orders (reduce-only)
    pos_side: Side = Side.LONG    # the owning agent's Lane side (for Fill tagging)
    oref: int = field(default_factory=lambda: next(_oref))
    active: bool = True


@dataclass
class Trade:
    price: float
    size: float                   # BTC
    buy_agent: int
    sell_agent: int
    buy_side: Side
    sell_side: Side


@dataclass
class Fill:
    """Balance change to apply to one agent (kept compatible with simulation._apply_fills)."""
    agent_id: int
    side: Side
    eur_delta: float
    btc_delta: float


class Book:
    """Central limit order book with continuous price-time-priority matching."""

    def __init__(self, last_price: float, size_eps: float = 1e-12) -> None:
        # size_eps is the dust threshold in BTC. BTC quantities scale as 1/x_0,
        # so a fixed 1e-12 is an ABSOLUTE scale hiding in a scale-free model:
        # it broke the exact x_0 scale-invariance below x_0 ~ 2^-8 (§3e).
        # The simulation passes 1e-12 / x_0 so the threshold lives in the
        # model's own units.
        self.bids: list[LimitOrder] = []   # BUY, best = highest price
        self.asks: list[LimitOrder] = []   # SELL, best = lowest price
        self.last_price: float = last_price
        self.size_eps: float = size_eps
        self._by_ref: dict[int, LimitOrder] = {}

    # ── views ─────────────────────────────────────────────────────────────────
    def _live(self, book: list[LimitOrder]) -> list[LimitOrder]:
        return [o for o in book if o.active and o.size > self.size_eps]

    @property
    def best_bid(self) -> Optional[float]:
        live = self._live(self.bids)
        return max(o.price for o in live) if live else None

    @property
    def best_ask(self) -> Optional[float]:
        live = self._live(self.asks)
        return min(o.price for o in live) if live else None

    def mid(self) -> float:
        b, a = self.best_bid, self.best_ask
        if b is not None and a is not None:
            return 0.5 * (b + a)
        return self.last_price

    def depth(self) -> tuple[int, int]:
        return len(self._live(self.bids)), len(self._live(self.asks))

    def bid_btc(self) -> float:
        return float(sum(o.size for o in self._live(self.bids)))

    def ask_btc(self) -> float:
        return float(sum(o.size for o in self._live(self.asks)))

    # ── mutation ──────────────────────────────────────────────────────────────
    def cancel(self, oref: int) -> None:
        o = self._by_ref.get(oref)
        if o is not None:
            o.active = False

    def _rest(self, o: LimitOrder) -> None:
        (self.bids if o.direction is Dir.BUY else self.asks).append(o)
        self._by_ref[o.oref] = o

    def _prune(self) -> None:
        self.bids = self._live(self.bids)
        self.asks = self._live(self.asks)

    def expire(self, current_tick: int, W: int) -> int:
        """Expire OPEN limits older than W ticks. TP/close limits never expire
        (they live with the position until filled or cancelled)."""
        cutoff = current_tick - W
        n = 0
        for o in self.bids + self.asks:
            if o.active and (not o.is_close) and o.tick_placed < cutoff:
                o.active = False
                n += 1
        self._prune()
        return n

    def purge_agent(self, agent_id: int) -> None:
        for o in self.bids + self.asks:
            if o.agent_id == agent_id:
                o.active = False
        self._prune()

    # ── matching ──────────────────────────────────────────────────────────────
    def submit(self, o: LimitOrder, eur_budget: Optional[float] = None,
               rest_residual: bool = True, btc_budget: Optional[float] = None) -> list[Trade]:
        """Insert a limit order, matching it against the opposite side at maker
        prices (price-time priority). Residual rests unless rest_residual is False
        (marketable IOC: opens rest, stop/market closes do not). For BUY orders an
        eur_budget caps total spend so a cover can never overspend (solvency)."""
        trades: list[Trade] = []
        spent = 0.0
        if o.direction is Dir.BUY:
            self.asks = self._live(self.asks)
            self.asks.sort(key=lambda x: (x.price, x.oref))          # best (low) first
            i = 0
            while o.size > self.size_eps and i < len(self.asks):
                resting = self.asks[i]
                if resting.price > o.price:      # no cross
                    break
                ts = min(o.size, resting.size)
                if eur_budget is not None:                           # solvency clamp
                    room = (eur_budget - spent) / resting.price
                    if room <= self.size_eps:
                        break
                    ts = min(ts, room)
                tp = resting.price               # trade at maker price
                trades.append(Trade(tp, ts, o.agent_id, resting.agent_id,
                                    o.pos_side, resting.pos_side))
                o.size -= ts
                resting.size -= ts
                spent += ts * tp
                self.last_price = tp
                if resting.size <= self.size_eps:
                    resting.active = False
                    i += 1
            self.asks = self._live(self.asks)
            if o.size > self.size_eps and rest_residual:
                self._rest(o)
        else:  # SELL
            self.bids = self._live(self.bids)
            self.bids.sort(key=lambda x: (-x.price, x.oref))         # best (high) first
            i = 0
            sold = 0.0
            while o.size > self.size_eps and i < len(self.bids):
                resting = self.bids[i]
                if resting.price < o.price:      # no cross
                    break
                ts = min(o.size, resting.size)
                if btc_budget is not None:                           # solvency clamp (mirror of eur_budget)
                    room = btc_budget - sold
                    if room <= self.size_eps:
                        break
                    ts = min(ts, room)
                tp = resting.price
                trades.append(Trade(tp, ts, resting.agent_id, o.agent_id,
                                    resting.pos_side, o.pos_side))
                o.size -= ts
                resting.size -= ts
                sold += ts
                self.last_price = tp
                if resting.size <= self.size_eps:
                    resting.active = False
                    i += 1
            self.bids = self._live(self.bids)
            if o.size > self.size_eps and rest_residual:
                self._rest(o)
        return trades


def trades_to_fills(trades: list[Trade]) -> list[Fill]:
    """Two conserved fills per trade: buyer +BTC/-EUR, seller -BTC/+EUR."""
    fills: list[Fill] = []
    for t in trades:
        eur = t.size * t.price
        fills.append(Fill(t.buy_agent,  t.buy_side,  eur_delta=-eur, btc_delta=+t.size))
        fills.append(Fill(t.sell_agent, t.sell_side, eur_delta=+eur, btc_delta=-t.size))
    return fills
