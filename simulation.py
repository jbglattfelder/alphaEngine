"""
simulation.py — the main loop. Wires the modules together; no business logic.

MECHANISM: continuous CLOB (book.py). The Dutch auction (market.py) is RETIRED
and no longer imported; see market.py's deprecation header.

Each tick:
    1. pressure           (phi up on flat agents; K marked at p_int(t-1))
    2. TP resting         (every open position rests a take-profit limit; these
                           reduce-only limits ARE the book's two-sided depth.
                           The SL trigger line is armed at the same time.)
    3. SL triggers        (last price through an SL line -> position committed
                           to a marketable close, joining this tick's flow)
    4. entry firing       (flat agents past threshold size an open at p_prev)
    5. entry cross        (balanced buy/sell entry flow crosses at p_prev with
                           no price impact; only the NET imbalance walks the
                           resting TP depth as market orders — the price-moving
                           flow. Residual order submission is shuffled per tick
                           (SL closes keep priority) so no agent id has a
                           standing price-priority advantage.)
    6. settlement         (positions back to flat bank realized PnL, re-arm)
    7. bankruptcy check   (agents at/under epsilon die; their orders purged)
    8. record             (time series logged via the injected recorder)
    9. termination        (stop early if the whole pool is dead)

NOTE: open limits never rest in this design (entries are IOC), so the old
rolling-window expiry (cfg.W) is a structural no-op and is no longer called.

RECORDER INTERFACE (dependency-injected, so analysis.py is swappable)
The Simulation needs only an object exposing `record(**fields)` and a `history`
dict-of-lists. A minimal fallback (_DictRecorder) is provided so the loop runs
standalone now; analysis.Recorder will be the richer drop-in later.

A NOTE ON total_capital AND THE §24 MONOTONICITY CHECK (flagged)
Capital marked to market in EUR terms, Sum(eur) + p_int(t)*Sum(btc), is NOT
monotonically non-increasing: when p_int rises, the pool's BTC inventory revalues
upward, so the EUR-terms total can increase even though value only ever leaves
(via deaths / bailout swaps). The price-invariant aggregate Sum(eur)+x_0*Sum(btc)
is the clean monotone series (changes only at deaths). We therefore log
both: `total_capital` (mark-to-market — the pool-drain curve to study, §18) and
`total_capital_x0` (the clean invariant for the sanity check). §24's monotonicity
assertion should run against total_capital_x0, not the mark-to-market series.

Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from config import Config
from agents import Population, Side, House
from book_coin import CoinBook
from book import Book, LimitOrder, Dir, trades_to_fills, Fill


class _DictRecorder:
    """Minimal fallback recorder: appends each tick's fields into lists."""

    def __init__(self) -> None:
        self.history: dict[str, list] = {}

    def record(self, **fields) -> None:
        for k, v in fields.items():
            self.history.setdefault(k, []).append(v)

    def series(self, name: str) -> list:
        return self.history.get(name, [])


class Simulation:
    def __init__(self, cfg: Config, recorder=None,
                 rng: Optional[np.random.Generator] = None,
                 run_checks: bool = True,
                 plot_clearings: bool = False,
                 max_clearing_plots: int = 5,
                 snapshot_every: int = 0) -> None:
        self.cfg = cfg
        self.rng = rng if rng is not None else np.random.default_rng(cfg.seed)
        self.pop = Population(cfg, self.rng)
        self.house = House.seed(cfg)         # v1: funded central market maker
        self._bailouts_total = 0
        self.book = (CoinBook(last_price=cfg.x_0, size_eps=1e-12 / cfg.x_0, x_ref=cfg.x_0)
                     if cfg.book_mode == "coin" else Book(last_price=cfg.x_0, size_eps=1e-12 / cfg.x_0))      # the house owns the venue (CLOB)
        self.recorder = recorder if recorder is not None else _DictRecorder()
        self.p_int: float = cfg.x_0          # p_int(0) = x_0
        self._eur0 = sum(a.eur for a in self.pop.agents) + self.house.eur
        self._btc0 = sum(a.btc for a in self.pop.agents) + self.house.btc
        # initial per-agent holdings, captured BEFORE any trade. Needed to measure
        # wealth concentration honestly: comparing t=0 to t=T requires the SAME price,
        # otherwise the numeraire-valuation channel (eur/sqrt(p) vs btc*sqrt(p)) swamps it.
        self.eur0 = np.array([a.eur for a in self.pop.agents])
        self.btc0 = np.array([a.btc for a in self.pop.agents])
        self.run_checks = run_checks
        self.plot_clearings = plot_clearings
        self.max_clearing_plots = max_clearing_plots
        self._n_clearing_plots = 0
        # per-agent PnL snapshots (0 = off). Static keys captured once; pnl per snapshot.
        self.snapshot_every = snapshot_every
        self.snap_tick: list[int] = []
        self.snap_pnl: list[np.ndarray] = []
        self.agent_k0 = np.array([a.K0 for a in self.pop.agents])
        self.agent_is_long = np.array([a.side is Side.LONG for a in self.pop.agents])
        self.t = 0
        self.stopped_reason: Optional[str] = None
        self._last_trade_t: int = 0          # stall detector (cfg.stall_T)
        # per-round-trip log: one entry per settled position (side, TP/SL, realized
        # PnL, entry notional). Committed instrumentation — HANDOFF §7 complained
        # that the fill instrument was a monkeypatch that never survived; this one
        # lives in the engine.
        self.trade_log: list[dict] = []
        # ── stranding instrumentation (P2 taxonomy; additive, no RNG) ──
        # every _fire_close attempt that leaves a residual, classified by WHY it
        # stopped: "funding" = the budget clamp bit while opposite depth remained;
        # "liquidity" = the opposite book side was exhausted.
        self.close_fail = {"L_funding": 0, "L_liquidity": 0,
                           "S_funding": 0, "S_liquidity": 0}
        self.close_fail_agents = {"L_funding": set(), "L_liquidity": set(),
                                  "S_funding": set(), "S_liquidity": set()}
        self.close_attempts = {"L": 0, "S": 0}   # _fire_close submissions per side
        # evolution: per-agent realized PnL and notional accumulated THIS epoch.
        # Fitness is their ratio — dimensionless, so no currency is privileged.
        n2 = cfg.total_agents
        self._win_pnl = np.zeros(n2)
        self._win_not = np.zeros(n2)
        self.evolve_log: list[dict] = []     # per-epoch mix + switch counts

    # ── helpers ───────────────────────────────────────────────────────────────
    def _apply_fills(self, fills: list[Fill]) -> None:
        by_id = self.pop.by_id()
        for f in fills:
            a = by_id[f.agent_id]
            a.eur += f.eur_delta
            a.btc += f.btc_delta
            a.pos.apply_fill(f.eur_delta, f.btc_delta)   # trade tally for PnL
        for f in fills:                      # re-mark matched agents at the new price
            by_id[f.agent_id].mark_to_market(self.p_int)

    def _total_capital_x0(self) -> float:
        """Price-invariant aggregate over alive agents — the monotonic invariant."""
        x0 = self.cfg.x_0
        return float(sum(a.eur + a.btc * x0 for a in self.pop.alive()))

    def _pnl_by_side(self, p: float) -> tuple[float, float]:
        """Aggregate trade PnL (EUR) — realized + unrealized — for longs and shorts."""
        long_pnl = sum(a.total_pnl(p) for a in self.pop.agents if a.side is Side.LONG)
        short_pnl = sum(a.total_pnl(p) for a in self.pop.agents if a.side is Side.SHORT)
        return float(long_pnl), float(short_pnl)

    def _run_bailouts(self) -> int:
        """
        v1 house bailout. An agent is 'stuck' when its home-currency fraction has
        fallen below bailout_floor_frac * f. The house swaps the agent back toward
        the f split at p_int — value-neutral for the agent (K unchanged, just
        recomposed), funded from the house reserve. Capped by the house's holdings,
        so the house can run a pot dry (freeze) and stop rescuing that side.
        """
        cfg = self.cfg
        if not cfg.house_bailout:
            return 0
        p = self.p_int
        trigger = cfg.bailout_floor_frac * cfg.f
        n = 0
        for a in self.pop.alive():
            K = a.mark_to_market(p)
            if K <= 0:
                continue
            home_val = a.eur if a.side is Side.LONG else a.btc * p   # home value in EUR terms
            if home_val / K >= trigger:
                continue                                            # not stuck
            need_val = cfg.f * K - home_val                         # EUR-value of home to add
            if need_val <= 0:
                continue
            if a.side is Side.LONG:                                 # needs EUR; house pays EUR, takes BTC
                pay_eur = min(need_val, self.house.eur)
                if pay_eur <= 0:
                    continue                                        # house EUR pot frozen
                take_btc = pay_eur / p
                a.eur += pay_eur; a.btc -= take_btc
                self.house.eur -= pay_eur; self.house.btc += take_btc
                a.pos.apply_fill(pay_eur, -take_btc)               # agent: +EUR, -BTC
                self.house.pos.apply_fill(-pay_eur, take_btc)      # house: mirror
            else:                                                   # needs BTC; house pays BTC, takes EUR
                pay_btc = min(need_val / p, self.house.btc)
                if pay_btc <= 0:
                    continue                                        # house BTC pot frozen
                take_eur = pay_btc * p
                a.btc += pay_btc; a.eur -= take_eur
                self.house.btc -= pay_btc; self.house.eur += take_eur
                a.pos.apply_fill(-take_eur, pay_btc)               # agent: -EUR, +BTC
                self.house.pos.apply_fill(take_eur, -pay_btc)      # house: mirror
            a.mark_to_market(p)
            n += 1
        self._bailouts_total += n
        return n

    # ── one tick: continuous CLOB ───────────────────────────────────────────────
    def _submit(self, o, **kw):
        """Submit to the book, apply resulting trade fills, advance the price."""
        trades = self.book.submit(o, **kw)
        if trades:
            self._apply_fills(trades_to_fills(trades))
            self.p_int = self.book.last_price
        self._trades_this_tick.extend(trades)
        return trades

    def _step_rest(self, t: int, sl_buys: list, sl_sells: list) -> None:
        """entry_mode="rest" — the v5 pure CLOB (no auction).

        SL closes fire as market orders walking the book. Entries are limits at
        the last price: fill what crosses, REST the remainder — the model's
        first passive depth that is not a winner waiting. One resting entry per
        agent; a clock-fire while flat cancels-and-replaces it at the live
        price (b'), bounding staleness by the agent's own period d/c.
        Submission order is shuffled on the dedicated (seed, 0xA1FA, t) stream.
        Maker-fill solvency: a resting BUY at px can only ever pay px per coin,
        so capping size at eur/px at submission makes later maker fills safe;
        the close-begin hook cancels the entry before any cover can drain EUR."""
        cfg, book = self.cfg, self.book
        srng = np.random.default_rng([cfg.seed or 0, 0xA1FA, t])
        closes = sl_buys + sl_sells
        order = srng.permutation(len(closes)) if len(closes) > 1 else range(len(closes))
        for i in order:
            a, sz = closes[i]
            if not self._close_unfinished(a):
                self._settle_if_flat(a)              # home-flat: bank, don't re-trade
                continue
            if a.pos.b < 0 or (cfg.close_mode == "home" and a.side is Side.SHORT and cfg.exit_promise in ("own_coin", "spend_short")):
                # short cover: budget-capped BUY (home-spend shorts stay BUYs at ANY
                # b -- the promise is q-denominated)
                budget = max(a.eur, 0.0)
                if cfg.close_mode == "home" and cfg.exit_promise in ("own_coin", "spend_short"):
                    budget = max(0.0, min(a.eur, a.pos.q))
                self._submit(LimitOrder(a.id, Dir.BUY, 1e18, sz, t,
                                        is_close=True, pos_side=a.side),
                             eur_budget=budget, rest_residual=False)
            else:                                    # long close: SELL held coins
                self._submit(LimitOrder(a.id, Dir.SELL, 1e-15, sz, t,
                                        is_close=True, pos_side=a.side),
                             rest_residual=False,
                             btc_budget=(max(a.btc, 0.0) if cfg.symmetric_solvency else None))
        firing = [a for a in self.pop.alive()
                  if a.pos.b == 0 and not a.closing and a.ready_to_fire()
                  and (cfg.recycle or not a.opened_ever)]
        order = srng.permutation(len(firing)) if len(firing) > 1 else range(len(firing))
        for i in order:
            a = firing[i]
            a.reset_pressure()
            if a.entry_ref is not None:              # b': cancel-and-replace
                book.cancel(a.entry_ref)
                a.entry_ref = None
            # Marketable-to-touch: quote AT the opposite best, so entries can
            # actually cross the spread. Pricing at last_price alone is a fixed
            # point — every fill happens at last, so last never moves and price
            # formation dies (measured: frozen at x_0, TPs never touched). The
            # touch is the minimal aggression that keeps the price alive without
            # introducing a new parameter; residuals rest at the same level.
            if a.side is Side.LONG:
                px = book.best_ask if book.best_ask is not None else book.last_price
            else:
                px = book.best_bid if book.best_bid is not None else book.last_price
            sz = a.open_btc(cfg, px)
            if sz <= 0 or px <= 0:
                continue
            if a.side is Side.LONG:
                sz = min(sz, max(a.eur, 0.0) / px)   # maker-fill solvency cap
            else:
                sz = min(sz, max(a.btc, 0.0))
            if sz <= 1e-12 / cfg.x_0:
                continue
            a.opened_ever = True
            a.req_q = sz * px
            o = LimitOrder(a.id, Dir.BUY if a.side is Side.LONG else Dir.SELL,
                           px, sz, t, pos_side=a.side)
            self._submit(o, eur_budget=(max(a.eur, 0.0) if a.side is Side.LONG else None),
                         btc_budget=(max(a.btc, 0.0) if (a.side is Side.SHORT
                                     and cfg.symmetric_solvency) else None),
                         rest_residual=True)
            a.entry_ref = o.oref if (o.active and o.size > book.size_eps) else None

    def _fire_close(self, a, t: int) -> None:
        """Inject a marketable close for a position being exited (SL, or stuck cover).

        Instrumented (P2 taxonomy): if a residual remains after the walk, classify
        the stop — opposite side exhausted -> "liquidity"; opposite depth remains
        (the budget clamp broke the loop) -> "funding". Counters only."""
        if not self._close_unfinished(a):
            self._settle_if_flat(a)          # home-flat: bank, don't re-trade
            return
        eps = self.book.size_eps
        if self.cfg.close_mode == "home" and a.side is Side.SHORT:
            # v4 spend order: convert the remaining entry-EUR q at market. The
            # eur_budget is the true terminator (spend stops at q); the size just
            # needs headroom for cheap asks, hence the 4x factor.
            q_rem = a.pos.q
            if q_rem > 1e-9 * self.cfg.x_min:
                self.close_attempts["S"] += 1
                size = 4.0 * q_rem / max(self.book.last_price, 1e-300)
                self._submit(LimitOrder(a.id, Dir.BUY, 1e18, size, t,
                                        is_close=True, pos_side=Side.SHORT),
                             eur_budget=max(0.0, min(a.eur, q_rem)), rest_residual=False)
                if a.pos.q > 1e-9 * self.cfg.x_min:       # residual spend remains
                    key = "S_funding" if self.book.ask_btc() > eps else "S_liquidity"
                    self.close_fail[key] += 1
                    self.close_fail_agents[key].add(a.id)
            return
        if a.pos.b > 1e-12 and not (self.cfg.close_mode == "home" and a.side is Side.SHORT and self.cfg.exit_promise in ("own_coin", "spend_short")):            # long: sell all held BTC into the bids
            self.close_attempts["L"] += 1
            self._submit(LimitOrder(a.id, Dir.SELL, 1e-15, a.pos.b, t,
                                    is_close=True, pos_side=Side.LONG), rest_residual=False,
                         btc_budget=(max(a.btc, 0.0) if self.cfg.symmetric_solvency else None))
            if a.pos.b > 1e-12:                       # residual remains
                key = "L_funding" if self.book.bid_btc() > eps else "L_liquidity"
                self.close_fail[key] += 1
                self.close_fail_agents[key].add(a.id)
        elif a.pos.b < -1e-12:         # short: buy back, walking asks, budget-capped (solvent)
            self.close_attempts["S"] += 1
            self._submit(LimitOrder(a.id, Dir.BUY, 1e18, -a.pos.b, t,
                                    is_close=True, pos_side=Side.SHORT),
                         eur_budget=max(a.eur, 0.0), rest_residual=False)
            if a.pos.b < -1e-12:                      # residual remains
                key = "S_funding" if self.book.ask_btc() > eps else "S_liquidity"
                self.close_fail[key] += 1
                self.close_fail_agents[key].add(a.id)

    def _close_unfinished(self, a) -> bool:
        """Is a close still undelivered, measured in the position's HOME quantity?
        quantity mode: BTC still to re-trade (both tribes; v3 semantics).
        home mode, shorts: entry-EUR still to spend (the v4 spend-order promise)."""
        if self.cfg.close_mode == "home" and a.side is Side.SHORT:
            return a.pos.q > 1e-9 * self.cfg.x_min      # EUR still to deliver
        return abs(a.pos.b) > 1e-9 / self.cfg.x_0       # BTC dust, in model units

    def _rest_close(self, a, t: int) -> None:
        """sl_mode="limit": submit the reduce-only stop-limit at the SL level.
        Fills whatever crosses now; the remainder RESTS in the book (no walking
        past the stop level, no re-fired all-in market covers, no EUR burn)."""
        if a.pos.b > 1e-12:            # long close: SELL limit at the stop level
            o = LimitOrder(a.id, Dir.SELL, a.sl_level, a.pos.b, t,
                           is_close=True, pos_side=Side.LONG)
            a.close_ref = o.oref
            self._submit(o, btc_budget=(max(a.btc, 0.0)
                                        if self.cfg.symmetric_solvency else None))
        elif a.pos.b < -1e-12:         # short close: BUY limit at the stop level
            o = LimitOrder(a.id, Dir.BUY, a.sl_level, -a.pos.b, t,
                           is_close=True, pos_side=Side.SHORT)
            a.close_ref = o.oref
            self._submit(o, eur_budget=max(a.eur, 0.0))

    def _settle_if_flat(self, a) -> None:
        """A position whose HOME quantity is delivered (TP filled / SL cover done)
        is realized. quantity mode: flat = b≈0 (EUR realized). home mode, shorts:
        flat = q≈0 — the entry EUR is spent; any BTC residual b_res is the
        realized gain/loss IN COINS (it already sits in the wallet; realized_pnl
        marks it at the settle price for the EUR-denominated books)."""
        if a.sl_level is not None and not self._close_unfinished(a):
            realized = a.pos.pnl_quote(self.p_int)          # ≈ q at flat (quantity) / p*b_res (home)
            self.trade_log.append({
                "tick": self.t, "agent": a.id,
                "side": "L" if a.side is Side.LONG else "S",
                "exit": "SL" if a.closing else "TP",
                "pnl": float(realized),
                "pnl_base": float(a.pos.pnl_base(self.p_int)),   # home-gauge PnL (BTC)
                "entry_q": float(a.entry_q),
                "entry_tick": int(a.entry_tick),
                "K0": float(a.K0),
                "req_q": float(a.req_q),
            })
            self._win_pnl[a.id] += realized                 # epoch fitness tally
            self._win_not[a.id] += a.entry_q
            a.entry_q = 0.0
            if self.cfg.close_mode == "home":
                # exact banking: coins stay coins, EUR stays EUR. Freezing even DUST
                # coins at a settle-price EUR mark breaks zero-sum macroscopically
                # once the price wanders 10+ e-folds (1e-9 BTC at p=2e8 is 0.2 EUR).
                a.realized_base += a.pos.b
                a.realized_pnl += a.pos.q
            else:
                a.realized_pnl += realized                  # bank (EUR; v3 semantics, bit-compat)
            a.pos.b = 0.0
            a.pos.q = 0.0
            if a.tp_ref is not None:
                self.book.cancel(a.tp_ref)
            if a.entry_ref is not None:
                self.book.cancel(a.entry_ref)
                a.entry_ref = None
            if a.close_ref is not None:
                self.book.cancel(a.close_ref)
            a.clear_orders()
            a.reset_pressure()                              # re-arm the open clock

    def step(self, t: int) -> bool:
        cfg = self.cfg
        book = self.book
        p_prev = book.last_price
        self.p_int = p_prev
        self._trades_this_tick = []

        # 1. pressure (flat agents only) + mark
        self.pop.accrue_pressure(p_prev)

        # (no expiry step: entries are IOC and TP limits live with the position,
        #  so nothing in the book ever ages out — cfg.W is vestigial)

        # 2. every open position rests a TP limit (long sells above, short buys below).
        #    These resting exits ARE the book's two-sided depth. Also arm the SL line.
        for a in self.pop.alive():
            if (a.tp_ref is not None and not a.closing
                    and abs(a.pos.b) > abs(a.tp_pos_b) + 1e-9 / cfg.x_0):
                # entry_mode="rest": the resting entry filled further after the TP
                # rested — the position GREW, so the TP size is stale. Cancel; it
                # re-rests just below. (Shrinkage is a partial TP fill: position
                # and resting size fall in lockstep — leave it its queue priority.)
                self.book.cancel(a.tp_ref)
                a.tp_ref = None
            if a.pos.b != 0 and not a.closing and a.tp_ref is None:
                if a.entry_q == 0.0:                 # fresh position: log entry notional
                    a.entry_q = abs(a.pos.q)
                    a.entry_tick = t
                if a.side is Side.LONG:
                    tp_sz = a.pos.b
                    if cfg.close_mode == "home" and cfg.exit_promise == "spend_long":
                        # spend order (long): recover the entry EUR |q| at p_tp;
                        # under-sells by e^-tp at profit -- passive residual, no dump
                        tpp_l = a.tp_price(cfg)
                        if tpp_l > 0:
                            tp_sz = min(a.pos.b, max(0.0, -a.pos.q) / tpp_l)
                    o = LimitOrder(a.id, Dir.SELL, a.tp_price(cfg), tp_sz, t,
                                   is_close=True, pos_side=Side.LONG)
                    a.tp_ref = o.oref
                    a.tp_pos_b = a.pos.b
                    self._submit(o, btc_budget=(max(a.btc, 0.0) if cfg.symmetric_solvency else None))
                else:
                    tpp = a.tp_price(cfg)
                    if cfg.close_mode == "home":
                        if cfg.exit_promise in ("own_coin", "spend_short"):
                            # spend order: q/p_tp = |b|*e^{+tp} over-buys by construction
                            # (the par-4.9 flip-channel seed)
                            size = a.pos.q / tpp
                        else:                        # exact / spend_long: shorts BTC-exact
                            size = -a.pos.b
                        budget = max(0.0, min(a.eur, a.pos.q))
                    else:
                        size = -a.pos.b
                        budget = max(a.eur, 0.0)
                    o = LimitOrder(a.id, Dir.BUY, tpp, size, t,
                                   is_close=True, pos_side=Side.SHORT)
                    a.tp_ref = o.oref
                    a.tp_pos_b = a.pos.b
                    self._submit(o, eur_budget=budget)
                a.sl_level = a.sl_price(cfg)
                a.sl_is_buy = a.side is Side.SHORT
                self._settle_if_flat(a)

        # 3. SL triggers (dormant until touched): breach vs last price -> market close,
        #    which joins the entry flow below as aggressive sell (long) / buy (short).
        sl_buys: list[tuple] = []
        sl_sells: list[tuple] = []
        if cfg.sl_enabled:
            for a in self.pop.alive():
                if a.pos.b != 0 and not a.closing and a.sl_level is not None:
                    px = book.last_price
                    hit = (px >= a.sl_level) if a.sl_is_buy else (px <= a.sl_level)
                    if hit:
                        a.closing = True
                        if a.tp_ref is not None:
                            book.cancel(a.tp_ref); a.tp_ref = None
                        if a.entry_ref is not None:      # reduce-only from here: a resting
                            book.cancel(a.entry_ref)     # BUY could overdraw the EUR the
                            a.entry_ref = None           # cover is about to spend
                        if cfg.sl_mode == "limit":
                            # stop-limit discipline: reduce-only limit AT the stop level.
                            # No cascade (never walks past the level), no EUR burn while
                            # waiting. The remainder rests as passive depth — stuck short
                            # covers become bids, mirroring longs' TP asks (symmetry).
                            self._rest_close(a, t)
                            self._settle_if_flat(a)
                        elif cfg.sl_mode == "wait":
                            # all-or-nothing market cover: join the flow only if the FULL
                            # cover is affordable at p_prev; otherwise spend nothing.
                            if a.pos.b > 0:
                                qty = a.pos.b
                                if cfg.symmetric_solvency:
                                    qty = min(qty, max(a.btc, 0.0))
                                sl_sells.append((a, qty))
                            elif a.eur >= -a.pos.b * p_prev:
                                sl_buys.append((a, -a.pos.b))
                        elif a.pos.b > 0 and not (cfg.close_mode == "home" and a.side is Side.SHORT and cfg.exit_promise in ("own_coin", "spend_short")):
                            # market (v2): long cover SELL, self-funded. Home-spend shorts are
                            # EXCLUDED even at b>0: their close is dispatched in their HOME coin
                            # (BUY while q remains) -- b-sign dispatch on a q-promise is the
                            # par-4.9 flip churn.
                            qty = a.pos.b
                            if cfg.close_mode == "home" and cfg.exit_promise == "spend_long":
                                qty = min(qty, -a.pos.q / p_prev)   # recover entry EUR only
                            if cfg.symmetric_solvency:
                                qty = min(qty, max(a.btc, 0.0))
                            sl_sells.append((a, qty))
                        elif cfg.close_mode == "home":       # v4: spend the entry EUR — always
                            # self-funded (q <= held EUR by construction), so no
                            # affordability trap exists to cap against.
                            if cfg.exit_promise in ("own_coin", "spend_short"):
                                sl_buys.append((a, min(a.pos.q, max(a.eur, 0.0)) / p_prev))
                            else:
                                sl_buys.append((a, min(-a.pos.b, max(a.eur, 0.0) / p_prev)))
                        else:                                # market (v2): short cover BUY, needs EUR.
                            # Cap at what EUR affords at p_prev: the balanced crossing (step 5)
                            # applies cover fills UNCLAMPED, so an unaffordable cover would drive
                            # EUR negative. Capping here leaves the short partially covered and
                            # stranded-but-SOLVENT (the correct margin-free spot-short behaviour).
                            sl_buys.append((a, min(-a.pos.b, max(a.eur, 0.0) / p_prev)))

        # 3b. impatience closes (hold_fires_close): a clock-fire while HOLDING is
        #     an exit at market. Rides the existing close machinery: mark closing,
        #     cancel resting orders, and step 6's stuck-cover re-fire submits the
        #     market close this same tick via _fire_close (both entry modes).
        if cfg.hold_fires_close:
            for a in self.pop.alive():
                if a.pos.b != 0 and not a.closing and a.ready_to_fire():
                    a.reset_pressure()
                    if not self._close_unfinished(a):
                        # home-flat (the promise in the agent's OWN coin is
                        # delivered): settle & bank the coin residual -- never
                        # re-trade it (par 4.9 flip channel; "coins are banked
                        # as coins", FINDINGS V4.1)
                        self._settle_if_flat(a)
                        continue
                    a.closing = True
                    if a.tp_ref is not None:
                        self.book.cancel(a.tp_ref); a.tp_ref = None
                    if a.entry_ref is not None:
                        self.book.cancel(a.entry_ref); a.entry_ref = None

        if cfg.entry_mode == "rest":
            self._step_rest(t, sl_buys, sl_sells)
            sl_buys, sl_sells = [], []           # steps 4-5 below become exact no-ops

        # 4. gather ENTRY market flow (flat & ready) + SL closes
        buys: list[tuple] = list(sl_buys)      # (agent, btc)  BUY BTC
        sells: list[tuple] = list(sl_sells)    # (agent, btc)  SELL BTC
        for a in self.pop.alive():
            if cfg.entry_mode != "rest" and a.pos.b == 0 and not a.closing and a.ready_to_fire():
                if not cfg.recycle and a.opened_ever:
                    continue
                a.reset_pressure()
                sz = a.open_btc(cfg, p_prev)
                if sz <= 0:
                    continue
                a.opened_ever = True
                a.req_q = sz * p_prev               # requested EUR notional (gamma instrument)
                (buys if a.side is Side.LONG else sells).append((a, sz))

        # 4b. deterministic per-tick shuffle for the residual (book-walking) stage.
        #     Sequential submission gives earlier orders better prices; iterating in
        #     agent-id order would hand agent 0 a standing structural advantage over
        #     agent 299, breaking "every long is a scaled copy of every other long".
        #     SL closes keep priority (they are urgent, committed flow); entries are
        #     shuffled among themselves, SLs among themselves. The stream is its own
        #     SeedSequence((seed, tick)) — integer arithmetic, bit-identical across
        #     platforms, and independent of the main RNG (adding/removing this shuffle
        #     cannot perturb the capital draw or the phase jitter).
        def _shuffled(items: list, n_sl: int) -> list:
            if len(items) < 2:
                return items
            srng = np.random.default_rng([cfg.seed or 0, 0xA1FA, t])
            sl, rest = items[:n_sl], items[n_sl:]
            sl = [sl[i] for i in srng.permutation(len(sl))] if len(sl) > 1 else sl
            rest = [rest[i] for i in srng.permutation(len(rest))] if len(rest) > 1 else rest
            return sl + rest

        buys = _shuffled(buys, len(sl_buys))
        sells = _shuffled(sells, len(sl_sells))

        # 5. ENTRY AUCTION: balanced flow crosses at p_prev (no price impact); the net
        #    imbalance is aggressive and walks the resting exit book (moves the price).
        Bt = float(sum(sz for _, sz in buys))
        St = float(sum(sz for _, sz in sells))
        self._imb = Bt - St
        M = min(Bt, St)
        if M > 1e-12:
            fills = []
            for a, sz in buys:                              # balanced buys at p_prev
                b = sz * (M / Bt)
                fills.append(Fill(a.id, a.side, eur_delta=-b * p_prev, btc_delta=+b))
            for a, sz in sells:                             # balanced sells at p_prev
                b = sz * (M / St)
                fills.append(Fill(a.id, a.side, eur_delta=+b * p_prev, btc_delta=-b))
            self._apply_fills(fills)
        # imbalance -> market order(s) walking the book (the price-moving flow)
        if Bt - St > 1e-12:                                 # net buying: walk the asks up
            for a, sz in buys:
                resid = sz * (1 - M / Bt)
                if resid > 1e-12:
                    budget = max(a.eur, 0.0)
                    if cfg.close_mode == "home" and a.closing and a.side is Side.SHORT:
                        budget = max(0.0, min(a.eur, a.pos.q))   # spend cap = home quantity left
                    self._submit(LimitOrder(a.id, Dir.BUY, 1e18, resid, t, pos_side=a.side),
                                 eur_budget=budget, rest_residual=False)
        elif St - Bt > 1e-12:                               # net selling: walk the bids down
            for a, sz in sells:
                resid = sz * (1 - M / St)
                if resid > 1e-12:
                    self._submit(LimitOrder(a.id, Dir.SELL, 1e-15, resid, t, pos_side=a.side),
                                 rest_residual=False,
                                 btc_budget=(max(a.btc, 0.0) if cfg.symmetric_solvency else None))

        # 6. settlement: drop tp_ref for TP limits that fully filled (position exited passively)
        live_refs = {o.oref for o in (book.bids + book.asks) if o.active}
        for a in self.pop.alive():
            if a.tp_ref is not None and a.tp_ref not in live_refs:
                a.tp_ref = None
            if a.close_ref is not None and a.close_ref not in live_refs:
                a.close_ref = None                          # stop-limit fully consumed
            if a.closing and self._close_unfinished(a):      # stuck SL covers (home-quantity test)
                if cfg.sl_mode == "limit":
                    if a.close_ref is None:                  # not resting: (re)place at the stop level
                        self._rest_close(a, t)
                elif cfg.sl_mode == "wait":
                    # all-or-nothing: fire the market cover only when fully affordable now
                    if a.pos.b > 0 or a.eur >= -a.pos.b * book.last_price:
                        self._fire_close(a, t)
                else:
                    self._fire_close(a, t)
            self._settle_if_flat(a)

        # 6b. evolution epoch: within-tribe imitation of the sizing convention.
        #     Fitness = window realized PnL / window entry notional (dimensionless;
        #     an EUR- or BTC-denominated fitness would privilege that currency and
        #     reintroduce the §3(f) disease as the cure). Longs imitate longs and
        #     shorts imitate shorts: the trait answers "which conversion should MY
        #     tribe use", and within-tribe comparison needs no numeraire choice.
        #     Dedicated SeedSequence((seed, 0xEB01, t)) stream: portable, and
        #     independent of the capital draw / jitter / shuffle streams.
        if cfg.evolve and t % cfg.evolve_every == 0:
            erng = np.random.default_rng([cfg.seed or 0, 0xEB01, t])
            fit = np.where(self._win_not > 0, self._win_pnl / np.maximum(self._win_not, 1e-300), np.nan)
            switches = 0
            for tribe in (Side.LONG, Side.SHORT):
                pool = [a for a in self.pop.alive() if a.side is tribe]
                for a in pool:
                    if erng.random() >= cfg.evolve_frac:
                        continue
                    if np.isnan(fit[a.id]):
                        continue                      # no settled trades: nothing learned
                    peer = pool[int(erng.integers(len(pool)))]
                    if peer.id != a.id and not np.isnan(fit[peer.id])                             and fit[peer.id] > fit[a.id] and peer.conv_live != a.conv_live:
                        a.conv_live = peer.conv_live
                        switches += 1
                    if erng.random() < cfg.evolve_mutate:
                        a.conv_live = not a.conv_live
                        switches += 1
            self._win_pnl[:] = 0.0
            self._win_not[:] = 0.0
            mix_l = np.mean([a.conv_live for a in self.pop.agents if a.side is Side.LONG])
            mix_s = np.mean([a.conv_live for a in self.pop.agents if a.side is Side.SHORT])
            self.evolve_log.append({"tick": t, "mix_long": float(mix_l),
                                    "mix_short": float(mix_s), "switches": switches})

        # 7. bankruptcy (bailout retained but off by default in CLOB era)
        if self.cfg.bailout_before_bankruptcy:
            n_bail = self._run_bailouts()
            dead = self.pop.apply_bankruptcies(self.p_int)
        else:
            dead = self.pop.apply_bankruptcies(self.p_int)
            n_bail = self._run_bailouts()
        for aid in dead:
            book.purge_agent(aid)
            self.pop.by_id()[aid].clear_orders()

        if self.run_checks:
            b = sum(a.eur for a in self.pop.agents) + self.house.eur
            c = sum(a.btc for a in self.pop.agents) + self.house.btc
            assert abs(b - self._eur0) < 1e-3 * max(abs(self._eur0), 1), "EUR not conserved"
            assert abs(c - self._btc0) < 1e-3 * max(abs(self._btc0), 1), "BTC not conserved"

        # 8. record
        n_long, n_short = self.pop.alive_count()
        n_bid, n_ask = book.depth()
        pnl_l, pnl_s = self._pnl_by_side(self.p_int)
        # diagnostics: open positions per side, and each tribe's share of
        # geometric-mean (X) wealth (1 X = p^-.5 EUR = p^.5 BTC). The X-share is the
        # numeraire-covariant transfer measure; EUR pnl_long/short is the misleading lens.
        open_l = sum(1 for a in self.pop.agents if a.side is Side.LONG and a.pos.b != 0)
        open_s = sum(1 for a in self.pop.agents if a.side is Side.SHORT and a.pos.b != 0)
        # stuck = committed to closing but unfillable; the stranding observable
        # (open counts include healthy positions and are side-symmetric without it)
        stuck_l = sum(1 for a in self.pop.agents
                      if a.side is Side.LONG and a.closing and self._close_unfinished(a))
        stuck_s = sum(1 for a in self.pop.agents
                      if a.side is Side.SHORT and a.closing and self._close_unfinished(a))
        _rp = self.p_int ** 0.5
        _wxL = sum(a.eur / _rp + a.btc * _rp for a in self.pop.agents if a.side is Side.LONG)
        _wxS = sum(a.eur / _rp + a.btc * _rp for a in self.pop.agents if a.side is Side.SHORT)
        long_x_share = _wxL / (_wxL + _wxS) if (_wxL + _wxS) else float("nan")
        matched_btc = float(sum(tr.size for tr in self._trades_this_tick))
        matched_eur = float(sum(tr.size * tr.price for tr in self._trades_this_tick))
        if self.snapshot_every and (t % self.snapshot_every == 0):
            self.snap_tick.append(t)
            self.snap_pnl.append(np.array([a.total_pnl(self.p_int) for a in self.pop.agents]))
        self.recorder.record(
            tick=t, p_int=self.p_int,
            crossed=bool(self._trades_this_tick),
            matched_eur=matched_eur, matched_btc=matched_btc,
            # book sides, NOT agent sides: bids are shorts' TP buybacks,
            # asks are longs' TP sells (old keys queue_long/queue_short
            # inverted the tribes and are retired)
            book_bids=n_bid, book_asks=n_ask,
            alive_long=n_long, alive_short=n_short,
            n_dead=len(dead), n_bailouts=n_bail,
            house_eur=self.house.eur, house_btc=self.house.btc,
            total_capital=self.pop.total_capital(self.p_int),
            total_capital_x0=self._total_capital_x0(),
            system_x0=self._total_capital_x0() + self.house.eur + self.house.btc * self.cfg.x_0,
            conv_live_long=float(np.mean([a.conv_live for a in self.pop.agents
                                          if a.side is Side.LONG])),
            conv_live_short=float(np.mean([a.conv_live for a in self.pop.agents
                                           if a.side is Side.SHORT])),
            pnl_long=pnl_l, pnl_short=pnl_s,
            pnl_house=self.house.pos.pnl_quote(self.p_int),   # 0 while dormant, real once bailouts/spread trade
            imbalance=getattr(self, "_imb", 0.0),
            open_long=open_l, open_short=open_s,           # stranding diagnostic
            stuck_long=stuck_l, stuck_short=stuck_s,       # the stranding observable proper
            long_x_share=long_x_share,                     # numeraire-covariant transfer diagnostic
        )

        if n_long + n_short == 0:
            self.stopped_reason = "all agents dead"
            return False
        if self._trades_this_tick:
            self._last_trade_t = t
        elif self.cfg.stall_T and t - self._last_trade_t >= self.cfg.stall_T:
            self.stopped_reason = (f"stalled: no trades for {self.cfg.stall_T} ticks "
                                   f"(absorbing state; HANDOFF-master par 4.7)")
            return False
        return True

    def run(self) -> "Simulation":
        for t in range(1, self.cfg.T + 1):
            self.t = t
            if not self.step(t):
                break
        else:
            self.stopped_reason = "reached T"
        return self

    # ── convenience ───────────────────────────────────────────────────────────
    def summary(self) -> str:
        h = self.recorder.history
        n_long, n_short = self.pop.alive_count()
        crossed_ticks = sum(1 for c in h.get("crossed", []) if c)
        cap0 = h.get("total_capital_x0", [self.cfg.K])[0]
        capN = h.get("total_capital_x0", [self.cfg.K])[-1]
        return (
            "Alpha Engine - run summary\n"
            f"  stopped           : {self.stopped_reason} at tick {self.t}\n"
            f"  agents alive      : {n_long + n_short}/{self.pop.cfg.total_agents}  "
            f"(long {n_long} / short {n_short})\n"
            f"  ticks with a clear: {crossed_ticks} / {self.t}\n"
            f"  p_int final       : {self.p_int:.6f}  (started {self.cfg.x_0})\n"
            f"  capital (at x_0)  : {cap0:,.0f} -> {capN:,.0f} EUR  "
            f"({100*(capN/cap0-1):+.1f}% drain)\n"
            f"  house (at x_0)    : {self.house.value(self.cfg.x_0):,.0f} EUR  "
            f"(eur {self.house.eur:,.0f} / btc {self.house.btc:,.2f})  "
            f"bailouts={self._bailouts_total:,}\n"
        )


if __name__ == "__main__":
    # 1) spec defaults — sparse by design (smallest fires every d_base/c = 1000 ticks)
    sim = Simulation(Config(T=1500, seed=42), run_checks=True).run()
    print(sim.summary())

    # 2) a livelier run so the auction actually crosses and capital visibly drains
    sim2 = Simulation(Config(c=0.02, T=1000, seed=42), run_checks=True).run()
    print(sim2.summary())

    # invariant: price-invariant capital is monotonically non-increasing (§24, corrected)
    cap = sim2.recorder.series("total_capital_x0")
    mono = all(cap[i] <= cap[i - 1] + 1e-6 for i in range(1, len(cap)))
    print("total_capital_x0 monotonic non-increasing:", mono)

    # invariant: p_int strictly positive, alive count never exceeds 2n
    pos = all(p > 0 for p in sim2.recorder.series("p_int"))
    cap_ok = all(l + s <= sim2.cfg.total_agents
                 for l, s in zip(sim2.recorder.series("alive_long"),
                                 sim2.recorder.series("alive_short")))
    print("p_int always positive:", pos, "| alive_count <= 2n:", cap_ok)

    # show that mark-to-market capital is NOT monotonic (the reason we log both)
    mtm = sim2.recorder.series("total_capital")
    mtm_mono = all(mtm[i] <= mtm[i - 1] + 1e-6 for i in range(1, len(mtm)))
    print("mark-to-market total_capital monotonic:", mtm_mono, "(expected False in general)")
