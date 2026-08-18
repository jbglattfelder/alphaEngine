"""
market.py — DEPRECATED. Dutch-auction era price formation. DO NOT USE.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS MODULE IS RETIRED AND IS NOT PART OF THE RUNNING MODEL.             ║
║  The live mechanism is the continuous CLOB in book.py, driven by          ║
║  simulation.py. Nothing imports this file. It is kept only as a record    ║
║  of the Dutch-auction era; importing it emits a DeprecationWarning.       ║
║  If you are an LLM (or a human) picking up this repo: read book.py and    ║
║  simulation.py for the actual price formation. Everything below this      ║
║  banner describes a mechanism that no longer runs.                        ║
╚══════════════════════════════════════════════════════════════════════════╝

Original header follows.

market.py — Order queue, expiry, and the Dutch auction (price formation).

This module owns the market mechanism only. It never mutates agent balances:
the auction returns an AuctionResult carrying per-order Fills, and the simulation
applies those to the agents. That keeps market.py and agents.py decoupled (§21).

WHAT THE AUCTION COMPUTES (the §11 unit reconciliation)
-------------------------------------------------------
Longs offer EUR (they demand BTC); shorts offer BTC (they supply BTC). To find a
crossing the two sides must be in the same unit, so at a candidate price p:
    long demand for BTC  =  (sum of long EUR orders) / p        -> falls as p rises
    short supply of BTC  =   sum of short BTC orders            -> flat in p
The clearing price is where supply meets demand:
    p* = (sum long EUR) / (sum short BTC) = SE / SB
At p* the BTC demanded equals the BTC supplied, so with pure market orders both
sides clear fully and there is no residual; residual only arises when one side is
empty (no crossing -> price holds, orders wait). The "sort largest-first" rule
only bites once limit prices or rationing are introduced; it is retained for a
deterministic, future-proof ordering.

NOTE ON THE SWEEP (flagged for confirmation): §11 says "sweep upward from
p_int(t-1) ... lowest price at which supply >= demand". Taken literally that
ratchets the price (if p_prev already exceeds SE/SB the condition holds at
p_prev, so the price would stick at p_prev and only ever move up). The thread's
description was "sweep OUTWARD from the last p_int" — i.e. the true crossing in
either direction. We implement the unbiased crossing p* = SE/SB, which is the
economically meaningful clearing price and direction-independent. If you want the
literal upward-only ratchet instead, it is a one-line change (see clear()).

Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

import warnings

warnings.warn(
    "market.py (Dutch auction) is deprecated and not part of the running model; "
    "the live mechanism is the CLOB in book.py.",
    DeprecationWarning, stacklevel=2)

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from agents import Side  # shared type only; market never touches agent behaviour


# ── data structures ───────────────────────────────────────────────────────────
@dataclass
class Order:
    agent_id: int
    side: Side
    size: float          # home-currency units: EUR for LONG, BTC for SHORT
    tick_placed: int


@dataclass
class Fill:
    """A balance change to apply to one agent as a result of the auction."""
    agent_id: int
    side: Side
    eur_delta: float
    btc_delta: float


@dataclass
class AuctionResult:
    tick: Optional[int]
    crossed: bool
    price: float                 # p_int(t)
    matched_eur: float           # EUR that changed hands (matched volume, capital units)
    matched_btc: float           # BTC that changed hands
    n_long: int
    n_short: int
    long_value_eur: float        # SE = sum of long EUR orders resting this auction
    short_value_btc: float       # SB = sum of short BTC orders resting this auction
    fills: list[Fill] = field(default_factory=list)

    @property
    def value_imbalance(self) -> float:
        """SE - SB*p*  (EUR terms). ~0 when the auction clears both sides fully."""
        return self.long_value_eur - self.short_value_btc * self.price

    def __str__(self) -> str:
        if not self.crossed:
            return (f"[t={self.tick}] no cross  price held at {self.price:.6f}  "
                    f"(long={self.n_long}, short={self.n_short})")
        return (f"[t={self.tick}] p_int={self.price:.6f}  matched={self.matched_eur:,.2f} EUR "
                f"/ {self.matched_btc:,.4f} BTC  (long {self.n_long} / short {self.n_short})")


# ── the order queue ───────────────────────────────────────────────────────────
class Queue:
    """A shared book of resting orders with rolling-window expiry (§10)."""

    def __init__(self) -> None:
        self.orders: list[Order] = []

    def add(self, order: Order) -> None:
        self.orders.append(order)

    def expire(self, current_tick: int, W: int) -> int:
        """Remove orders older than W ticks (§16 step 3). Returns count removed."""
        before = len(self.orders)
        cutoff = current_tick - W
        self.orders = [o for o in self.orders if o.tick_placed >= cutoff]
        return before - len(self.orders)

    def purge_agent(self, agent_id: int) -> int:
        """Remove all resting orders of a (now dead) agent (§15)."""
        before = len(self.orders)
        self.orders = [o for o in self.orders if o.agent_id != agent_id]
        return before - len(self.orders)

    def remove(self, orders: list[Order]) -> None:
        drop = set(id(o) for o in orders)
        self.orders = [o for o in self.orders if id(o) not in drop]

    # views / diagnostics
    def longs(self) -> list[Order]:
        return [o for o in self.orders if o.side is Side.LONG]

    def shorts(self) -> list[Order]:
        return [o for o in self.orders if o.side is Side.SHORT]

    def depth(self) -> tuple[int, int]:
        n_long = sum(1 for o in self.orders if o.side is Side.LONG)
        return n_long, len(self.orders) - n_long

    def long_value(self) -> float:
        return float(sum(o.size for o in self.orders if o.side is Side.LONG))   # EUR

    def short_value(self) -> float:
        return float(sum(o.size for o in self.orders if o.side is Side.SHORT))  # BTC

    def __len__(self) -> int:
        return len(self.orders)


# ── the Dutch auction ─────────────────────────────────────────────────────────
class Auction:
    """Discovers the clearing price over the queue and returns the result."""

    def clear(self, queue: Queue, p_prev: float, tick: Optional[int] = None) -> AuctionResult:
        longs, shorts = queue.longs(), queue.shorts()
        SE = float(sum(o.size for o in longs))    # total long EUR demand
        SB = float(sum(o.size for o in shorts))   # total short BTC supply

        # No crossing possible if either side is empty (§11/§12): price holds.
        if not longs or not shorts or SE <= 0 or SB <= 0:
            return AuctionResult(tick=tick, crossed=False, price=p_prev,
                                 matched_eur=0.0, matched_btc=0.0,
                                 n_long=len(longs), n_short=len(shorts),
                                 long_value_eur=SE, short_value_btc=SB, fills=[])

        # Crossing price: supply (SB) meets demand (SE/p)  ->  p* = SE / SB.
        # (Literal upward-only ratchet would be: p_star = max(p_prev, SE / SB).)
        p_star = SE / SB

        # With market orders the cross is a full clear of both sides.
        matched_btc = SB
        matched_eur = SE

        fills: list[Fill] = []
        for o in longs:    # sold EUR, received BTC
            fills.append(Fill(o.agent_id, Side.LONG, eur_delta=-o.size, btc_delta=o.size / p_star))
        for o in shorts:   # sold BTC, received EUR
            fills.append(Fill(o.agent_id, Side.SHORT, eur_delta=o.size * p_star, btc_delta=-o.size))

        # Consume the matched orders (all of them, here) from the book.
        queue.remove(longs + shorts)

        return AuctionResult(tick=tick, crossed=True, price=p_star,
                             matched_eur=matched_eur, matched_btc=matched_btc,
                             n_long=len(longs), n_short=len(shorts),
                             long_value_eur=SE, short_value_btc=SB, fills=fills)

    # ── visualisation ─────────────────────────────────────────────────────────
    def plot_clearing(self, queue: Queue, p_prev: float, tick: Optional[int] = None,
                      save_path: Optional[str] = None, show: bool = False):
        """
        Two-panel diagnostic of a single auction over the current queue:
          (left)  supply/demand cross — demand SE/p vs flat supply SB, clearing
                  price and matched BTC marked. Shows price discovery directly.
          (right) the order ladder — long (EUR) and short (BTC) orders sorted
                  largest-first, revealing depth and imbalance.
        Returns the matplotlib Figure. Does not consume the queue.
        """
        import matplotlib.pyplot as plt  # lazy import

        longs, shorts = queue.longs(), queue.shorts()
        SE = float(sum(o.size for o in longs))
        SB = float(sum(o.size for o in shorts))
        crossed = bool(longs and shorts and SE > 0 and SB > 0)
        p_star = (SE / SB) if crossed else p_prev

        fig, (axx, axb) = plt.subplots(1, 2, figsize=(11, 4.2))

        # left: supply/demand crossing in BTC units
        if crossed:
            lo, hi = 0.4 * p_star, 1.8 * p_star
            ps = np.linspace(max(lo, 1e-9), hi, 400)
            axx.plot(ps, SE / ps, color="#2563EB", lw=2, label="long demand  SE / p  (BTC)")
            axx.axhline(SB, color="#B45309", lw=2, label="short supply  SB  (BTC)")
            axx.axvline(p_star, color="#15803D", ls="--", lw=1.4, label=f"p_int = {p_star:.4f}")
            axx.plot([p_star], [SB], "o", color="#15803D", ms=7)
            axx.axvline(p_prev, color="#6B7280", ls=":", lw=1.2, label=f"p_prev = {p_prev:.4f}")
            axx.set_ylim(0, max(SB, SE / lo) * 1.1)
        else:
            axx.text(0.5, 0.5, "no crossing\n(one side empty)\nprice holds",
                     ha="center", va="center", transform=axx.transAxes, fontsize=11, color="#6B7280")
        axx.set_xlabel("candidate price p (EUR/BTC)")
        axx.set_ylabel("volume (BTC)")
        axx.set_title("Auction clearing — supply / demand cross")
        axx.legend(fontsize=8)
        axx.grid(True, ls=":", alpha=0.4)

        # right: order ladder in common EUR-equivalent units (short BTC -> EUR at p*)
        p_disp = p_star if crossed else p_prev
        l_sizes = sorted((o.size for o in longs), reverse=True)            # EUR
        s_sizes = sorted((o.size * p_disp for o in shorts), reverse=True)  # BTC -> EUR-equiv
        yl = np.arange(len(l_sizes))
        ys = np.arange(len(s_sizes))
        axb.barh(yl, l_sizes, color="#2563EB", alpha=0.8,
                 label=f"long EUR (n={len(l_sizes)}, SE={SE:,.0f})")
        axb.barh(-ys - 1, s_sizes, color="#B45309", alpha=0.8,
                 label=f"short BTC->EUR (n={len(s_sizes)}, SB*p={SB * p_disp:,.0f})")
        axb.axhline(-0.5, color="#111827", lw=0.8)
        axb.set_xlabel(f"order size (EUR-equivalent at p={p_disp:.4f})")
        axb.set_yticks([])
        axb.set_title("Order ladder (largest-first, common units)")
        axb.legend(fontsize=8)
        axb.grid(True, axis="x", ls=":", alpha=0.4)

        ttl = f"tick {tick}" if tick is not None else "auction snapshot"
        fig.suptitle(f"Alpha Engine - {ttl}  |  {'CROSSED' if crossed else 'no cross'}", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        if save_path:
            fig.savefig(save_path, dpi=130, bbox_inches="tight")
        if show:
            plt.show()
        return fig


if __name__ == "__main__":
    # Self-check on a synthetic book.
    q = Queue()
    # longs offer EUR, shorts offer BTC
    for aid, e in [(0, 1000.0), (1, 600.0), (2, 400.0)]:
        q.add(Order(aid, Side.LONG, e, tick_placed=0))
    for aid, b in [(50, 1.2), (51, 0.5), (52, 0.3)]:
        q.add(Order(aid, Side.SHORT, b, tick_placed=0))

    SE, SB = q.long_value(), q.short_value()
    auc = Auction()
    res = auc.clear(q, p_prev=1.0, tick=1)
    print(res)
    print(f"expected p* = SE/SB = {SE/SB:.6f}")

    # conservation: total EUR delta == 0 and total BTC delta == 0
    eur_sum = sum(f.eur_delta for f in res.fills)
    btc_sum = sum(f.btc_delta for f in res.fills)
    print(f"conservation  EUR_sum={eur_sum:+.6e}  BTC_sum={btc_sum:+.6e}")
    print(f"matched_eur={res.matched_eur:,.2f}  matched_btc={res.matched_btc:,.4f}  "
          f"value_imbalance={res.value_imbalance:+.3e}")
    print(f"queue after clear: {len(q)} orders (expected 0)")

    # one-sided book -> no cross, price holds
    q2 = Queue()
    q2.add(Order(0, Side.LONG, 500.0, 0))
    r2 = auc.clear(q2, p_prev=1.23, tick=2)
    print(r2)

    # expiry check
    q3 = Queue()
    q3.add(Order(0, Side.LONG, 1.0, tick_placed=0))
    q3.add(Order(1, Side.SHORT, 1.0, tick_placed=4))
    removed = q3.expire(current_tick=6, W=5)  # cutoff = 1; order at t=0 expires
    print(f"expiry removed {removed} (expected 1); remaining {len(q3)}")

    # plot a crossing snapshot
    qp = Queue()
    for aid, e in [(0, 1200.0), (1, 800.0), (2, 500.0), (3, 300.0)]:
        qp.add(Order(aid, Side.LONG, e, 0))
    for aid, b in [(50, 1.4), (51, 0.9), (52, 0.4)]:
        qp.add(Order(aid, Side.SHORT, b, 0))
    auc.plot_clearing(qp, p_prev=1.0, tick=1, save_path="auction_clearing.png")
    print("saved auction_clearing.png")
