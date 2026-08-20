"""
simulation_mvp.py — the Alpha Engine null model.

THE MODEL
---------
A closed two-currency market (BTC/EUR). n "longs" open positions by
buying BTC; n "shorts" open by selling it; side is fixed for life. At the
default f=0.5 every agent starts with the identical wallet (half EUR,
half BTC) — the sides differ only in direction.
There is no external price feed and no external money: THE PRICE IS THE
LAST TRADE. Every agent only ever does four things:

    1. JOIN        — an internal clock fires; the agent opens one position.
    2. LEAVE HAPPY — a take-profit limit RESTS in the book ("wake me at +1%").
    3. LEAVE SAD   — a stop-loss fires a market order ("get me out NOW").
    4. TIME OUT    — the clock fires while holding: exit at market.

Liquidity is other agents' unrealized profit (resting take-profits) plus
waiting wishes (resting entry residuals). Money is conserved exactly and
checked every tick; PnL is zero-sum; the matching engine never fills an
agent against its own resting paper (self-trade prevention, cancel-resting
policy) and no order ever rests at a non-positive price.

RANDOMNESS
----------
Everything random is rolled before the first tick or drawn from a stream
that is a pure function of (seed, purpose, tick); after that the run is
clockwork. Per-agent band multipliers are precomputed with decimal exp, so
the hot path is pure IEEE arithmetic: the same Config produces the same
run TO THE BIT on any machine. `python validate_simulation_mvp.py` proves
twelve invariants of all of the above in ~30 seconds.

THE FOUR BLOCKS (the model's dials; each draws on its own RNG stream, so
changing one cannot perturb the others)
-----------------------------------------------------------------------
    capital_dist : "pareto" | "normal"  — who gets how much money
    band_dist    : "fixed"  | "normal"  — TP/SL exit bands per agent
    closing      : "clock"  | "normal"  — how the timer exit triggers
    size_dist    : "fixed"  | "normal"  — per-agent order fraction q_i

RUNNING
-------
`python simulation_mvp.py` runs the block at the bottom of this file and
writes its outputs (figures, price + trades CSVs, optional narrative log
and raw tapes) next to the code. `scan_simulation_mvp.py` sweeps the
blocks; everything else lives in helper/.
"""

from __future__ import annotations

import csv
import itertools
import math
import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from typing import Optional, Self, TextIO

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = HERE                      # repo root
sys.path.insert(0, os.path.join(_ROOT, "helper"))
OUT = HERE                                   # run outputs land next to the code


# ═════════════════════════════════════════════════════════════════════════════
# 1. CONFIG — every knob of the null model, nothing else
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """Every knob of the null model. Defaults ARE the frozen null; the
    __main__ block at the bottom overrides some for interactive runs."""

    # ── world ────────────────────────────────────────────────────────────────
    n: int = 150              # agents PER SIDE (population = 2n)
    T: int = 100_000          # ticks
    seed: int = 9             # global seed; every stream derives from it
    K: float = 1_000_000.0    # total initial capital, EUR terms (K/2 per side)
    x_0: float = 100.0        # initial price (EUR per BTC); p(0) = x_0
    f: float = 0.5            # home-currency fraction of each wallet at init

    # ── the clock (what sets the market's pace) ──────────────────────────────
    c: float = 0.004          # pressure per tick; agent i fires every d_i/c ticks
    q: int = 8                # order fraction: each open deploys wealth/q

    # ── block: capital_dist — who gets how much money ────────────────────────
    capital_dist: str = "pareto"  # "pareto" (heavy tail) | "normal" (homogeneous)
    alpha: float = 1.5            # Pareto tail exponent          (pareto arm)
    capital_cv: float = 0.3       # sd = cv * mean                (normal arm)
    capital_floor: float = 0.05   # truncate below floor*mean     (normal arm)

    # ── block: band_dist — the exit bands ────────────────────────────────────
    band_dist: str = "fixed"  # "fixed" (everyone tp/sl) | "normal" (per-agent)
    tp: float = 0.01          # take-profit band (log distance from entry)
    sl: float = 0.01          # stop-loss band   (log distance from entry)
    band_cv: float = 0.3      # sd = cv * band                (normal arm)
    band_floor: float = 0.1   # truncate below floor*band     (normal arm)
    band_seed: Optional[int] = None  # separate seed for the band draw only
                                     # (None = the global seed): redraw band
                                     # luck while everything else stays fixed

    # ── block: closing — how the timer exit triggers ─────────────────────────
    closing: str = "clock"    # "clock" (pressure >= d) | "normal" (drawn time)
    close_cv: float = 0.3     # holding time ~ N(d/c, cv*d/c), floored at 1 tick

    # ── block: size_dist — per-agent order fraction ──────────────────────────
    # The default couples everything to capital: size ~ wealth/q and clock
    # d ~ K0, which makes every agent's volume throughput equal (size x rate
    # = c/q for all). "normal" gives each agent its own q_i on a dedicated
    # stream, decoupling bite size from the capital draw.
    size_dist: str = "fixed"  # "fixed" (everyone wealth/q) | "normal" (q_i)
    size_cv: float = 0.1      # q_i ~ N(q, size_cv*q), floored at 1.0

    # ── floors (derived when None) ───────────────────────────────────────────
    x_min: Optional[float] = None    # Pareto capital floor; K/(10n) when None
    epsilon: Optional[float] = None  # bankruptcy threshold; 0.01*x_min when None

    # ── outputs ──────────────────────────────────────────────────────────────
    save_csv: bool = True     # write price_btc_eur_<tag>.csv + trades_<tag>.csv
                              # at run end (sweeps pass False)
    save_tapes: bool = False  # write tape_<tag>.npy (tick prices) and
                              # tape_<tag>_events.npz (every print) at run end,
                              # so analyses can be re-sliced without re-running
    print_log: bool = True    # write log_<tag>.txt — one narrative line per
                              # decision point (order, trade, stop, timer,
                              # settle); validation by reading. Grows with
                              # event count: meant for small n/T runs

    def __post_init__(self) -> None:
        """Fill the derived parameters and fail loudly on nonsense."""
        if self.x_min is None:
            self.x_min = self.K / (self.n * 10)
        if self.epsilon is None:
            self.epsilon = 0.01 * self.x_min
        assert self.n >= 1 and self.K > 0 and self.x_0 > 0
        assert 0.0 < self.f <= 1.0 and self.alpha > 1.0
        assert self.capital_dist in ("pareto", "normal")
        assert self.size_dist in ("fixed", "normal")
        assert self.band_dist in ("fixed", "normal")
        assert self.closing in ("clock", "normal")
        assert self.c > 0 and self.q >= 1 and self.tp > 0 and self.sl > 0

    def summary(self) -> str:
        """One block naming the arm that actually runs (anti-lying-header rule)."""
        lines = []
        lines.append("Alpha Engine MVP — resolved configuration")
        lines.append(f"  population : {2 * self.n} agents ({self.n} long / {self.n} short)")
        lines.append(f"  capital    : K={self.K:,.0f} EUR, dist={self.capital_dist}"
                     f" (alpha={self.alpha})")
        lines.append(f"  price      : x_0={self.x_0}  (pair BTC/EUR: EUR per BTC)")
        lines.append(f"  clock      : c={self.c}  -> smallest agent fires every"
                     f" {1.0 / self.c:,.0f} ticks; order = wealth/{self.q}"
                     f" (size_dist={self.size_dist})")
        lines.append(f"  bands      : tp={self.tp} sl={self.sl}, dist={self.band_dist}"
                     f" (log-symmetric)")
        lines.append(f"  timer exit : {self.closing}")
        lines.append(f"  horizon    : T={self.T:,}  seed={self.seed}")
        return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ORDERS & TRADES — the only message types in the market
# ═════════════════════════════════════════════════════════════════════════════

# Global order-reference counter. Every order gets a unique, increasing oref;
# it is the time half of price-TIME priority (ties at one price level are
# broken by who arrived first = lower oref).
_next_oref = itertools.count(1)


@dataclass
class Order:
    """One limit order. A BUY gives EUR and wants BTC; a SELL gives BTC.

    The book denominates every order in the coin it DELIVERS (give_amt):
    a bid's give_amt is EUR, an ask's give_amt is BTC. `size` is kept as the
    BTC-equivalent view at the limit price, because the simulation's dust
    checks read it. Marketable orders use extreme limit prices
    (BUY at 1e18 / SELL at 1e-15 crosses everything)."""
    agent_id: str
    is_buy: bool
    price: float          # limit, EUR per BTC
    size: float           # BTC-equivalent view (back-annotated by the book)
    tick: int             # tick placed (kept for inspection; nothing expires)
    is_close: bool = False            # True for TP limits and close orders
    oref: int = field(default_factory=lambda: next(_next_oref))  # (factory, not logic)
    active: bool = True
    give_amt: float = 0.0             # remaining amount in the DELIVERED coin

    def init_give(self) -> None:
        """Set the delivered-coin amount from the (size, price) the caller gave."""
        if self.is_buy:
            self.give_amt = self.size * self.price   # delivers EUR
        else:
            self.give_amt = self.size                # delivers BTC

    def sync_size_view(self) -> None:
        """Refresh the BTC-equivalent `size` view after give_amt changed."""
        if self.is_buy:
            self.size = self.give_amt / self.price
        else:
            self.size = self.give_amt


@dataclass
class Trade:
    """One print: `size` BTC changed hands at `price` EUR/BTC."""
    price: float
    size: float           # BTC
    buy_agent: str
    sell_agent: str


def _bid_sort_key(o: Order) -> tuple:
    """Bids: best = HIGHEST price; ties by arrival (lower oref first)."""
    return (-o.price, o.oref)


def _ask_sort_key(o: Order) -> tuple:
    """Asks: best = LOWEST price; ties by arrival (lower oref first)."""
    return (o.price, o.oref)


# ═════════════════════════════════════════════════════════════════════════════
# 3. THE BOOK — a coin-symmetric central limit order book
# ═════════════════════════════════════════════════════════════════════════════

class Book:
    """The venue. Holds resting limits, matches marketable flow at MAKER
    prices (price-time priority), and reports trades. It never takes a
    position.

    Coin symmetry: every order lives in the coin it delivers; the single
    cross-coin conversion happens at match, at the maker's rate, through one
    side-agnostic expression. Dust thresholds are per-coin and equal in the
    initial gauge (eps_eur = eps_btc * x_0)."""

    def __init__(self, last_price: float, size_eps: float, x_ref: float) -> None:
        self.bids: list[Order] = []       # give EUR, want BTC
        self.asks: list[Order] = []       # give BTC, want EUR
        # ── THE PRICE. This float IS the market price: it moves only inside
        #    submit(), only when a trade prints, to that trade's price. ──
        self.last_price: float = last_price
        self.btc_eps: float = size_eps            # BTC dust
        self.eur_eps: float = size_eps * x_ref    # EUR dust (equal at the x_0 gauge)
        self._by_ref: dict[int, Order] = {}       # oref -> order, for cancel()

    # ── small helpers ────────────────────────────────────────────────────────
    def eps_of(self, o: Order) -> float:
        """The dust threshold in the order's OWN delivered coin."""
        if o.is_buy:
            return self.eur_eps
        return self.btc_eps

    def _live(self, queue: list[Order]) -> list[Order]:
        """The orders in `queue` that are still active and above dust."""
        result = []
        for o in queue:
            if o.active and o.give_amt > self.eps_of(o):
                result.append(o)
        return result

    # ── views (no side effects) ──────────────────────────────────────────────
    @property
    def best_bid(self) -> Optional[float]:
        """Highest live bid price, or None if the bid side is empty."""
        live = self._live(self.bids)
        if not live:
            return None
        return max(o.price for o in live)

    @property
    def best_ask(self) -> Optional[float]:
        """Lowest live ask price, or None if the ask side is empty."""
        live = self._live(self.asks)
        if not live:
            return None
        return min(o.price for o in live)

    def depth_counts(self) -> tuple[int, int]:
        """(number of live bids, number of live asks)."""
        return len(self._live(self.bids)), len(self._live(self.asks))

    def bid_btc(self) -> float:
        """Total live bid volume, BTC-equivalent at each bid's own price."""
        total = 0.0
        for o in self._live(self.bids):
            total += o.give_amt / o.price
        return float(total)

    def ask_btc(self) -> float:
        """Total live ask volume in BTC (asks already deliver BTC)."""
        total = 0.0
        for o in self._live(self.asks):
            total += o.give_amt
        return float(total)

    def snapshot(self) -> list[tuple[float, float, str]]:
        """Full book state as (price, btc_size, 'bid'|'ask') rows — for the
        deepest-book diagram in the orderbook plot."""
        rows = []
        for o in self._live(self.bids):
            rows.append((float(o.price), float(o.give_amt / o.price), "bid"))
        for o in self._live(self.asks):
            rows.append((float(o.price), float(o.give_amt), "ask"))
        return rows

    # ── mutation ─────────────────────────────────────────────────────────────
    def cancel(self, oref: int) -> None:
        """Deactivate the order with this reference (no error if gone)."""
        o = self._by_ref.get(oref)
        if o is not None:
            o.active = False

    def purge_agent(self, agent_id: str) -> None:
        """Remove every order of a (dead) agent from the book."""
        for o in self.bids + self.asks:
            if o.agent_id == agent_id:
                o.active = False
        self.bids = self._live(self.bids)
        self.asks = self._live(self.asks)

    def _rest(self, o: Order) -> None:
        """Park the (residual of the) order in its queue as passive depth."""
        if o.is_buy:
            self.bids.append(o)
        else:
            self.asks.append(o)
        self._by_ref[o.oref] = o

    # ── matching: one side-agnostic loop ─────────────────────────────────────
    def submit(self, o: Order, eur_budget: Optional[float] = None,
               btc_budget: Optional[float] = None,
               rest_residual: bool = True) -> list[Trade]:
        """Match an incoming order against the opposite queue.

        Walks the opposite side best-price-first, trading at each MAKER's
        price (the taker gets no price improvement beyond the maker's quote;
        this is what lets a market order move the price level by level).
        The optional budget clamps the incoming give_amt in its OWN coin —
        one solvency rule, both sides. The residual rests as passive depth
        unless rest_residual is False (market/IOC orders).

        Returns the trades printed. self.last_price advances to each trade's
        price as it prints — THIS is the emergent price evolving."""
        o.init_give()

        # solvency clamp, in the incoming order's own delivered coin
        if o.is_buy and eur_budget is not None:
            o.give_amt = min(o.give_amt, max(eur_budget, 0.0))
        if (not o.is_buy) and btc_budget is not None:
            o.give_amt = min(o.give_amt, max(btc_budget, 0.0))

        # the queue we eat from, sorted best-first (stable; ties by oref)
        if o.is_buy:
            queue = self.asks
            queue[:] = self._live(queue)
            queue.sort(key=_ask_sort_key)
        else:
            queue = self.bids
            queue[:] = self._live(queue)
            queue.sort(key=_bid_sort_key)

        trades: list[Trade] = []
        i = 0
        while o.give_amt > self.eps_of(o) and i < len(queue):
            maker = queue[i]

            # does the incoming limit cross this maker's price?
            if o.is_buy:
                crosses = maker.price <= o.price
            else:
                crosses = maker.price >= o.price
            if not crosses:
                break                      # book is sorted: nothing further crosses

            if maker.agent_id == o.agent_id:
                # SELF-TRADE PREVENTION (cancel-resting): an order never
                # fills against the same agent's own resting paper — the
                # incoming order expresses newer intent, so the stale quote
                # is canceled. (Skipping it instead would leave a standing
                # crossed book for other agents to trade through.)
                maker.active = False
                i += 1
                continue

            rate = maker.price             # ── trade at the MAKER's rate ──

            # both availabilities expressed in BTC through the same rate —
            # the one cross-coin conversion, side-agnostic:
            if o.is_buy:
                incoming_btc = o.give_amt / rate     # incoming gives EUR
                maker_btc = maker.give_amt           # maker gives BTC
            else:
                incoming_btc = o.give_amt            # incoming gives BTC
                maker_btc = maker.give_amt / rate    # maker gives EUR
            traded_btc = min(incoming_btc, maker_btc)
            if traded_btc <= self.btc_eps:
                i += 1                     # dust level: skip it
                continue
            traded_eur = traded_btc * rate

            # settle the two give_amts, each in its own coin
            if o.is_buy:
                buyer_id, seller_id = o.agent_id, maker.agent_id
                o.give_amt -= traded_eur
                maker.give_amt -= traded_btc
            else:
                buyer_id, seller_id = maker.agent_id, o.agent_id
                o.give_amt -= traded_btc
                maker.give_amt -= traded_eur

            trades.append(Trade(rate, traded_btc, buyer_id, seller_id))

            # ═════════ THE EMERGENT PRICE ═════════
            # The market price is, by definition, the last traded price.
            # No other line in this file writes it.
            self.last_price = rate
            # ═════════════════════════════════════

            if maker.give_amt <= self.eps_of(maker):
                maker.active = False       # maker fully consumed
                i += 1
            maker.sync_size_view()

        # drop consumed makers; rest (or drop) the incoming residual
        queue[:] = self._live(queue)
        o.sync_size_view()
        if o.give_amt > self.eps_of(o) and rest_residual:
            self._rest(o)
        return trades


# ═════════════════════════════════════════════════════════════════════════════
# 4. AGENTS — wallet, clock, position, exit bands
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Agent:
    """One market participant. Side is fixed for life.

    The position is the running trade tally (arXiv:2411.14068):
        pos_b = net BTC acquired by trading
        pos_q = net EUR received by trading (signed)
    so avg entry = -pos_q/pos_b and PnL at price p = p*pos_b + pos_q."""
    id: str               # "L0".."L{n-1}" longs, "S0".."S{n-1}" shorts. Safe as a
                          # string: ids never enter arithmetic, ordering (priority
                          # is by oref, iteration by array position) or, on the
                          # default path, any RNG stream — they only tag orders,
                          # trades and wallets. The one place needing a NUMBER
                          # (the closing="normal" hold-time stream) derives it
                          # from the label; see _step_closes_and_entries.
    is_long: bool         # long: EUR-heavy, buys BTC. short: BTC-heavy, sells BTC.
    eur: float            # EUR wallet
    btc: float            # BTC wallet
    K0: float             # initial capital (EUR terms) — sets the clock threshold
    d: float              # pressure threshold: fires every d/c ticks
    tp_band: float        # this agent's take-profit band (log distance)
    sl_band: float        # this agent's stop-loss band  (log distance)
    e_tp_up: Optional[float] = None   # e^{+tp_band}, e^{-tp_band},
    e_tp_dn: Optional[float] = None   # e^{+sl_band}, e^{-sl_band}, precomputed once via
    e_sl_up: Optional[float] = None   # decimal at build time so the hot path never
    e_sl_dn: Optional[float] = None   # calls platform libm exp (cross-machine bits)
    q_i: float = 8.0      # this agent's order fraction: each open deploys
                          # wealth/q_i (block 2d; cfg.q for everyone on the
                          # "fixed" default arm)

    phi: float = 0.0      # accumulated pressure — the internal clock
    alive: bool = True
    pos_b: float = 0.0    # position: net BTC from trading
    pos_q: float = 0.0    # position: net EUR from trading (signed)
    closing: bool = False           # committed to unwinding (SL or timer)
    close_reason: str = ""          # "sl" | "timer" | "" (TP path)
    realized_pnl: float = 0.0       # banked PnL, EUR leg
    realized_base: float = 0.0      # banked PnL, BTC leg (coins stay coins)
    tp_ref: Optional[int] = None    # oref of the resting TP limit
    entry_ref: Optional[int] = None # oref of the resting entry residual
    tp_pos_b: float = 0.0           # pos_b snapshot when the TP rested (growth check)
    sl_level: Optional[float] = None  # armed stop trigger price
    sl_is_buy: bool = False           # stop direction: buy back (short) / sell (long)
    opened_ever: bool = False
    open_tick: int = 0              # tick of the current open (closing="normal")
    close_deadline: int = 0         # drawn holding time in ticks (closing="normal")

    # ── views ────────────────────────────────────────────────────────────────
    def is_flat(self) -> bool:
        """No open position."""
        return self.pos_b == 0.0

    def avg_entry_price(self) -> float:
        """Average entry price of the open position, x̄ = -q/b.
        NaN for an exactly-flat position (a NaN entry makes
        every derived TP/SL level NaN, and NaN comparisons never trigger —
        the safe behaviour for a position that just zeroed out)."""
        if self.pos_b == 0:
            return math.nan
        return -self.pos_q / self.pos_b

    def total_pnl(self, p: float) -> float:
        """Realized + unrealized trade PnL in EUR at price p. Banked coins
        (realized_base) are marked at the CURRENT price — they are held
        coins, not frozen EUR — which keeps PnL exactly zero-sum."""
        open_pnl = p * self.pos_b + self.pos_q
        return self.realized_pnl + self.realized_base * p + open_pnl

    # ── the clock ────────────────────────────────────────────────────────────
    def accrue_pressure(self, c: float) -> None:
        """Pressure rises every tick while flat, and also while holding
        (impatience) — but not once the agent is committed to closing."""
        if self.is_flat() or not self.closing:
            self.phi += c

    def clock_fired(self) -> bool:
        """Has the internal clock reached its threshold?"""
        return self.alive and self.phi >= self.d

    def reset_pressure(self) -> None:
        """Restart the clock after acting."""
        self.phi = 0.0

    # ── exit prices (log-symmetric bands around the entry) ───────────────────
    def tp_price(self) -> float:
        """The take-profit limit price: one band ABOVE entry for a long
        (sell higher), one band BELOW for a short (buy back lower)."""
        x_entry = self.avg_entry_price()
        assert self.e_tp_up is not None and self.e_tp_dn is not None
        if self.is_long:
            return x_entry * self.e_tp_up
        return x_entry * self.e_tp_dn

    def sl_price(self) -> float:
        """The stop trigger price: one band BELOW entry for a long,
        one band ABOVE for a short."""
        x_entry = self.avg_entry_price()
        assert self.e_sl_up is not None and self.e_sl_dn is not None
        if self.is_long:
            return x_entry * self.e_sl_dn
        return x_entry * self.e_sl_up

    # ── order sizing (X-accounting: identical formula both tribes) ───────────
    def open_size_btc(self, q_frac: int, price: float) -> float:
        """Opening size in BTC. Wealth is measured in geometric-mean units
        X (1 X = p^-1/2 EUR = p^1/2 BTC), the numeraire-covariant measure;
        the order deploys wealth/q of it. The same expression for both
        tribes is what makes sizing side-symmetric. Capped at what the
        wallet can actually deliver."""
        if price <= 0:
            return 0.0
        root_p = math.sqrt(price)
        wealth_x = self.eur / root_p + self.btc * root_p
        size = (wealth_x / q_frac) / root_p
        if self.is_long:
            return min(size, self.eur / price)   # buys BTC: limited by EUR
        return min(size, self.btc)               # sells BTC: limited by BTC

    # ── cleanup after a round trip ───────────────────────────────────────────
    def clear_orders(self) -> None:
        """Forget refs and triggers once the position is fully settled."""
        self.tp_ref = None
        self.sl_level = None
        self.closing = False
        self.close_reason = ""


# ═════════════════════════════════════════════════════════════════════════════
# 5. INITIALISATION — the three dice
# ═════════════════════════════════════════════════════════════════════════════

def _norm_ppf(u: float, prec: int = 60) -> Decimal:
    """Wichura AS241 inverse normal CDF, evaluated in `decimal`.

    Why decimal: math.log / erfinv route through libm, which IEEE-754 does
    not require to be correctly rounded — ARM and x86 differ in the last
    bit, and the model is chaotic (one bit rewrites the run). Decimal's
    ln()/sqrt() have specified semantics: same bits on every CPU."""
    getcontext().prec = prec
    D = Decimal
    p = D(u)
    q = p - D("0.5")
    if abs(q) <= D("0.425"):
        r = D("0.180625") - q * q
        num = (((((((D("2509.0809287301226727") * r + D("33430.575583588128105")) * r + D("67265.770927008700853")) * r
               + D("45921.953931549871457")) * r + D("13731.693765509461125")) * r + D("1971.5909503065514427")) * r
               + D("133.14166789178437745")) * r + D("3.387132872796366608"))
        den = (((((((D("5226.495278852545925") * r + D("28729.085735721942674")) * r + D("39307.89580009271061")) * r
               + D("21213.794301586595867")) * r + D("5394.1960214247511077")) * r + D("687.1870074920579083")) * r
               + D("42.313330701600911252")) * r + D(1))
        return q * num / den
    if q < 0:
        r = p
    else:
        r = D(1) - p
    r = (-r.ln()).sqrt()
    if r <= D(5):
        r -= D("1.6")
        num = (((((((D("7.7454501427834140764e-4") * r + D("0.0227238449892691845833")) * r + D("0.24178072517745061177")) * r
               + D("1.27045825245236838258")) * r + D("3.64784832476320460504")) * r + D("5.7694972214606914055")) * r
               + D("4.6303378461565452959")) * r + D("1.42343711074968357734"))
        den = (((((((D("1.05075007164441684324e-9") * r + D("5.475938084995344946e-4")) * r + D("0.0151986665636164571966")) * r
               + D("0.14810397642748007459")) * r + D("0.68976733498510000455")) * r + D("1.6763848301838038494")) * r
               + D("2.05319162663775882187")) * r + D(1))
    else:
        r -= D(5)
        num = (((((((D("2.01033439929228813265e-7") * r + D("2.71155556874348757815e-5")) * r + D("0.0012426609473880784386")) * r
               + D("0.026532189526576123093")) * r + D("0.29656057182850489123")) * r + D("1.7848265399172913358")) * r
               + D("5.4637849111641143699")) * r + D("6.6579046435011037772"))
        den = (((((((D("2.04426310338993978564e-15") * r + D("1.4215117583164458887e-7")) * r + D("1.8463183175100546818e-5")) * r
               + D("7.868691311456132591e-4")) * r + D("0.0148753612908506148525")) * r + D("0.13692988092273580531")) * r
               + D("0.59983220655588793769")) * r + D(1))
    val = num / den
    if q < 0:
        return -val
    return val


def draw_capital(cfg: Config, rng: np.random.Generator, count: int) -> np.ndarray:
    """DICE 1 — who gets the money. Draw `count` capitals and rescale so the
    group sums to exactly K/2.

    Block 2a: "pareto" (default) draws from Pareto(x_min, alpha) — a few
    whales, many minnows; "normal" draws a homogeneous N(mean, cv*mean),
    truncated at floor*mean.

    Portability: rng.pareto()/np.sum() go through libm/SIMD whose rounding
    varies by CPU. Instead: exact uniforms from PCG64 (integer arithmetic,
    identical everywhere) pushed through the inverse CDF in `decimal`, and
    math.fsum for the correctly-rounded, order-independent total."""
    getcontext().prec = 60
    u = rng.random(count)                          # the portable bit stream
    if cfg.capital_dist == "normal":
        mu = Decimal(str(cfg.K / 2.0)) / Decimal(count)
        sd = mu * Decimal(str(cfg.capital_cv))
        lo = mu * Decimal(str(cfg.capital_floor))
        raw_list = []
        for ui in u:
            value = mu + sd * _norm_ppf(float(ui))
            raw_list.append(float(max(value, lo)))
        raw = np.array(raw_list)
    else:
        inv_a = Decimal(1) / Decimal(str(cfg.alpha))
        xmin = Decimal(str(cfg.x_min))
        raw_list = []
        for ui in u:
            value = (Decimal(1) - Decimal(float(ui))) ** (-inv_a) * xmin
            raw_list.append(float(value))
        raw = np.array(raw_list)
    target = cfg.K / 2.0
    return raw * (target / math.fsum(raw))


def build_agents(cfg: Config) -> list[Agent]:
    """Build the 2n agents: capitals (dice 1), wallets, clock thresholds,
    exit bands (block 2b), and phase jitter (dice 2).

    Clock thresholds: d = (K0/mean_K0), renormalised to mean(d) = 1, so big
    agents fire proportionally rarely and the market's pace is set purely
    by c (the mean is K/(2n) exactly, by the rescaled draw)."""
    rng = np.random.default_rng(cfg.seed)          # the MAIN stream: capital only
    k0_long = draw_capital(cfg, rng, cfg.n)
    k0_short = draw_capital(cfg, rng, cfg.n)

    # threshold normalisation (the mean, never the min: a min-statistic
    # would let one unlucky small agent set everyone's pace)
    all_k0 = np.concatenate([k0_long, k0_short])
    mu = float(all_k0.mean())
    d_raw = all_k0 / mu
    scale = float(d_raw.mean())                    # fix mean(d) = 1 exactly-ish

    agents: list[Agent] = []
    for i, k0 in enumerate(k0_long):               # LONGS first: EUR-heavy wallets
        eur = k0 * cfg.f
        btc = k0 * (1.0 - cfg.f) / cfg.x_0
        d = (float(k0) / mu) / scale
        agents.append(Agent(id=f"L{i}", is_long=True, eur=eur, btc=btc,
                            K0=float(k0), d=d, tp_band=cfg.tp, sl_band=cfg.sl))
    for i, k0 in enumerate(k0_short):              # SHORTS: BTC-heavy wallets
        btc = k0 * cfg.f / cfg.x_0
        eur = k0 * (1.0 - cfg.f)
        d = (float(k0) / mu) / scale
        agents.append(Agent(id=f"S{i}", is_long=False, eur=eur, btc=btc,
                            K0=float(k0), d=d, tp_band=cfg.tp, sl_band=cfg.sl))

    # DICE 2 — who wakes up first. phi_0 ~ U(0, d): agents start uniformly
    # in phase (steady state), on a DEDICATED stream so toggling jitter or
    # any later block can never shift the capital draw.
    jitter_rng = np.random.default_rng((cfg.seed or 0) + 90210)
    for a in agents:
        a.phi = float(jitter_rng.random()) * a.d

    # everyone starts on the shared fraction; block 2d may override below
    for a in agents:
        a.q_i = cfg.q

    # block 2b — per-agent exit bands. "fixed" leaves every band at cfg.tp /
    # cfg.sl (the frozen null: one shared price scale, the tp lattice).
    # "normal" draws each agent's bands once, on its own stream.
    if cfg.band_dist == "normal":
        if cfg.band_seed is not None:
            band_entropy = cfg.band_seed
        else:
            band_entropy = cfg.seed or 0
        band_rng = np.random.default_rng([band_entropy, 0xBA2D])
        for a in agents:
            tp_draw = cfg.tp * (1.0 + cfg.band_cv * float(band_rng.standard_normal()))
            sl_draw = cfg.sl * (1.0 + cfg.band_cv * float(band_rng.standard_normal()))
            a.tp_band = max(tp_draw, cfg.band_floor * cfg.tp)
            a.sl_band = max(sl_draw, cfg.band_floor * cfg.sl)

    # Each agent's four band multipliers e^{+-tp}, e^{+-sl} are precomputed
    # ONCE with decimal exp (correctly rounded, platform-independent): the
    # hot path never calls libm exp, so runs are bit-identical across
    # machines and compilers.
    getcontext().prec = 40
    def dexp(v: float) -> float:
        return float(Decimal(repr(v)).exp())
    for a in agents:
            a.e_tp_up = dexp(a.tp_band)
            a.e_tp_dn = dexp(-a.tp_band)
            a.e_sl_up = dexp(a.sl_band)
            a.e_sl_dn = dexp(-a.sl_band)

    # block 2d — per-agent order fraction. "fixed" keeps everyone at cfg.q
    # (the coupled default: equal volume flux, heterogeneous granularity).
    # "normal" draws q_i once per agent on its own stream: bite size becomes
    # an independent dial, decoupled from the capital-driven clock. Floor at
    # 1.0 = an order can deploy at most the agent's full wealth.
    if cfg.size_dist == "normal":
        size_rng = np.random.default_rng([cfg.seed or 0, 0x512E])
        for a in agents:
            q_draw = cfg.q * (1.0 + cfg.size_cv * float(size_rng.standard_normal()))
            a.q_i = max(1.0, q_draw)
    return agents


def cfg_tag(cfg: Config) -> str:
    """The minimal config designator appended to every output filename,
    e.g. "mvp_n150_s9_x0-1.0". Always names (n, seed, x_0); a non-default
    block switch appends itself, so variant runs never overwrite the null's
    files."""
    tag = f"mvp_n{cfg.n}_s{cfg.seed}_x0-{cfg.x_0}"
    if cfg.capital_dist != "pareto":
        tag += f"_cap-{cfg.capital_dist}"
    if cfg.band_dist != "fixed":
        tag += f"_band-{cfg.band_dist}"
    if cfg.closing != "clock":
        tag += f"_close-{cfg.closing}"
    if cfg.size_dist != "fixed":
        tag += f"_size-{cfg.size_dist}"
    if cfg.band_seed is not None:
        tag += f"_bseed{cfg.band_seed}"
    return tag


# ═════════════════════════════════════════════════════════════════════════════
# 6. THE SIMULATION — one tick, six steps
# ═════════════════════════════════════════════════════════════════════════════

class Simulation:
    """The tick loop. Each tick:

        1. pressure    — every clock advances
        2. rest TPs    — open positions park their take-profit in the book
                         and arm their stop line              (shuffled 0x59A7)
        3. stops       — price through a stop line -> committed to close
        3b. impatience — clock fires while holding -> committed to close
        4. closes      — committed closes walk the book as market orders
        5. entries     — fired flat agents send marketable-to-touch limits;
                         the residual RESTS as depth  (4+5 shuffled on 0xA1FA)
        6. re-fire     — still-stuck closes try again; settled round trips
                         bank their PnL
        7. bankruptcy  — agents at/under epsilon die; orders purged
        8. record      — series + trades logged; conservation asserted
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.agents = build_agents(cfg)
        self.book = Book(last_price=cfg.x_0,
                         size_eps=1e-12 / cfg.x_0,   # dust in the model's own units
                         x_ref=cfg.x_0)
        self.p = cfg.x_0                  # the recorded price; mirrors book.last_price
        self.t = 0
        self.stopped_reason: Optional[str] = None

        # conservation reference (nothing enters or leaves the market)
        self._eur_total0 = 0.0
        self._btc_total0 = 0.0
        for a in self.agents:
            self._eur_total0 += a.eur
            self._btc_total0 += a.btc

        # recorded series (plain lists; a dict would hide the schema)
        self.rec_tick: list[int] = []
        self.rec_price: list[float] = []
        self.rec_price_hi: list[float] = []   # highest print of the tick
        self.rec_price_lo: list[float] = []   # lowest  print of the tick
        #   (hi/lo = the intra-tick wick envelope; rec_price alone is the
        #    LAST print per tick and censors flash excursions entirely)
        self.rec_crossed: list[bool] = []
        self.rec_matched_btc: list[float] = []
        self.rec_matched_eur: list[float] = []
        self.rec_book_bids: list[int] = []       # live order COUNT per side
        self.rec_book_asks: list[int] = []
        self.rec_bid_btc: list[float] = []       # live order VOLUME per side (BTC)
        self.rec_ask_btc: list[float] = []
        self.rec_alive_long: list[int] = []
        self.rec_alive_short: list[int] = []
        self.rec_pnl_long: list[float] = []
        self.rec_pnl_short: list[float] = []

        # trade log for trades_mvp.csv: one row per print, tagged by the TAKER
        # (the incoming order that walked the book)
        self.trades_log: list[tuple] = []        # (tick, trade_id, taker, side,
                                                 #  size, price, buy_agent,
                                                 #  sell_agent) — [5]=price is
                                                 #  load-bearing for consumers
        self._next_trade_id = 1

        # deepest-book tracker for the orderbook plot
        self.deepest_tick = 0
        self.deepest_count = -1
        self.deepest_snapshot: list[tuple[float, float, str]] = []
        self.deepest_price = cfg.x_0

        self._trades_this_tick: list[Trade] = []

        # print_log: the narrative log (one line per decision point)
        self._logf: Optional[TextIO] = None
        self._runs: dict[str, list] = {}   # retry-compression state (_plog)
        if cfg.print_log:
            self._logf = open(os.path.join(OUT, f"log_{cfg_tag(cfg)}.txt"), "w")
            self._plog(f"CONFIG {cfg_tag(cfg)} | n={cfg.n}/side, T={cfg.T:,}, "
                       f"seed={cfg.seed}, x_0={cfg.x_0}")
            for a in self.agents:
                self._plog(f"t=0 INIT {a.id} {'long' if a.is_long else 'short'}"
                           f" | K0={a.K0:.2f} EUR={a.eur:.2f} BTC={a.btc:.4f}"
                           f" | timer d={a.d} q_i={a.q_i:.2f}"
                           f" tp={a.tp_band:.4f} sl={a.sl_band:.4f}")

    def _plog(self, msg: str) -> None:
        """One narrative-log line (no-op unless cfg.print_log). Market-close
        retry loops ("residual tries again next tick") are compressed PER
        AGENT: the first attempt is logged, repeats are counted across any
        interleaved lines, and one summary is written when the run resolves
        (the agent's close fills, or it does something else)."""
        if self._logf is None:
            return
        if self._logf is None:
            return
        parts = msg.split(" ", 1)
        body = parts[1] if parts[0].startswith("t=") and len(parts) == 2 else msg
        agent = body.split(" ", 1)[0]

        run = self._runs.get(agent)
        if run is not None and run[0] == body:
            run[1] += 1                          # suppressed repeat
            return
        if run is not None:
            self._flush_run(agent, filled=False)  # agent moved on to something else
        for a in [a for a, r in self._runs.items() if f"taker {a} " in msg]:
            self._flush_run(a, filled=True)       # a trade resolved that run
        if "[market, close" in body:
            self._runs[agent] = [body, 0]         # start tracking a retry run
        self._logf.write(msg + "\n")

    def _flush_run(self, agent: str, filled: bool) -> None:
        """Summary line for a compressed retry run."""
        body, n = self._runs.pop(agent)
        if not n:
            return
        empty = "bid side was empty" if " sell " in f" {body} " else "ask side was empty"
        outcome = "close filled" if filled else "close attempt moved on"
        if self._logf is None:
            return
        self._logf.write(f"t={self.t} {agent} {outcome} after {n} retries "
                         f"({empty})\n")

    # ── plumbing ─────────────────────────────────────────────────────────────
    def alive(self) -> list[Agent]:
        """The living agents, in array order (longs 0..n-1, shorts n..2n-1)."""
        result = []
        for a in self.agents:
            if a.alive:
                result.append(a)
        return result

    def _submit(self, o: Order, eur_budget: Optional[float] = None,
                btc_budget: Optional[float] = None,
                rest_residual: bool = True) -> None:
        """Send an order to the book; apply the resulting trades to both
        wallets; advance the recorded price. The taker is o's agent."""
        if self._logf:
            kind = "close/tp" if o.is_close else "entry"
            style = ("market" if (o.is_buy and o.price > 1e12) or
                     ((not o.is_buy) and o.price < 1e-9) else "limit")
            px_txt = "MKT" if style == "market" else f"{o.price:.6f}"
            self._plog(f"t={self.t} {o.agent_id} PLACE "
                       f"{'buy' if o.is_buy else 'sell'} {o.size:.6f} @ "
                       f"{px_txt} [{style}, {kind}"
                       f"{', rests' if rest_residual else ''}]")
        trades = self.book.submit(o, eur_budget=eur_budget,
                                  btc_budget=btc_budget,
                                  rest_residual=rest_residual)
        if trades:
            self._apply_trades(trades)
            # the recorded price follows the book's last trade
            self.p = self.book.last_price
        taker_side = "buy" if o.is_buy else "sell"
        for tr in trades:
            self.trades_log.append((self.t, self._next_trade_id, o.agent_id,
                                    taker_side, tr.size, tr.price,
                                    tr.buy_agent, tr.sell_agent))
            self._next_trade_id += 1
            if self._logf:
                mk = tr.sell_agent if o.is_buy else tr.buy_agent
                tag = "  <-- SELF-TRADE" if tr.buy_agent == tr.sell_agent else ""
                self._plog(f"t={self.t} TRADE#{self._next_trade_id - 1} "
                           f"{tr.buy_agent} buys {tr.size:.6f} from "
                           f"{tr.sell_agent} @ {tr.price:.6f} | taker "
                           f"{o.agent_id} {taker_side}, maker {mk} | "
                           f"px -> {self.book.last_price:.6f}{tag}")
        self._trades_this_tick.extend(trades)

    def _apply_trades(self, trades: list[Trade]) -> None:
        """Move the money. Each trade produces two conserved wallet updates:
        buyer +BTC/-EUR, seller -BTC/+EUR — and the same deltas land in the
        position tallies (that IS the PnL bookkeeping)."""
        by_id = {}
        for a in self.agents:
            by_id[a.id] = a
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

    # ── the close promise (own-coin exits, the verified symmetric rule) ──────
    def _close_undelivered(self, a: Agent) -> bool:
        """Is this position's close promise still undelivered?

        Each tribe promises its OWN coin: a long delivers the BTC it bought
        (done when pos_b is dust); a short re-spends the entry EUR it
        received (done when pos_q is dust) — each side settles in its own
        coin, so the two sides' exit rules are exact mirrors."""
        assert self.cfg.x_min is not None
        if not a.is_long:
            return a.pos_q > 1e-9 * self.cfg.x_min       # EUR still to spend
        return abs(a.pos_b) > 1e-9 / self.cfg.x_0        # BTC still to deliver

    def _settle_if_flat(self, a: Agent) -> None:
        """If the close promise is delivered, the round trip is over: bank
        the residuals and re-arm. Coins are banked AS COINS (realized_base)
        — freezing dust BTC at an EUR mark would break zero-sum once the
        price wanders e-folds."""
        if a.sl_level is None:
            return                    # no armed position to settle
        if self._close_undelivered(a):
            return                    # promise not yet delivered
        if self._logf:
            self._plog(f"t={self.t} {a.id} SETTLE: bank b={a.pos_b:+.6f} "
                       f"q={a.pos_q:+.2f} | wallet EUR={a.eur:.2f} "
                       f"BTC={a.btc:.4f} | clock reset")
        a.realized_base += a.pos_b    # leftover coins -> the BTC bank
        a.realized_pnl += a.pos_q     # leftover euros -> the EUR bank
        a.pos_b = 0.0
        a.pos_q = 0.0
        if a.tp_ref is not None:
            self.book.cancel(a.tp_ref)
        if a.entry_ref is not None:
            self.book.cancel(a.entry_ref)
            a.entry_ref = None
        a.clear_orders()
        a.reset_pressure()            # the clock restarts for the next round

    def _timer_due(self, a: Agent, t: int) -> bool:
        """Block 2c — is the timer exit due for a HOLDING agent?

        "clock" (default): the same pressure clock that opened the agent has
        fired again (phi >= d) — impatience, no new parameter.
        "normal": a holding time drawn at open (N(d/c, cv*d/c), >= 1 tick)
        has elapsed."""
        if self.cfg.closing == "clock":
            return a.clock_fired()
        return t - a.open_tick >= a.close_deadline

    # ── tick steps ───────────────────────────────────────────────────────────
    def _step_pressure(self) -> None:
        """Step 1. Every living agent's clock advances — while flat (drives
        the next open) and while holding (drives the timer exit) — but not
        once committed to closing."""
        for a in self.alive():
            a.accrue_pressure(self.cfg.c)

    def _step_rest_take_profits(self, t: int) -> None:
        """Step 2. Every open, non-closing position without a resting TP
        parks one in the book — a long SELLS one band above its entry, a
        short BUYS one band below. These resting winners-in-waiting ARE the
        book's standing depth. The stop line is armed at the same time.

        Iteration order is shuffled on the dedicated (seed, 0x59A7, t)
        stream: submitting can trade immediately (a TP through the touch
        prints at once), so array order would be a standing seat privilege.

        A short's TP is a SPEND order: it re-spends the entry EUR pos_q, so
        its BTC size is pos_q / tp_price — by construction e^tp more BTC
        than was sold. That over-buy is the own-coin promise, not a bug."""
        cfg = self.cfg
        candidates = self.alive()
        if len(candidates) > 1:
            shuffle_rng = np.random.default_rng(
                np.random.SeedSequence((cfg.seed, 0x59A7, t)))
            order = shuffle_rng.permutation(len(candidates))
            shuffled = []
            for i in order:
                shuffled.append(candidates[i])
            candidates = shuffled

        for a in candidates:
            # the resting entry kept filling after the TP rested: the
            # position GREW, the TP size is stale -> cancel; it re-rests below
            if (a.tp_ref is not None and not a.closing
                    and abs(a.pos_b) > abs(a.tp_pos_b) + 1e-9 / cfg.x_0):
                self.book.cancel(a.tp_ref)
                a.tp_ref = None

            if a.pos_b != 0 and a.avg_entry_price() <= 0.0:
                continue          # neg-x_bar residual: timer-only (see Config)
            if a.pos_b != 0 and not a.closing and a.tp_ref is None:
                if a.is_long:
                    # long TP: SELL the held BTC one band above entry
                    o = Order(a.id, is_buy=False, price=a.tp_price(),
                              size=a.pos_b, tick=t, is_close=True)
                    a.tp_ref = o.oref
                    a.tp_pos_b = a.pos_b
                    self._submit(o, btc_budget=max(a.btc, 0.0))
                else:
                    tp_px = a.tp_price()
                    # short TP: BUY back one band below entry, spending
                    # the entry EUR (size = pos_q/tp_price; budget = that
                    # EUR — the e^tp over-buy is the promise)
                    size = a.pos_q / tp_px
                    budget = max(0.0, min(a.eur, a.pos_q))
                    o = Order(a.id, is_buy=True, price=tp_px,
                              size=size, tick=t, is_close=True)
                    a.tp_ref = o.oref
                    a.tp_pos_b = a.pos_b
                    self._submit(o, eur_budget=budget)
                # arm the stop line for this position
                a.sl_level = a.sl_price()
                a.sl_is_buy = not a.is_long
                self._settle_if_flat(a)   # the TP may have filled instantly

    def _step_trigger_stops(self, t: int, p_prev: float) -> tuple[list, list]:
        """Step 3. A last price at/through an armed stop line commits the
        position to a market close THIS tick: cancel its resting orders,
        mark it closing, and stage the close order.

        Returns (sl_buys, sl_sells): lists of (agent, size) staged closes.
        A long's stop SELLS the BTC it holds; a short's stop BUYS with the
        entry EUR it holds (sized at p_prev; the spend budget is the true
        terminator)."""
        sl_buys: list[tuple] = []
        sl_sells: list[tuple] = []
        for a in self.alive():
            if a.pos_b != 0 and a.avg_entry_price() <= 0.0:
                continue      # neg-x_bar residual: stale stop is void
            if a.pos_b != 0 and not a.closing and a.sl_level is not None:
                px = self.book.last_price
                if a.sl_is_buy:
                    hit = px >= a.sl_level     # short stops out when price RISES
                else:
                    hit = px <= a.sl_level     # long stops out when price FALLS
                if hit:
                    a.closing = True
                    a.close_reason = "sl"
                    if self._logf:
                        self._plog(f"t={t} {a.id} STOP hit: last {px:.6f} "
                                   f"through level {a.sl_level:.6f} -> closing"
                                   f" (pos_b={a.pos_b:+.6f})")
                    if a.tp_ref is not None:
                        self.book.cancel(a.tp_ref)
                        a.tp_ref = None
                    if a.entry_ref is not None:
                        self.book.cancel(a.entry_ref)
                        a.entry_ref = None
                    if a.pos_b > 0 and a.is_long:
                        # long cover: sell the position, capped by held BTC
                        qty = min(a.pos_b, max(a.btc, 0.0))
                        sl_sells.append((a, qty))
                    else:
                        # short cover: spend the remaining entry EUR at market
                        qty = min(a.pos_q, max(a.eur, 0.0)) / p_prev
                        sl_buys.append((a, qty))
        return sl_buys, sl_sells

    def _step_impatience(self, t: int) -> None:
        """Step 3b. The timer exit: a HOLDING agent whose timer is due
        (block 2c) exits at market — mark closing, cancel resting orders;
        the close itself is fired by step 6 this same tick. If the promise
        is already delivered, just settle."""
        for a in self.alive():
            if a.pos_b != 0 and not a.closing and self._timer_due(a, t):
                a.reset_pressure()
                if not self._close_undelivered(a):
                    self._settle_if_flat(a)
                    continue
                a.closing = True
                a.close_reason = "timer"
                if self._logf:
                    self._plog(f"t={t} {a.id} TIMER due -> closing "
                               f"(pos_b={a.pos_b:+.6f}, pos_q={a.pos_q:+.2f})")
                if a.tp_ref is not None:
                    self.book.cancel(a.tp_ref)
                    a.tp_ref = None
                if a.entry_ref is not None:
                    self.book.cancel(a.entry_ref)
                    a.entry_ref = None

    def _step_closes_and_entries(self, t: int, sl_buys: list, sl_sells: list) -> None:
        """Steps 4+5. First the staged stop closes walk the book as market
        orders (extreme limit prices cross everything; the wallet budget is
        the solvency clamp). Then the fired flat agents enter.

        ENTRIES are marketable-to-touch: a long bids AT the best ask, a
        short offers AT the best bid — the minimal aggression that lets the
        price form at all (quoting at last is a fixed point: every fill at
        last, last never moves). What crosses fills; the remainder RESTS as
        real passive depth. One resting entry per agent — a re-fire while
        flat cancels-and-replaces it at the live touch.

        Both submission sequences are shuffled on the shared per-tick
        (seed, 0xA1FA, t) stream: sequential submission gives earlier
        orders better prices, so array order would be a seat privilege."""
        cfg = self.cfg
        shuffle_rng = np.random.default_rng([cfg.seed or 0, 0xA1FA, t])

        # ── staged stop closes, shuffled among themselves ──
        closes = sl_buys + sl_sells
        if len(closes) > 1:
            order = shuffle_rng.permutation(len(closes))
        else:
            order = range(len(closes))
        for i in order:
            a, size = closes[i]
            if not self._close_undelivered(a):
                self._settle_if_flat(a)       # already home-flat: bank, don't trade
                continue
            if not a.is_long:
                # short cover: market BUY, spend capped at the entry EUR left
                budget = max(0.0, min(a.eur, a.pos_q))
                o = Order(a.id, is_buy=True, price=1e18, size=size, tick=t,
                          is_close=True)
                self._submit(o, eur_budget=budget, rest_residual=False)
            else:
                # long cover: market SELL of the held BTC
                o = Order(a.id, is_buy=False, price=1e-15, size=size, tick=t,
                          is_close=True)
                self._submit(o, btc_budget=max(a.btc, 0.0), rest_residual=False)

        # ── entries: flat, not closing, clock fired ──
        firing = []
        for a in self.alive():
            if a.pos_b == 0 and not a.closing and a.clock_fired():
                firing.append(a)
        if len(firing) > 1:
            order = shuffle_rng.permutation(len(firing))
        else:
            order = range(len(firing))
        for i in order:
            a = firing[i]
            a.reset_pressure()
            if a.entry_ref is not None:                  # cancel-and-replace
                self.book.cancel(a.entry_ref)
                a.entry_ref = None
            # quote AT the opposite touch (fall back to last on an empty side)
            if a.is_long:
                px = self.book.best_ask
                if px is None:
                    px = self.book.last_price
            else:
                px = self.book.best_bid
                if px is None:
                    px = self.book.last_price
            size = a.open_size_btc(a.q_i, px)   # q_i == cfg.q on the fixed arm
            if size <= 0 or px <= 0:
                continue
            if a.is_long:
                size = min(size, max(a.eur, 0.0) / px)   # maker-fill solvency cap
            else:
                size = min(size, max(a.btc, 0.0))
            if size <= 1e-12 / cfg.x_0:
                continue                                  # dust entry: skip
            a.opened_ever = True
            if cfg.closing == "normal" and a.pos_b == 0:
                # block 2c "normal": draw this round trip's holding time on a
                # dedicated per-agent-per-tick stream (default "clock" never
                # draws). SeedSequence needs INTEGERS, so the string id is
                # decomposed into (side, number): "L12" -> (0, 12), "S3" -> (1, 3)
                side_code = 0 if a.is_long else 1
                number = int(a.id[1:])
                hold_rng = np.random.default_rng(
                    [cfg.seed or 0, 0xC10C, t, side_code, number])
                mean_hold = a.d / cfg.c
                draw = mean_hold * (1.0 + cfg.close_cv * float(hold_rng.standard_normal()))
                a.close_deadline = max(1, int(round(draw)))
                a.open_tick = t
            if a.is_long:
                o = Order(a.id, is_buy=True, price=px, size=size, tick=t)
                self._submit(o, eur_budget=max(a.eur, 0.0), rest_residual=True)
            else:
                o = Order(a.id, is_buy=False, price=px, size=size, tick=t)
                self._submit(o, btc_budget=max(a.btc, 0.0), rest_residual=True)
            # remember the resting residual (if any survived above dust)
            if o.active and o.size > self.book.eps_of(o):
                a.entry_ref = o.oref
            else:
                a.entry_ref = None

    def _fire_close(self, a: Agent, t: int) -> None:
        """Fire (or re-fire) the market close for a committed position.

        Short: a SPEND order — convert the remaining entry EUR at market
        (the eur_budget is the true terminator; the 4x size just gives
        headroom for cheap asks). Long: sell all held position BTC into the
        bids. A residual simply tries again next tick."""
        assert self.cfg.x_min is not None
        if not self._close_undelivered(a):
            self._settle_if_flat(a)
            return
        if not a.is_long:
            eur_left = a.pos_q
            if eur_left > 1e-9 * self.cfg.x_min:
                size = 4.0 * eur_left / max(self.book.last_price, 1e-300)
                o = Order(a.id, is_buy=True, price=1e18, size=size, tick=t,
                          is_close=True)
                self._submit(o, eur_budget=max(0.0, min(a.eur, eur_left)),
                             rest_residual=False)
            return
        if a.pos_b > 1e-12 / self.cfg.x_0:
            o = Order(a.id, is_buy=False, price=1e-15, size=a.pos_b, tick=t,
                      is_close=True)
            self._submit(o, btc_budget=max(a.btc, 0.0), rest_residual=False)

    def _step_refire_and_settle(self, t: int) -> None:
        """Step 6. Housekeeping after the tick's flow:
          - a TP whose resting order is gone was filled passively: drop the ref
          - a committed close still undelivered re-fires its market order
          - every delivered promise settles (banks PnL, re-arms the clock)

        ORDERING: _fire_close prints market orders, so iteration order is
        a seat privilege. The loop therefore runs in a fresh random
        permutation every tick, on its own (seed, 0x6E1C, t) stream — no
        agent owns a structurally early seat."""
        live_refs = set()
        for o in self.book.bids + self.book.asks:
            if o.active:
                live_refs.add(o.oref)
        agents_6 = self.alive()
        if len(agents_6) > 1:
            shuffle_rng = np.random.default_rng(
                np.random.SeedSequence((self.cfg.seed, 0x6E1C, t)))
            order = shuffle_rng.permutation(len(agents_6))
            shuffled = []
            for i in order:
                shuffled.append(agents_6[i])
            agents_6 = shuffled
        for a in agents_6:
            if a.tp_ref is not None and a.tp_ref not in live_refs:
                a.tp_ref = None                    # TP fully filled: exited happy
            if a.closing and self._close_undelivered(a):
                self._fire_close(a, t)             # stuck close: try again now
            self._settle_if_flat(a)

    def _step_bankruptcy(self) -> None:
        """Step 7. An agent whose PRICE-INVARIANT capital (eur + btc*x_0)
        is at/under epsilon is dead: purge its resting orders. The x_0
        valuation kills only genuine insolvency, not a transient mark."""
        x0 = self.cfg.x_0
        for a in self.alive():
            assert self.cfg.epsilon is not None
            bank_val = a.eur + a.btc * x0
            if bank_val <= self.cfg.epsilon:
                a.alive = False
                self.book.purge_agent(a.id)
                a.clear_orders()

    def _step_record(self, t: int) -> None:
        """Step 8. Log the tick's series; assert conservation; track the
        deepest book state for the orderbook plot."""
        # conservation, checked EVERY tick: the market is closed — nothing
        # enters or leaves
        eur_total = 0.0
        btc_total = 0.0
        for a in self.agents:
            eur_total += a.eur
            btc_total += a.btc
        assert abs(eur_total - self._eur_total0) < 1e-3 * max(abs(self._eur_total0), 1), \
            "EUR not conserved"
        assert abs(btc_total - self._btc_total0) < 1e-3 * max(abs(self._btc_total0), 1), \
            "BTC not conserved"

        n_bids, n_asks = self.book.depth_counts()
        alive_long = 0
        alive_short = 0
        pnl_long = 0.0
        pnl_short = 0.0
        for a in self.agents:
            if a.alive:
                if a.is_long:
                    alive_long += 1
                else:
                    alive_short += 1
            if a.is_long:
                pnl_long += a.total_pnl(self.p)
            else:
                pnl_short += a.total_pnl(self.p)
        matched_btc = 0.0
        matched_eur = 0.0
        for tr in self._trades_this_tick:
            matched_btc += tr.size
            matched_eur += tr.size * tr.price

        if self._trades_this_tick:
            tick_hi = self._trades_this_tick[0].price
            tick_lo = tick_hi
            for tr in self._trades_this_tick:
                if tr.price > tick_hi:
                    tick_hi = tr.price
                if tr.price < tick_lo:
                    tick_lo = tr.price
        else:
            tick_hi = self.p          # quiet tick: envelope collapses to the price
            tick_lo = self.p

        self.rec_tick.append(t)
        self.rec_price.append(self.p)
        self.rec_price_hi.append(float(tick_hi))
        self.rec_price_lo.append(float(tick_lo))
        self.rec_crossed.append(bool(self._trades_this_tick))
        self.rec_matched_btc.append(float(matched_btc))
        self.rec_matched_eur.append(float(matched_eur))
        self.rec_book_bids.append(n_bids)
        self.rec_book_asks.append(n_asks)
        self.rec_bid_btc.append(self.book.bid_btc())
        self.rec_ask_btc.append(self.book.ask_btc())
        self.rec_alive_long.append(alive_long)
        self.rec_alive_short.append(alive_short)
        self.rec_pnl_long.append(float(pnl_long))
        self.rec_pnl_short.append(float(pnl_short))

        # deepest book state (by live order count)
        if n_bids + n_asks > self.deepest_count:
            self.deepest_count = n_bids + n_asks
            self.deepest_tick = t
            self.deepest_snapshot = self.book.snapshot()
            self.deepest_price = float(self.book.last_price)

    # ── one tick, assembled ──────────────────────────────────────────────────
    def step(self, t: int) -> bool:
        """Run one tick. Returns False when the run should stop."""
        self.t = t
        p_prev = self.book.last_price
        self.p = p_prev
        self._trades_this_tick = []

        self._step_pressure()                                   # 1
        self._step_rest_take_profits(t)                         # 2
        sl_buys, sl_sells = self._step_trigger_stops(t, p_prev)  # 3
        self._step_impatience(t)                                # 3b
        self._step_closes_and_entries(t, sl_buys, sl_sells)     # 4+5
        self._step_refire_and_settle(t)                         # 6
        self._step_bankruptcy()                                 # 7
        self._step_record(t)                                    # 8

        alive_total = self.rec_alive_long[-1] + self.rec_alive_short[-1]
        if alive_total == 0:
            self.stopped_reason = "all agents dead"
            return False
        return True

    def run(self) -> Self:
        """Run the full horizon."""
        for t in range(1, self.cfg.T + 1):
            keep_going = self.step(t)
            if not keep_going:
                break
        if self.stopped_reason is None:
            self.stopped_reason = "reached T"
        if self.cfg.save_csv:
            self.write_price_csv()
            self.write_trades_csv()
        if self.cfg.save_tapes:
            base = os.path.join(OUT, f"tape_{cfg_tag(self.cfg)}")
            np.save(base + ".npy", np.asarray(self.rec_price))
            np.savez_compressed(base + "_events.npz",
                                p=np.asarray([r[5] for r in self.trades_log]),
                                t=np.asarray([r[0] for r in self.trades_log]))
        if self._logf:
            self._plog(f"t={self.cfg.T} END p={self.p:.6f} "
                       f"ln(p/x0)={math.log(self.p / self.cfg.x_0):+.4f}")
            for a in list(self._runs):
                self._flush_run(a, filled=False)
            self._logf.close()
            self._logf = None
        return self

    def summary(self) -> str:
        """Human-readable end-of-run report."""
        alive_long = self.rec_alive_long[-1]
        alive_short = self.rec_alive_short[-1]
        crossed = 0
        for c in self.rec_crossed:
            if c:
                crossed += 1
        lines = []
        lines.append("Alpha Engine MVP — run summary")
        lines.append(f"  stopped        : {self.stopped_reason} at tick {self.t}")
        lines.append(f"  agents alive   : {alive_long + alive_short}/{2 * self.cfg.n}"
                     f"  (long {alive_long} / short {alive_short})")
        lines.append(f"  ticks w/ trade : {crossed} / {self.t}")
        lines.append(f"  price BTC/EUR  : {self.cfg.x_0} -> {self.p:.6f}"
                     f"  (ln p/x0 = {math.log(self.p / self.cfg.x_0):+.4f})")
        lines.append(f"  trades printed : {len(self.trades_log):,}")
        lines.append(f"  PnL zero-sum   : long {self.rec_pnl_long[-1]:+,.2f}"
                     f" / short {self.rec_pnl_short[-1]:+,.2f} EUR")
        return "\n".join(lines)

    # ── CSV outputs ──────────────────────────────────────────────────────────
    def write_price_csv(self, path: Optional[str] = None) -> str:
        """The emergent price series. Column named after the pair BTC/EUR
        (base BTC, quote EUR — the value is EUR per BTC, same number the
        engine trades at)."""
        if path is None:
            path = os.path.join(OUT, f"price_btc_eur_{cfg_tag(self.cfg)}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tick", "BTC/EUR"])
            for t, p in zip(self.rec_tick, self.rec_price):
                w.writerow([t, repr(float(p))])   # repr(float()) = full precision,
                                                  # plain text (np.float64's repr
                                                  # would write "np.float64(...)")
        return path

    def write_trades_csv(self, path: Optional[str] = None) -> str:
        """The market trades, one row per print — BOTH parties. The first six
        columns are unchanged (agent_id/buy_sell = the TAKER, size in BTC);
        appended: buy_agent, sell_agent, maker_id. A per-agent ledger needs
        the appended columns — filtering on agent_id alone sees only the
        taker half of an agent's fills (~50% of its volume)."""
        if path is None:
            path = os.path.join(OUT, f"trades_{cfg_tag(self.cfg)}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tick", "trade_id", "agent_id", "buy_sell", "size",
                        "price", "buy_agent", "sell_agent", "maker_id"])
            for row in self.trades_log:
                tick, trade_id, agent_id, side, size, price, ba, sa = row
                maker = sa if side == "buy" else ba
                w.writerow([tick, trade_id, agent_id, side, repr(float(size)),
                            repr(float(price)), ba, sa, maker])
        return path


# ═════════════════════════════════════════════════════════════════════════════
# 7. DEFAULT RUN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import time
    t = time.time()

    # ---------------- edit these to override defaults ----------------
    N = 2          # agents per side
    T = 150_000      # ticks
    SEED = 9
    CAPITAL_DIST = "normal"   # block 2a: "pareto" | "normal"
    BAND_DIST = "fixed"       # block 2b: "fixed"  | "normal"
    CLOSING = "normal"         # block 2c: "clock"  | "normal"
    SIZE_DIST = "normal"       # block 2d: "fixed"  | "normal"
    SHOW = True               # pop the figures in the IDE (they save either way)
    # --------------------------------------------
    cfg = Config(n=N, T=T, seed=SEED, capital_dist=CAPITAL_DIST,
                 band_dist=BAND_DIST, closing=CLOSING, size_dist=SIZE_DIST)
    print(cfg.summary())
    sim = Simulation(cfg).run()
    print(sim.summary())
    tag = cfg_tag(cfg)
    print("wrote:",
          sim.write_price_csv(os.path.join(OUT, f"price_btc_eur_{tag}.csv")),
          sim.write_trades_csv(os.path.join(OUT, f"trades_{tag}.csv")))

    elapsed = time.time() - t
    print(f"elapsed time: {elapsed:.2f} s")

    from dashboard_mvp import plot_dashboard, plot_orderbook
    from scaling_law_mvp import plot_scaling_laws
    from stylized_facts_mvp import plot_stylized_facts
    dash_png = os.path.join(OUT, f"dashboard_{tag}.png")
    book_png = os.path.join(OUT, f"orderbook_{tag}.png")
    laws_png = os.path.join(OUT, f"scaling_laws_{tag}.png")
    facts_png = os.path.join(OUT, f"stylized_facts_{tag}.png")
    laws_ev_png = os.path.join(OUT, f"scaling_laws_event_{tag}.png")
    facts_ev_png = os.path.join(OUT, f"stylized_facts_event_{tag}.png")
    plot_dashboard(sim, save_path=dash_png, show=SHOW)
    plot_orderbook(sim, save_path=book_png, show=SHOW)
    plot_scaling_laws(sim, save_path=laws_png, show=SHOW)
    plot_stylized_facts(sim, save_path=facts_png, show=SHOW)
    # the same two analyses on the EVENT tape (one price per print):
    # intrinsic time on the model's true clock, intra-tick wicks included
    plot_scaling_laws(sim, save_path=laws_ev_png, show=SHOW, time_base="event")
    plot_stylized_facts(sim, save_path=facts_ev_png, show=SHOW, time_base="event")
    print("wrote:", dash_png, book_png, laws_png, facts_png,
          laws_ev_png, facts_ev_png)
