"""
book_coin.py — the X-program applied to the venue (HANDOFF-master §4.9 endgame).

THE RULE
--------
Every order is a SELL of the coin it delivers: a bid GIVES EUR, an ask GIVES
BTC. Each order's size, residual, and dust test live in ITS OWN coin; the only
cross-coin conversion happens at MATCH, at the maker's rate, through one
side-agnostic expression. "Buy BTC with EUR" and "sell EUR for BTC" are the
same object. This removes the base-currency privilege of book.py (all sizes
BTC; eur_budget divides by price while btc_budget doesn't; dust in BTC only).

WHAT IT DOES AND DOES NOT CLAIM
-------------------------------
It makes the VENUE's arithmetic side-symmetric. It does not (cannot) remove
the remaining gauge choices, each documented where it lives:
  - the print (last_price) is reported in EUR/BTC — a reporting gauge; matching
    never reads it except as the empty-book fallback both sides share;
  - per-coin dust: eps_btc = size_eps, eps_eur = size_eps * x_ref (equal in the
    initial gauge; fixed thereafter — a convention, stated);
  - price-time priority and the shuffle stream are side-symmetric already.
If a bias survives THIS book, it is demarcated to live outside the venue.

INTERFACE
---------
Drop-in for book.py's Book: same constructor shape, same submit(LimitOrder,
eur_budget=, btc_budget=, rest_residual=) signature, same Trade list out, same
views (best_bid/best_ask/mid/depth/bid_btc/ask_btc), cancel/purge/expire.
Internally an order converts to (give, amount, rate); LimitOrder.size is kept
back-annotated as the BTC-equivalent view at the limit rate so existing
callers' dust checks keep working.
"""

from __future__ import annotations

from typing import Optional

from agents import Side
from book import Dir, LimitOrder, Trade


class CoinBook:
    def __init__(self, last_price: float, size_eps: float = 1e-12,
                 x_ref: float = 1.0) -> None:
        self.eur_givers: list[LimitOrder] = []   # bids: give EUR, want BTC
        self.btc_givers: list[LimitOrder] = []   # asks: give BTC, want EUR
        self.last_price: float = last_price
        self.size_eps: float = size_eps               # BTC dust
        self.eur_eps: float = size_eps * x_ref        # EUR dust (equal in the initial gauge)
        self._by_ref: dict[int, LimitOrder] = {}

    # ── internal per-coin state on the order object ──────────────────────────
    @staticmethod
    def _init_coin(o: LimitOrder) -> None:
        if not hasattr(o, "give_amt"):
            if o.direction is Dir.BUY:      # gives EUR: amount = size_btc * limit
                o.give_amt = o.size * o.price
            else:                            # gives BTC
                o.give_amt = o.size

    def _sync_view(self, o: LimitOrder) -> None:
        """Back-annotate .size as the BTC-equivalent view (callers' dust checks)."""
        o.size = (o.give_amt / o.price) if o.direction is Dir.BUY else o.give_amt

    def _eps(self, o: LimitOrder) -> float:
        return self.eur_eps if o.direction is Dir.BUY else self.size_eps

    def _live(self, q: list[LimitOrder]) -> list[LimitOrder]:
        return [o for o in q if o.active and o.give_amt > self._eps(o)]

    # ── views (identical semantics to book.py) ───────────────────────────────
    @property
    def bids(self) -> list[LimitOrder]:
        return self.eur_givers

    @property
    def asks(self) -> list[LimitOrder]:
        return self.btc_givers

    @property
    def best_bid(self) -> Optional[float]:
        live = self._live(self.eur_givers)
        return max(o.price for o in live) if live else None

    @property
    def best_ask(self) -> Optional[float]:
        live = self._live(self.btc_givers)
        return min(o.price for o in live) if live else None

    def mid(self) -> float:
        b, a = self.best_bid, self.best_ask
        if b is not None and a is not None:
            return 0.5 * (b + a)
        return self.last_price

    def depth(self) -> tuple[int, int]:
        return len(self._live(self.eur_givers)), len(self._live(self.btc_givers))

    def bid_btc(self) -> float:
        # EUR-givers' BTC-equivalent at their own rates (a view, not a ledger)
        return float(sum(o.give_amt / o.price for o in self._live(self.eur_givers)))

    def ask_btc(self) -> float:
        return float(sum(o.give_amt for o in self._live(self.btc_givers)))

    # ── mutation ─────────────────────────────────────────────────────────────
    def cancel(self, oref: int) -> None:
        o = self._by_ref.get(oref)
        if o is not None:
            o.active = False

    def purge_agent(self, agent_id: int) -> None:
        for o in self.eur_givers + self.btc_givers:
            if o.agent_id == agent_id:
                o.active = False
        self.eur_givers = self._live(self.eur_givers)
        self.btc_givers = self._live(self.btc_givers)

    def expire(self, current_tick: int, W: int) -> int:
        cutoff = current_tick - W
        n = 0
        for o in self.eur_givers + self.btc_givers:
            if o.active and (not o.is_close) and o.tick_placed < cutoff:
                o.active = False
                n += 1
        self.eur_givers = self._live(self.eur_givers)
        self.btc_givers = self._live(self.btc_givers)
        return n

    def _rest(self, o: LimitOrder) -> None:
        (self.eur_givers if o.direction is Dir.BUY else self.btc_givers).append(o)
        self._by_ref[o.oref] = o

    # ── matching: one side-agnostic loop ─────────────────────────────────────
    def submit(self, o: LimitOrder, eur_budget: Optional[float] = None,
               rest_residual: bool = True, btc_budget: Optional[float] = None) -> list[Trade]:
        """Match the incoming giver against the opposite queue at maker rates.

        The budgets clamp the incoming order's GIVE amount in its own coin
        (eur_budget for EUR-givers, btc_budget for BTC-givers) — one rule, both
        sides, applied before the walk; the per-level cross-coin conversion is
        the SAME expression whichever coin the maker gives.
        """
        self._init_coin(o)
        if o.direction is Dir.BUY and eur_budget is not None:
            o.give_amt = min(o.give_amt, max(eur_budget, 0.0))
        if o.direction is Dir.SELL and btc_budget is not None:
            o.give_amt = min(o.give_amt, max(btc_budget, 0.0))

        incoming_gives_eur = o.direction is Dir.BUY
        queue = self.btc_givers if incoming_gives_eur else self.eur_givers
        queue[:] = self._live(queue)
        # best rate first: lowest ask for an EUR-giver, highest bid for a BTC-giver
        queue.sort(key=(lambda x: (x.price, x.oref)) if incoming_gives_eur
                   else (lambda x: (-x.price, x.oref)))

        trades: list[Trade] = []
        i = 0
        while o.give_amt > self._eps(o) and i < len(queue):
            maker = queue[i]
            crosses = (maker.price <= o.price) if incoming_gives_eur else (maker.price >= o.price)
            if not crosses:
                break
            r = maker.price                    # trade at the maker's rate
            # both availabilities expressed in BTC through the SAME rate r —
            # the one conversion, side-agnostic:
            inc_btc = (o.give_amt / r) if incoming_gives_eur else o.give_amt
            mak_btc = maker.give_amt if incoming_gives_eur else (maker.give_amt / r)
            q_btc = min(inc_btc, mak_btc)
            if q_btc <= self.size_eps:
                i += 1
                continue
            q_eur = q_btc * r
            if incoming_gives_eur:
                buyer, seller = o, maker
                o.give_amt -= q_eur
                maker.give_amt -= q_btc
            else:
                buyer, seller = maker, o
                o.give_amt -= q_btc
                maker.give_amt -= q_eur
            trades.append(Trade(r, q_btc, buyer.agent_id, seller.agent_id,
                                buyer.pos_side, seller.pos_side))
            self.last_price = r
            if maker.give_amt <= self._eps(maker):
                maker.active = False
                i += 1
            self._sync_view(maker)
        queue[:] = self._live(queue)
        self._sync_view(o)
        if o.give_amt > self._eps(o) and rest_residual:
            self._rest(o)
        return trades
